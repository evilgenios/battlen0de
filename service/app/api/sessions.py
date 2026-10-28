"""Live-session endpoints: connect/disconnect/reconnect/status.

Every route here goes through the ONE AccountManager the process started
with (see main.py) — never a second one. AccountManager only knows
accounts by account_id string; this module is the seam that converts
between that and the DB's uuid.UUID.

Registering a session with AccountManager on first /connect (rather than at
account-creation time) keeps POST /accounts a pure persistence operation —
the runtime session only exists once someone actually asks to connect.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.pilot_activation import PilotBlocked
from app.core.account_manager import AccountManager
from app.core.account_session import AccountSession, SessionState
from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_owned_account, get_repository
from app.schemas.sessions import LiveSessionStatus, SessionStatusResponse

router = APIRouter(prefix='/accounts', tags=['sessions'])


def _live_status(session: AccountSession | None) -> LiveSessionStatus | None:
    if session is None:
        return None
    return LiveSessionStatus(**session.status())


def _refresh_if_stale(
    manager: AccountManager, repo: AccountRepository, account: AccountRecord, session: AccountSession
) -> AccountSession:
    """AccountSession.credentials is a snapshot taken once, at registration
    time — it is never re-read from the database on its own. If this
    account's persisted credentials/device metadata were incomplete when a
    session was first registered (e.g. an earlier /connect attempt, or a
    link flow that ran before WARPATH_* device metadata was fully
    configured), that session fails validation once and then replays the
    exact same stale validation_errors() on every future /connect (or
    /reconnect — this must be called from BOTH, not just /connect, which is
    exactly the gap that let this bug resurface via /reconnect alone) from
    this same server process forever — even after the database row is
    corrected — because nothing ever tells it the row changed. Only ever
    swap in a fresh session when the old one isn't currently
    connecting/connected/reconnecting: never interrupt a live connection."""
    if session.is_active:
        return session
    credentials = repo.get_credentials(account.id)
    if credentials is not None and session.credentials != credentials:
        manager.remove_account(str(account.id))
        try:
            return manager.add_account(credentials)
        except ValueError:
            # Two concurrent /connect or /reconnect calls on the same stale,
            # inactive session can both pass the check above and race here —
            # the other request's add_account() already won by the time
            # ours runs. Self-heal instead of surfacing a 500: whatever
            # session is registered now (the other caller's fresh one, or
            # None if it also got swapped again) is what this request
            # should use.
            refreshed = manager.get_account(str(account.id))
            return refreshed if refreshed is not None else session
    return session


def _ensure_registered(
    manager: AccountManager, repo: AccountRepository, account: AccountRecord
) -> AccountSession:
    session = manager.get_account(str(account.id))
    if session is None:
        credentials = repo.get_credentials(account.id)
        if credentials is None:
            # Can't happen in practice (the row was just read), but never
            # let a missing-credentials edge case surface as an unhandled 500.
            raise HTTPException(status_code=503, detail='account credentials are unavailable')
        return manager.add_account(credentials)

    return _refresh_if_stale(manager, repo, account, session)


def _check_owner_capacity(manager, repo, account):
    owner = repo.get_user_by_id(account.owner_user_id)
    if owner is None or owner.status != 'active':
        raise HTTPException(409, 'account owner unavailable')
    active = sum(bool((s := manager.get_account(str(a.id))) and s.is_active)
                 for a in repo.list_accounts(account.owner_user_id) if a.id != account.id)
    if active >= owner.max_active_accounts:
        raise HTTPException(409, 'active account limit reached')


@router.post('/{account_id}/connect', response_model=SessionStatusResponse, status_code=202)
def connect_account(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> SessionStatusResponse:
    _check_owner_capacity(manager, repo, account)
    session = _ensure_registered(manager, repo, account)

    if session.is_active:
        raise HTTPException(status_code=409, detail=f'account is already {session.state.value}')

    try:
        started = manager.start(str(account_id))
    except PilotBlocked:
        raise
    except RuntimeError as exc:
        # MAX_CONCURRENT_SESSIONS reached — a capacity constraint, not a
        # bad request or a bad account.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not started:
        if session.state == SessionState.FAILED and session.last_error:
            # start() validated credentials and found them incomplete.
            # session.last_error here is always a list of missing FIELD
            # NAMES (WarpathCredentials.validation_errors()), never a value.
            raise HTTPException(status_code=422, detail=session.last_error)
        raise HTTPException(status_code=409, detail=f'could not start (currently {session.state.value})')

    repo.add_event(
        account_id=account_id,
        actor=f'user:{user.id}',
        event_type='account_connect_requested',
        detail={},
    )
    return SessionStatusResponse(account_id=account_id, db_status=account.status, live=_live_status(session))


@router.post('/{account_id}/disconnect', response_model=SessionStatusResponse)
def disconnect_account(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> SessionStatusResponse:
    session = manager.get_account(str(account_id))
    if session is None or not session.is_active:
        raise HTTPException(status_code=409, detail='account is not connected')

    manager.stop(str(account_id))
    repo.add_event(
        account_id=account_id,
        actor=f'user:{user.id}',
        event_type='account_disconnect_requested',
        detail={},
    )
    return SessionStatusResponse(account_id=account_id, db_status=account.status, live=_live_status(session))


@router.post('/{account_id}/reconnect', response_model=SessionStatusResponse, status_code=202)
def reconnect_account(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> SessionStatusResponse:
    _check_owner_capacity(manager, repo, account)
    session = manager.get_account(str(account_id))
    if session is None:
        raise HTTPException(status_code=409, detail='account has no session to reconnect; call /connect first')
    # Same stale-credentials refresh /connect gets — a session that was
    # registered with since-corrected credentials must not keep replaying
    # its original validation failure forever just because the caller used
    # /reconnect instead of /connect.
    session = _refresh_if_stale(manager, repo, account, session)

    # AccountManager.reconnect() now enforces max_concurrent_sessions the
    # same way start() does (see account_manager.py's _raise_if_at_capacity)
    # — mirror connect_account's handling of the same RuntimeError below.
    try:
        started = manager.reconnect(str(account_id))
    except PilotBlocked:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not started and session.state == SessionState.FAILED and session.last_error:
        raise HTTPException(status_code=422, detail=session.last_error)

    repo.add_event(
        account_id=account_id,
        actor=f'user:{user.id}',
        event_type='account_reconnect_requested',
        detail={},
    )
    return SessionStatusResponse(account_id=account_id, db_status=account.status, live=_live_status(session))


@router.get('/{account_id}/status', response_model=SessionStatusResponse)
def account_status(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> SessionStatusResponse:
    session = manager.get_account(str(account_id))
    return SessionStatusResponse(account_id=account_id, db_status=account.status, live=_live_status(session))


