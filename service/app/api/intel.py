"""Read-mostly account intelligence: vehicles, armies, Army Groups,
player profile, skins, map objects, locate bases, refresh, heartbeat.

Every field returned here comes from data WarpathConnection already
collects from normal server replies (see app/core/warpath/connection.py) —
nothing here invents a new protocol call except send_join_group_army /
send_exit_group_army / request_mainbase_position / request_user_position,
which were verified against the vendored protobuf schema before use (see
app/core/mass_deploy.py's module docstring for the same verification done
for Mass Deploy). GET routes never send a game request — each has a
matching refresh/join/leave route for that.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.account_manager import AccountManager
from app.core.mass_deploy import MassDeployValidationError, parse_army_ids, parse_group_type
from app.core.warpath.active_actions import build_active_actions, list_production_cells
from app.core.warpath.credentials import redact_secrets
from app.core.warpath.labels import base_state_label, vehicle_state_label
from app.core.warpath.mass_deploy_ops import GROUP_ARMY_SLOTS, _wait_for_reply, select_group_armies
from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_owned_account, get_repository, require_player_scout_access
from app.schemas.intel import (
    AccountSummary,
    ActiveActionInfo,
    ArmyGroupInfo,
    ArmyInfo,
    JoinArmyGroupRequest,
    JoinArmyGroupResponse,
    ProductionLineInfo,
    LeaveArmyGroupRequest,
    LeaveArmyGroupResponse,
    LocateBasesRequest,
    MainbasePosition,
    MapObjectInfo,
    ProfileInfo,
    RefreshResponse,
    SkinsResponse,
    VehicleInfo,
)
from app.schemas.actions import ActionResponse

router = APIRouter(prefix='/accounts', tags=['intel'])


def _session(manager: AccountManager, account_id: uuid.UUID):
    return manager.get_account(str(account_id))


def _connected_session(manager: AccountManager, account_id: uuid.UUID):
    session = _session(manager, account_id)
    if session is None or not session.connection.connected:
        raise HTTPException(status_code=409, detail='account is not connected')
    return session


def _perform(*, repo: AccountRepository, user: AuthenticatedUser, account_id, action_name: str, session, call) -> ActionResponse:
    try:
        call()
    except Exception as exc:
        message = redact_secrets(exc, session.credentials)
        repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_failed', detail={'action': action_name, 'error': message})
        raise HTTPException(status_code=503, detail=f'{action_name} failed: {message}') from exc
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_requested', detail={'action': action_name})
    return ActionResponse(detail=f'{action_name} requested')


@router.get('/{account_id}/summary', response_model=AccountSummary)
def account_summary(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> AccountSummary:
    session = _session(manager, account_id)
    if session is None:
        return AccountSummary()
    snap = session.connection.account_snapshot
    return AccountSummary(
        name=snap.get('name'),
        uid=snap.get('uid'),
        account_level=snap.get('account_level'),
        mainbase_level=snap.get('mainbase_level'),
        base_state=base_state_label(snap),
        base_x=snap.get('base_x'),
        base_y=snap.get('base_y'),
        current_map_id=session.connection.current_map_id,
        vehicle_count=len(session.connection.farm_vehicles),
        scout_plane_count=len(session.connection.scout_planes),
        map_object_count=len(session.connection.known_map_objects),
        army_count=len(session.connection.armies),
    )


@router.get('/{account_id}/vehicles', response_model=list[VehicleInfo])
def list_vehicles(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[VehicleInfo]:
    session = _session(manager, account_id)
    if session is None:
        return []
    return [
        VehicleInfo(**v, state_label=vehicle_state_label(v['state']))
        for v in session.connection.farm_vehicles
    ]


@router.get('/{account_id}/active-actions', response_model=list[ActiveActionInfo])
def list_active_actions(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[ActiveActionInfo]:
    """Real-time operations view: everything this account is provably doing
    right now, per already-collected protocol state (see
    app/core/warpath/active_actions.py). Sends no request of its own — call
    /refresh first for the freshest upstream data, same as /vehicles."""
    session = _session(manager, account_id)
    if session is None:
        return []
    return [ActiveActionInfo(**entry) for entry in build_active_actions(session.connection)]


@router.get('/{account_id}/production', response_model=list[ProductionLineInfo])
def list_production(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[ProductionLineInfo]:
    """The complete production picture — every known produce_cell, not just
    the ones with a real end_time (see list_active_actions for that
    filtered view). Same underlying connection.production_lines data,
    shared extraction via list_production_cells()."""
    session = _session(manager, account_id)
    if session is None:
        return []
    return [ProductionLineInfo(**cell) for cell in list_production_cells(session.connection)]


@router.get('/{account_id}/armies', response_model=list[ArmyInfo])
def list_armies(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[ArmyInfo]:
    session = _session(manager, account_id)
    if session is None:
        return []
    return [ArmyInfo(**entry) for entry in session.connection.armies.values()]


@router.get('/{account_id}/army-groups', response_model=list[ArmyGroupInfo])
def list_army_groups(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[ArmyGroupInfo]:
    session = _session(manager, account_id)
    if session is None:
        return []
    return [ArmyGroupInfo(**entry) for entry in session.connection.group_armies.values()]


@router.post('/{account_id}/army-groups/refresh', response_model=ActionResponse)
def refresh_army_groups(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    session = _connected_session(manager, account_id)
    return _perform(
        repo=repo, user=user, account_id=account_id, action_name='army_groups_refresh',
        session=session, call=session.connection.request_group_army_list,
    )


@router.post('/{account_id}/army-groups/{ag_id}/join', response_model=JoinArmyGroupResponse)
def join_army_group(
    account_id: uuid.UUID,
    ag_id: int,
    body: JoinArmyGroupRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> JoinArmyGroupResponse:
    """Waits for the resulting user_army_group_data_reply and reads back
    each selected army's group_unique_id to confirm the join actually took
    — a live test showed the join request succeeding server-side (the AG's
    army_count went up) while the dashboard kept showing "Join" instead of
    "Leave" because nothing ever re-checked the real membership state."""
    session = _connected_session(manager, account_id)
    connection = session.connection
    try:
        group_type = parse_group_type(body.group_type)
        army_ids = parse_army_ids(body.army_ids)
    except MassDeployValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    group = connection.group_armies.get(ag_id)
    if group is None:
        raise HTTPException(status_code=404, detail='Army Group not found in this account\'s AG list — refresh first')
    resolved_type = int(group.get('group_type') or group_type or 0)
    if resolved_type not in GROUP_ARMY_SLOTS:
        raise HTTPException(status_code=422, detail=f'unsupported AG type {resolved_type}')

    try:
        selected, _already, _missing, _busy = select_group_armies(connection, army_ids, resolved_type, ag_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not selected:
        raise HTTPException(status_code=422, detail='no eligible equipped army slots to join with')

    old_error_serial = connection.server_error_serial
    old_army_serial = connection.army_update_reply_serial
    try:
        connection.send_join_group_army(ag_id, selected, resolved_type)
    except Exception as exc:
        message = redact_secrets(exc, session.credentials)
        repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_failed', detail={'action': 'army_group_join', 'error': message})
        raise HTTPException(status_code=503, detail=f'army_group_join failed: {message}') from exc

    status, error = _wait_for_reply(connection, 'army_update_reply_serial', old_army_serial, old_error_serial, timeout=8.0)
    if status == 'error':
        detail = (error or {}).get('info') or 'join rejected'
        raise HTTPException(status_code=503, detail=f'army_group_join failed: {detail}')
    if status != 'reply':
        raise HTTPException(status_code=503, detail=f'army_group_join got no reply from the server ({status})')

    joined = [army_id for army_id in selected if connection.armies.get(army_id, {}).get('group_unique_id') == ag_id]
    unconfirmed = [army_id for army_id in selected if army_id not in joined]
    repo.add_event(
        account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
        detail={'action': 'army_group_join', 'ag_id': ag_id, 'joined_army_ids': joined, 'unconfirmed_army_ids': unconfirmed},
    )
    return JoinArmyGroupResponse(ag_id=ag_id, joined_army_ids=joined, unconfirmed_army_ids=unconfirmed)


@router.post('/{account_id}/army-groups/leave', response_model=LeaveArmyGroupResponse)
def leave_army_group(
    account_id: uuid.UUID,
    body: LeaveArmyGroupRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> LeaveArmyGroupResponse:
    session = _connected_session(manager, account_id)
    connection = session.connection
    old_error_serial = connection.server_error_serial
    old_army_serial = connection.army_update_reply_serial
    try:
        connection.send_exit_group_army(body.army_id)
    except Exception as exc:
        message = redact_secrets(exc, session.credentials)
        repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_failed', detail={'action': 'army_group_leave', 'error': message})
        raise HTTPException(status_code=503, detail=f'army_group_leave failed: {message}') from exc

    status, error = _wait_for_reply(connection, 'army_update_reply_serial', old_army_serial, old_error_serial, timeout=8.0)
    if status == 'error':
        detail = (error or {}).get('info') or 'leave rejected'
        raise HTTPException(status_code=503, detail=f'army_group_leave failed: {detail}')
    if status != 'reply':
        raise HTTPException(status_code=503, detail=f'army_group_leave got no reply from the server ({status})')

    left = connection.armies.get(body.army_id, {}).get('group_unique_id', 0) == 0
    repo.add_event(
        account_id=account_id, actor=f'user:{user.id}', event_type='action_requested',
        detail={'action': 'army_group_leave', 'army_id': body.army_id, 'left': left},
    )
    return LeaveArmyGroupResponse(army_id=body.army_id, left=left)


@router.get('/{account_id}/profile/{uid}', response_model=ProfileInfo)
def get_profile(
    account_id: uuid.UUID,
    uid: int,
    account: AccountRecord = Depends(get_owned_account),
    scout_user: AuthenticatedUser = Depends(require_player_scout_access),
    manager: AccountManager = Depends(get_account_manager),
) -> ProfileInfo:
    session = _session(manager, account_id)
    entry = session.connection.profile_cache.get(uid) if session else None
    if entry is None:
        raise HTTPException(status_code=404, detail='no cached profile for this UID yet — refresh first')
    return ProfileInfo(**{k: entry[k] for k in ('uid', 'name', 'guild_id', 'guild_name', 'power', 'skin_point', 'commander_skin', 'title_skin')})


@router.post('/{account_id}/profile/{uid}/refresh', response_model=ActionResponse)
def refresh_profile(
    account_id: uuid.UUID,
    uid: int,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(require_player_scout_access),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    session = _connected_session(manager, account_id)
    return _perform(
        repo=repo, user=user, account_id=account_id, action_name='profile_refresh',
        session=session, call=lambda: session.connection.request_player_profile(uid),
    )


@router.get('/{account_id}/skins', response_model=SkinsResponse)
def get_skins(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> SkinsResponse:
    session = _session(manager, account_id)
    return SkinsResponse(categories=session.connection.skin_data if session else {})


@router.get('/{account_id}/map-objects', response_model=list[MapObjectInfo])
def list_map_objects(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> list[MapObjectInfo]:
    session = _session(manager, account_id)
    if session is None:
        return []
    return [
        MapObjectInfo(
            unique_id=o['unique_id'], owner_id=o['owner_id'], x=o['x'], y=o['y'],
            object_type=o['object_type'], map_id=o['map_id'], is_mainbase=o.get('is_mainbase', False),
        )
        for o in session.connection.known_map_objects.values()
    ]


@router.post('/{account_id}/locate-bases', response_model=ActionResponse)
def locate_bases(
    account_id: uuid.UUID,
    body: LocateBasesRequest,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    """Optional player_uid -> exact main-base lookup for that player.
    Exact player lookup is a privileged Player Scout feature. Without a UID,
    the route only refreshes the visible area around the account's own base."""
    if body.player_uid is not None:
        require_player_scout_access(user=user, repo=repo)
    session = _connected_session(manager, account_id)
    if body.player_uid is not None:
        call = lambda: session.connection.request_mainbase_position(body.player_uid)  # noqa: E731
        name = 'locate_base'
    else:
        call = session.connection.send_map_around_request
        name = 'locate_nearby_bases'
    return _perform(repo=repo, user=user, account_id=account_id, action_name=name, session=session, call=call)


@router.get('/{account_id}/locate-bases/{player_uid}', response_model=MainbasePosition)
def get_located_base(
    account_id: uuid.UUID,
    player_uid: int,
    account: AccountRecord = Depends(get_owned_account),
    scout_user: AuthenticatedUser = Depends(require_player_scout_access),
    manager: AccountManager = Depends(get_account_manager),
) -> MainbasePosition:
    session = _session(manager, account_id)
    position = session.connection.mainbase_positions.get(player_uid) if session else None
    if position is None:
        raise HTTPException(status_code=404, detail='no cached position for this player yet — locate first')
    return MainbasePosition(player_id=position['player_id'], x=position['x'], y=position['y'])


@router.post('/{account_id}/refresh', response_model=RefreshResponse)
def refresh_account_data(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> RefreshResponse:
    session = _connected_session(manager, account_id)
    sent, failures = session.connection.request_debug_snapshots()
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='action_requested', detail={'action': 'refresh', 'sent': sent})
    return RefreshResponse(requested=sent, failures=failures)


@router.post('/{account_id}/heartbeat', response_model=ActionResponse)
def heartbeat(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> ActionResponse:
    session = _connected_session(manager, account_id)
    return _perform(repo=repo, user=user, account_id=account_id, action_name='heartbeat', session=session, call=session.connection.send_keepalive)
