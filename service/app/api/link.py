"""Owner-bound email linking using ONLY operator-configured WARPATH credentials.
No customer account is selected as a bootstrap vehicle. Device metadata
is validated and captured from WARPATH_* before requesting a code.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.link_challenge_store import ChallengeError, LinkChallengeStore
from app.core.warpath import lilith
from app.core.warpath.credentials import WarpathCredentials
from app.db.repository import DEVICE_METADATA_FIELDS, AccountRepository
from app.deps import AuthenticatedUser, get_current_user, get_link_challenge_store, get_repository, get_dashboard_sessions
from app.security.identity import canonical_identity
from app.schemas.accounts import AccountResponse
from app.schemas.link import LinkRequestBody, LinkRequestResponse, LinkVerifyBody

router = APIRouter(prefix='/accounts/link', tags=['link'])


def _resolve_vehicle() -> Optional[WarpathCredentials]:
    vehicle = WarpathCredentials.from_env('link-vehicle')
    return vehicle if vehicle.app_uid and vehicle.app_token else None


def _device_metadata_template() -> WarpathCredentials:
    """Client/device metadata for newly-linked accounts, sourced from
    WARPATH_* environment variables — see this module's docstring."""
    return WarpathCredentials.from_env('link-template')


def _is_valid_vehicle(vehicle: WarpathCredentials) -> bool:
    """A usable vehicle needs a Lilith-shaped numeric app_uid (send_login_code
    sends it as a JSON int) and a non-empty app_token. Anything else can
    never be a real Lilith session and must never reach the Lilith client —
    letting a malformed value through crashes int(vehicle.app_uid) deep
    inside lilith.send_login_code() as an unhandled 500 instead of the clean
    503 this check produces."""
    return canonical_identity(vehicle.app_uid) is not None and bool(vehicle.app_token)


def _no_vehicle_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail='Account linking is unavailable. An operator must configure WARPATH_APP_UID and WARPATH_APP_TOKEN.',
    )


def _invalid_vehicle_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail='Vehicle session is invalid; a valid bootstrap account is required.',
    )


def _preflight(request, repo, user, target_id):
    owner = repo.get_user_by_id(user.id)
    if owner is None or owner.status != 'active':
        raise HTTPException(409, 'account owner unavailable')
    if target_id is None:
        if len(repo.list_accounts(user.id)) >= owner.max_accounts:
            raise HTTPException(409, 'linked account limit reached')
        return
    target = repo.get_account(target_id)
    # No admin bypass: relinking is always bound to the proved owner's row.
    if target is None or target.owner_user_id != user.id:
        raise HTTPException(404, 'relink target not found')
    if target.status not in ('active', 'needs_reauth'):
        raise HTTPException(409, 'account status prevents relinking')
    session = request.app.state.account_manager.get_account(str(target_id))
    if session and session.is_active:
        raise HTTPException(409, 'disconnect the account before relinking')


@router.post('/request', response_model=LinkRequestResponse, status_code=202)
def request_link(
    body: LinkRequestBody,
    request: Request,
    identity=Depends(get_dashboard_sessions),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    store: LinkChallengeStore = Depends(get_link_challenge_store),
) -> LinkRequestResponse:
    email = body.email.strip().lower()

    # Explicit resend IDs are checked before configuration lookup or Lilith.
    if body.challenge_id and store.get(body.challenge_id, user.id) is None:
        raise HTTPException(status_code=410, detail='Verification request not found or expired.')
    with request.app.state.lifecycle_lock:
        _preflight(request, repo, user, body.account_id)
    identity.throttle('link-send-minute', user.id, limit=3, seconds=60)
    identity.throttle('link-send-hour', user.id, limit=10, seconds=3600)
    try:
        vehicle = _resolve_vehicle()
        template = _device_metadata_template()
    except ValueError:
        raise HTTPException(503, 'operator linking configuration is invalid') from None
    if vehicle is None:
        raise _no_vehicle_error()
    if not _is_valid_vehicle(vehicle):
        raise _invalid_vehicle_error()
    if template.with_updates(app_uid='1', app_token='placeholder', device_id='placeholder').validation_errors():
        raise HTTPException(503, 'Account linking is unavailable: operator device metadata is incomplete.')
    try:
        pending = store.begin_send(owner_user_id=user.id, email=email, vehicle=vehicle,
                                   challenge_id=body.challenge_id, target_account_id=body.account_id, template=template)
    except ChallengeError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    link_session = None
    try:
        link_session = lilith.send_login_code(pending.vehicle, email, pending.link_session)
    except Exception:
        # Upstream messages can contain secrets. Do not log or echo them.
        raise HTTPException(status_code=503, detail='Could not send a verification code through Lilith.') from None
    finally:
        store.finish_send(pending.challenge_id, user.id, link_session)

    repo.add_event(
        account_id=None,
        actor=f'user:{user.id}',
        event_type='account_link_requested',
        detail={'email': email},
    )

    return LinkRequestResponse(challenge_id=pending.challenge_id, email=email, expires_in_seconds=store.ttl_seconds)


@router.post('/verify', response_model=AccountResponse, status_code=201)
def verify_link(
    body: LinkVerifyBody,
    request: Request,
    identity=Depends(get_dashboard_sessions),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    store: LinkChallengeStore = Depends(get_link_challenge_store),
) -> AccountResponse:
    if store.get(body.challenge_id, user.id) is None:
        raise HTTPException(410, 'Verification request not found or expired.')
    identity.throttle('link-verify', user.id, limit=30, seconds=300)
    try:
        pending = store.claim_verification(body.challenge_id, user.id)
    except ChallengeError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None

    try:
        with request.app.state.lifecycle_lock:
            _preflight(request, repo, user, pending.target_account_id)
    except Exception:
        store.finish_verification(body.challenge_id, user.id, success=False)
        raise
    failure_status = None
    try:
        uid, token = lilith.verify_login_code(pending.vehicle, pending.email, body.code, pending.link_session)
    except lilith.LilithLoginError:
        failure_status = 422
    except Exception:
        failure_status = 503
    # Leave the exception context before persistence: even a failing event
    # write must not chain/log an upstream exception containing the code.
    store.finish_verification(body.challenge_id, user.id, success=failure_status is None)
    if failure_status == 422:
        repo.add_event(account_id=None, actor=f'user:{user.id}', event_type='account_link_failed',
                       detail={'email': pending.email, 'error': 'verification rejected'})
        raise HTTPException(status_code=422, detail='Verification failed. Check the code or request a new one.')
    if failure_status:
        raise HTTPException(status_code=503, detail='Could not reach the Lilith account service.')

    if canonical_identity(uid) is None or not token or int(uid) > 9223372036854775807:
        raise HTTPException(502, 'Lilith returned an invalid game identity')
    template = pending.template
    if template is None:
        raise HTTPException(503, 'linking metadata unavailable; request a new code')
    fields = dict(linked_email=pending.email, app_uid=uid, app_token=token,
                  device_id=pending.link_session.device_id, profile_uid=int(uid), platform=template.platform,
                  device_metadata={field: getattr(template, field) for field in DEVICE_METADATA_FIELDS})
    with request.app.state.lifecycle_lock:
        _preflight(request, repo, user, pending.target_account_id)
        if pending.target_account_id:
            account = repo.relink_account(pending.target_account_id, owner_user_id=user.id, **fields)
            manager = request.app.state.account_manager
            if manager.get_account(str(account.id)) is not None:
                manager.remove_account(str(account.id))
        else:
            account = repo.create_account(owner_user_id=user.id, label=(body.label or pending.email).strip(), **fields)
    repo.add_event(
        account_id=account.id,
        actor=f'user:{user.id}',
        event_type='account_relinked' if pending.target_account_id else 'account_created',
        detail={'label': account.label, 'via': 'lilith_link'},
    )

    return AccountResponse.model_validate(account, from_attributes=True)


@router.delete('/{challenge_id}', status_code=204)
def discard_link(challenge_id: str, user: AuthenticatedUser = Depends(get_current_user),
                 store: LinkChallengeStore = Depends(get_link_challenge_store)) -> None:
    try:
        store.discard(challenge_id, user.id)
    except ChallengeError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
