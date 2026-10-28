"""Action endpoints — one per EXISTING WarpathConnection method. No new
protocol behavior is added here; each route just calls the same method the
legacy Discord bot's slash commands call (see WarpathConnection in
app/core/warpath/connection.py: request_collect_all, send_map_view_request,
send_farm_search, send_recall_vehicle, send_continuous_scout)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.account_manager import AccountManager
from app.core.warpath.reply_actions import ActionBusy
from app.core.warpath.labels import RECALLABLE_VEHICLE_STATES
from app.core.warpath.mass_deploy_ops import _wait_for_reply
from app.core.warpath.credentials import redact_secrets
from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_owned_account, get_repository
from app.schemas.actions import (
    ActionResponse,
    CommandStatusResponse,
    CollectResponse,
    FarmRequest,
    FarmResponse,
    RecallAllResponse,
    RecallRequest,
    RecallResponse,
    ScanRequest,
    ScoutRequest,
)

router = APIRouter(prefix='/accounts', tags=['actions'])


def _connected_session(manager: AccountManager, account_id: uuid.UUID):
    session = manager.get_account(str(account_id))
    if session is None or not session.connection.connected:
        raise HTTPException(status_code=409, detail='account is not connected')
    return session


def _perform(
    *,
    account_id: uuid.UUID,
    action_name: str,
    repo: AccountRepository,
    user: AuthenticatedUser,
    session,
    call,
) -> ActionResponse:
    try:
        call()
    except Exception as exc:
        message = redact_secrets(exc, session.credentials)
        repo.add_event(
            account_id=account_id,
            actor=f'user:{user.id}',
            event_type='action_failed',
            detail={'action': action_name, 'error': message},
        )
        raise HTTPException(status_code=503, detail=f'{action_name} failed: {message}') from exc

    repo.add_event(
        account_id=account_id,
        actor=f'user:{user.id}',
        event_type='action_requested',
        detail={'action': action_name},
    )
    return ActionResponse(detail=f'{action_name} requested')


@router.get('/{account_id}/command-status', response_model=CommandStatusResponse)
def command_status(
    account_id: uuid.UUID,
    response: Response,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> CommandStatusResponse:
    """Local observation only, including disconnected/restricted accounts."""
    response.headers['Cache-Control'] = 'no-store'
    session = manager.get_account(str(account_id))
    if session is None:
        return CommandStatusResponse()
    return CommandStatusResponse(**session.connection.reply_actions.operational_status())


@router.post('/{account_id}/collect', response_model=CollectResponse)
def collect(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> CollectResponse:
    connection = _connected_session(manager, account_id).connection
    if not connection.production_building_ids:
        raise HTTPException(409, 'no production buildings known for this account yet — try Refresh first')
    try:
        tracker = connection.reply_actions
        tickets = connection.request_collect_all()
    except ActionBusy as exc:
        raise HTTPException(409, str(exc)) from None
    result = tracker.collect_result(tickets)
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
                   detail={'action': 'collect', **result})
    return CollectResponse(**result)


@router.post('/{account_id}/scan', response_model=ActionResponse)
def scan(
    account_id: uuid.UUID,
    body: ScanRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    session = _connected_session(manager, account_id)
    return _perform(
        account_id=account_id, action_name='scan', repo=repo, user=user, session=session,
        call=lambda: session.connection.send_map_view_request(body.center_x, body.center_y),
    )


@router.post('/{account_id}/farm', response_model=FarmResponse)
def farm(
    account_id: uuid.UUID,
    body: FarmRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> FarmResponse:
    connection = _connected_session(manager, account_id).connection
    try:
        result = connection.reply_actions.farm(body.resource, body.level)
    except ActionBusy as exc:
        raise HTTPException(409, str(exc)) from None
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
                   detail={'action': 'farm', **result})
    return FarmResponse(**result)


@router.post('/{account_id}/recall', response_model=RecallResponse)
def recall(
    account_id: uuid.UUID,
    body: RecallRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> RecallResponse:
    session = _connected_session(manager, account_id)
    connection = session.connection
    old_error_serial = connection.server_error_serial
    old_return_serial = connection.vehicle_return_reply_serial
    try:
        connection.send_recall_vehicle(body.vehicle_id)
    except Exception as exc:
        message = redact_secrets(exc, session.credentials)
        repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_failed', detail={'action': 'recall', 'error': message})
        raise HTTPException(status_code=503, detail=f'recall failed: {message}') from exc

    status, error = _wait_for_reply(connection, 'vehicle_return_reply_serial', old_return_serial, old_error_serial, timeout=8.0)
    if status == 'error':
        detail = (error or {}).get('info') or 'recall rejected'
        raise HTTPException(status_code=503, detail=f'recall failed: {detail}')
    if status != 'reply':
        raise HTTPException(status_code=503, detail=f'recall got no reply from the server ({status})')

    result = connection.last_vehicle_return_reply or {}
    repo.add_event(
        account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
        detail={'action': 'recall', 'vehicle_id': body.vehicle_id, 'state': result.get('state')},
    )
    return RecallResponse(vehicle_id=result.get('vehicle_id', body.vehicle_id), state=result.get('state', 0))


@router.post('/{account_id}/recall-all', response_model=RecallAllResponse)
def recall_all(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> RecallAllResponse:
    """Ported from the legacy bot's /recall_all: refresh the vehicle list,
    wait for the reply, then recall every vehicle in a recallable state
    (traveling/gathering/gathering-super-mine — the same set the official
    client's own "return all" action uses)."""
    session = _connected_session(manager, account_id)
    connection = session.connection
    old_serial = connection.vehicle_list_reply_serial
    old_error_serial = connection.server_error_serial
    connection.request_vehicle_list()
    status, error = _wait_for_reply(connection, 'vehicle_list_reply_serial', old_serial, old_error_serial, timeout=8.0)
    if status != 'reply':
        detail = (error or {}).get('info') if status == 'error' else status
        raise HTTPException(status_code=503, detail=f'could not refresh vehicle states: {detail or "no reply"}')

    recallable_ids = [
        v['id'] for v in connection.farm_vehicles
        if v.get('state') in RECALLABLE_VEHICLE_STATES and v.get('id', 0) > 0
    ]
    for vehicle_id in recallable_ids:
        try:
            connection.send_recall_vehicle(vehicle_id)
        except Exception as exc:
            message = redact_secrets(exc, session.credentials)
            repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_failed', detail={'action': 'recall_all', 'error': message})
            raise HTTPException(status_code=503, detail=f'recall_all failed: {message}') from exc

    repo.add_event(
        account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
        detail={'action': 'recall_all', 'vehicle_ids': recallable_ids},
    )
    return RecallAllResponse(vehicle_ids=recallable_ids)


@router.post('/{account_id}/scout', response_model=ActionResponse)
def scout(
    account_id: uuid.UUID,
    body: ScoutRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    session = _connected_session(manager, account_id)
    return _perform(
        account_id=account_id, action_name='scout', repo=repo, user=user, session=session,
        call=lambda: session.connection.send_continuous_scout(body.plane_id),
    )

