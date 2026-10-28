"""Conquest Guard: enable/disable/status. Ported from the latest Discord
bot's /conquest_guard command — the detection/exit logic itself lives on
WarpathConnection (app/core/warpath/connection.py's conquest_guard_* state
and _maybe_exit_conquest_for_attack/_observe_conquest_guard_attacks), one
instance per account, so enabling it for one account can never affect any
other account's connection — there is no shared/global guard state
anywhere in this codebase.

Requires an active, authenticated connection to enable (the guard binds
itself to the UID that is logged in AT THE MOMENT of enabling — see
connection.py's conquest_guard_armed_uid comment for why a later /connect
to a different account never inherits it).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.account_manager import AccountManager
from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_owned_account, get_repository
from app.schemas.conquest_guard import ConquestGuardStatus

router = APIRouter(prefix='/accounts', tags=['conquest-guard'])


def _status(session) -> ConquestGuardStatus:
    if session is None:
        return ConquestGuardStatus(enabled=False, armed_uid=0, in_progress=False, attempts=0)
    connection = session.connection
    return ConquestGuardStatus(
        enabled=connection.conquest_guard_enabled,
        armed_uid=connection.conquest_guard_armed_uid,
        connected_uid=connection.account_snapshot.get('uid'),
        in_progress=connection.conquest_guard_in_progress,
        attempts=connection.conquest_guard_attempts,
        last_attack=connection.conquest_guard_last_attack,
        last_result=connection.conquest_guard_last_result,
    )


@router.get('/{account_id}/conquest-guard', response_model=ConquestGuardStatus)
def get_conquest_guard(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> ConquestGuardStatus:
    return _status(manager.get_account(str(account_id)))


@router.post('/{account_id}/conquest-guard/enable', response_model=ConquestGuardStatus)
def enable_conquest_guard(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ConquestGuardStatus:
    session = manager.get_account(str(account_id))
    if session is None or not session.connection.connected:
        raise HTTPException(status_code=409, detail='account is not connected')
    own_uid = int(session.connection.account_snapshot.get('uid') or 0)
    if not own_uid:
        raise HTTPException(status_code=409, detail='account UID is not yet known — wait for login to finish')
    session.connection.conquest_guard_enabled = True
    session.connection.conquest_guard_armed_uid = own_uid
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='conquest_guard_enabled', detail={'armed_uid': own_uid})
    return _status(session)


@router.post('/{account_id}/conquest-guard/disable', response_model=ConquestGuardStatus)
def disable_conquest_guard(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ConquestGuardStatus:
    session = manager.get_account(str(account_id))
    if session is not None:
        session.connection.conquest_guard_enabled = False
        session.connection.conquest_guard_armed_uid = 0
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='conquest_guard_disabled', detail={})
    return _status(session)
