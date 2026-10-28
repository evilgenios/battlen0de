"""Real per-account Mass Deploy operation: resolve a target player's
position, validate the Army Group and army slots, teleport (or rebuild) the
base into a nearby open footprint, and join the AG.

Ported from the latest Discord bot's `_run_mass_deploy` and its helpers
(_wait_for_reply, _position_error_can_retry, _prefer_visible_open_positions,
_deploy_or_rebuild_base, _select_group_armies, base_positions_around) — see
app/core/mass_deploy.py's module docstring for what could and could not be
ported before this pass, and the current pass's report for why this became
portable now (the real teleport/join-AG protocol calls, found in the
attached reference, now live on WarpathConnection).

Deliberate architectural change from the reference: the reference spawns
its OWN unmanaged WarpathConnection per account and waits for it to log in
(the global/legacy pattern this project has consistently rejected — see
app/core/account_manager.py's module docstring). This module never spawns a
connection: it only operates on an ALREADY-CONNECTED, ALREADY-AUTHENTICATED
connection that AccountManager/AccountSession already owns, exactly like
every other account action (collect/scan/farm/...). A disconnected account
is simply skipped by the caller (see mass_deploy.run_mass_deploy) — never
connected on this module's own initiative.

Everything else — the placement math, the retry/backoff behavior, the
"teleport items only, never premium currency" rule (use_item=True is the
only value ever passed to send_teleport_mainbase), the AG validation
rules — is preserved as-is.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

BASE_PLACEMENT_SPACING = 7
MASS_BASE_PLACEMENT_ATTEMPTS = 24

# Real values from the latest client (message (1).py) — land AGs accept
# army slots 1-5, navy AGs accept 2001-2003.
GROUP_ARMY_LAND = 10001
GROUP_ARMY_NAVY = 10002
GROUP_ARMY_SLOTS = {
    GROUP_ARMY_LAND: (1, 2, 3, 4, 5),
    GROUP_ARMY_NAVY: (2001, 2002, 2003),
}


def _oddr_to_cube(x: int, y: int):
    cube_x = int(x) - ((int(y) - (int(y) & 1)) // 2)
    cube_z = int(y)
    return cube_x, -cube_x - cube_z, cube_z


def _cube_to_oddr(x: int, _y: int, z: int):
    return int(x) + ((int(z) - (int(z) & 1)) // 2), int(z)


def _hex_distance(first, second) -> int:
    a = _oddr_to_cube(*first)
    b = _oddr_to_cube(*second)
    return max(abs(x - y) for x, y in zip(a, b))


def base_positions_around(target_x: int, target_y: int, limit: int = 120) -> List[tuple]:
    """Generate non-overlapping base centers around an Odd-R hex coordinate,
    spiraling outward in rings of BASE_PLACEMENT_SPACING."""
    center = _oddr_to_cube(target_x, target_y)
    positions: List[tuple] = []
    ring = 1
    while len(positions) < limit:
        offsets = []
        for dx in range(-ring, ring + 1):
            for dz in range(-ring, ring + 1):
                dy = -dx - dz
                if max(abs(dx), abs(dy), abs(dz)) == ring:
                    offsets.append((dx, dy, dz))
        offsets.sort(key=lambda item: (item[2], item[0], item[1]))
        for dx, dy, dz in offsets:
            x, y = _cube_to_oddr(
                center[0] + dx * BASE_PLACEMENT_SPACING,
                center[1] + dy * BASE_PLACEMENT_SPACING,
                center[2] + dz * BASE_PLACEMENT_SPACING,
            )
            if x >= 0 and y >= 0:
                positions.append((x, y))
                if len(positions) >= limit:
                    break
        ring += 1
    return positions


def _prefer_visible_open_positions(connection, candidates):
    """Put positions clear of visible bases/buildings first; the server is
    still authoritative — this is only a local ordering heuristic."""
    blockers = [
        (int(obj.get('x') or 0), int(obj.get('y') or 0))
        for obj in connection.known_map_objects.values()
        if obj.get('is_mainbase') or obj.get('client_building')
        if (
            not connection.current_map_id
            or not int(obj.get('map_id') or 0)
            or int(obj.get('map_id') or 0) == int(connection.current_map_id)
        )
    ]
    if not blockers:
        return list(candidates)
    clear, possibly_blocked = [], []
    for candidate in candidates:
        target = clear if all(
            _hex_distance(candidate, blocker) >= BASE_PLACEMENT_SPACING for blocker in blockers
        ) else possibly_blocked
        target.append(candidate)
    return clear + possibly_blocked


def _position_error_can_retry(error: Optional[dict]) -> bool:
    info = str((error or {}).get('info') or '').lower()
    return any(
        marker in info
        for marker in (
            'no_empty_pos', 'teleport_pos', 'position', 'occupied',
            'placement', 'place_', 'area_', 'map_block', 'terrain',
            'invalid_pos', 'blocked', 'no_space',
        )
    )


def _wait_for_reply(
    connection, serial_attribute: str, previous_serial: int, previous_error: int,
    *, timeout: float = 8.0, cancel_event=None,
):
    """Poll an already-connected connection's reply-serial counters — the
    AccountSession's own background thread is what advances them; this just
    waits for that to happen, matching the reference's identical polling
    loop."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return 'cancelled', None
        if getattr(connection, serial_attribute) > previous_serial:
            return 'reply', None
        if connection.server_error_serial > previous_error:
            return 'error', connection.last_server_error
        if not connection.is_active:
            return 'disconnected', connection.last_error
        time.sleep(0.05)
    return 'timeout', None


def select_group_armies(connection, requested_ids: Optional[List[int]], group_type: int, ag_id: int):
    allowed = set(GROUP_ARMY_SLOTS[group_type])
    wanted = sorted(allowed if requested_ids is None else requested_ids)
    invalid = [army_id for army_id in wanted if army_id not in allowed]
    if invalid:
        expected = ', '.join(str(v) for v in sorted(allowed))
        raise ValueError(f'army IDs {invalid} do not belong to this AG type; valid slots: {expected}')

    if not connection.armies:
        raise RuntimeError('the login reply did not include army-slot data')

    missing = [
        army_id for army_id in wanted
        if army_id not in connection.armies or connection.armies[army_id].get('equipment_id', 0) <= 0
    ]
    selected = [army_id for army_id in wanted if army_id not in missing]
    already = [army_id for army_id in selected if connection.armies[army_id].get('group_unique_id') == ag_id]
    busy = [
        army_id for army_id in selected
        if connection.armies[army_id].get('group_unique_id') not in (0, ag_id)
    ]
    selected = [army_id for army_id in selected if army_id not in already and army_id not in busy]
    return selected, already, missing, busy


def _deploy_or_rebuild_base(connection, candidates, *, start_index=0, cancel_event=None, max_attempts=MASS_BASE_PLACEMENT_ATTEMPTS):
    """Airlift (teleport-item) a base, then automatically rebuild it if the
    reply leaves it as an airborne base car — retries across candidate
    positions when the server rejects a specific footprint."""
    candidate_index = max(0, int(start_index))
    attempts = 0
    airlifted = False
    last_detail = 'no candidate positions were available'

    while candidate_index < len(candidates) and attempts < max_attempts:
        if cancel_event is not None and cancel_event.is_set():
            return False, 'cancelled before the next base placement request', candidate_index

        x, y = candidates[candidate_index]
        candidate_index += 1
        attempts += 1
        is_base_car = bool(connection.account_snapshot.get('base_is_car', False))
        old_error_serial = connection.server_error_serial

        if is_base_car:
            old_reply_serial = connection.base_move_reply_serial
            connection.send_build_mainbase(x, y)
            status, error = _wait_for_reply(
                connection, 'base_move_reply_serial', old_reply_serial, old_error_serial,
                timeout=10.0, cancel_event=cancel_event,
            )
            action = 'base rebuild'
            reply_data = connection.last_base_move_reply or {}
        else:
            old_reply_serial = connection.teleport_reply_serial
            # use_item=True always — teleport items only, no premium-currency
            # fallback exists anywhere in this path.
            connection.send_teleport_mainbase(x, y, use_item=True)
            status, error = _wait_for_reply(
                connection, 'teleport_reply_serial', old_reply_serial, old_error_serial,
                timeout=10.0, cancel_event=cancel_event,
            )
            action = 'airlift'
            reply_data = connection.last_teleport_reply or {}

        if status == 'reply':
            actual = reply_data.get('position') or {'x': x, 'y': y}
            still_car = bool(reply_data.get('is_car', connection.account_snapshot.get('base_is_car', False)))
            if not still_car:
                verb = 'airlifted and rebuilt' if airlifted else ('rebuilt' if is_base_car else 'airlifted')
                return True, f'success: {verb} at ({actual["x"]}, {actual["y"]}) after {attempts} position attempt(s)', candidate_index
            airlifted = airlifted or not is_base_car
            last_detail = f'{action} reached ({actual["x"]}, {actual["y"]}) but the base remained in airlift mode'
            continue

        if status == 'error':
            detail = (error or {}).get('info') or f'server rejected {action}'
            last_detail = str(detail)
            if _position_error_can_retry(error):
                continue
            return False, f'failed: {action}: {detail}', candidate_index
        if status == 'cancelled':
            return False, f'unconfirmed: cancellation arrived after the {action} request was sent', candidate_index
        return False, f'failed: {action} reply {status}', candidate_index

    suffix = f'{attempts} nearby position(s) tried'
    return False, f'failed: {last_detail} ({suffix})', candidate_index


def deploy_one_account(
    connection, *, ag_id: int, player_uid: int, army_ids: Optional[List[int]], group_type: int,
    cancel_event=None, position_index: int = 0,
) -> Dict[str, Any]:
    """The full per-account operation, run against an already-connected
    session's connection. Returns {'teleport': ..., 'ag': ..., 'error': ...,
    'position_index': ...} — position_index lets the caller keep handing
    out non-overlapping footprints across a whole batch, same as the
    reference's shared `position_index` across accounts."""
    result: Dict[str, Any] = {'teleport': 'not attempted', 'ag': 'not attempted', 'error': None}

    if cancel_event is not None and cancel_event.is_set():
        result['error'] = 'cancelled before this account started'
        return {**result, 'position_index': position_index}

    old_position_serial = connection.user_position_reply_serial
    old_error_serial = connection.server_error_serial
    connection.request_user_position(player_uid)
    position_status, position_error = _wait_for_reply(
        connection, 'user_position_reply_serial', old_position_serial, old_error_serial, cancel_event=cancel_event,
    )
    if position_status == 'cancelled':
        result['error'] = 'cancelled while resolving the target player'
        return {**result, 'position_index': position_index}
    target_position = connection.user_positions.get(player_uid)
    if position_status != 'reply' or not target_position:
        detail = (position_error or {}).get('info') if position_status == 'error' else f'player position lookup {position_status}'
        result['teleport'] = f'failed: {detail}'

    old_group_serial = connection.group_list_reply_serial
    old_error_serial = connection.server_error_serial
    connection.request_group_army_list()
    group_status, group_error = _wait_for_reply(
        connection, 'group_list_reply_serial', old_group_serial, old_error_serial, cancel_event=cancel_event,
    )
    if group_status == 'cancelled':
        result['error'] = 'cancelled while validating the AG'
        return {**result, 'position_index': position_index}

    group = connection.group_armies.get(ag_id)
    resolved_group_type = group_type
    if group_status == 'reply':
        if group is None:
            result['ag'] = "failed: AG is not in this account's alliance AG list"
        else:
            actual_type = int(group.get('group_type') or 0)
            if group_type and actual_type != group_type:
                result['ag'] = f'failed: AG type is {actual_type}, not {group_type}'
            else:
                resolved_group_type = actual_type
            if actual_type not in GROUP_ARMY_SLOTS:
                result['ag'] = f'failed: unsupported AG type {actual_type}'
            if group.get('max_num') and group.get('army_count', 0) >= group['max_num']:
                result['ag'] = 'failed: AG is already full'
    else:
        detail = (group_error or {}).get('info') if group_status == 'error' else f'AG list request {group_status}'
        result['ag'] = f'failed: cannot validate AG ({detail})'

    if str(result['ag']).startswith('failed:') or resolved_group_type not in GROUP_ARMY_SLOTS:
        result['teleport'] = 'skipped: AG validation failed'
        return {**result, 'position_index': position_index}

    try:
        selected, already, missing, busy = select_group_armies(connection, army_ids, resolved_group_type, ag_id)
    except Exception as error:
        result['ag'] = f'failed: {connection.safe_error_message(error)}'
        result['teleport'] = 'skipped: army validation failed'
        return {**result, 'position_index': position_index}

    notes = []
    if already:
        notes.append(f'already joined {already}')
    if missing:
        notes.append(f'empty/unavailable {missing}')
    if busy:
        notes.append(f'in another AG {busy}')
    if not selected:
        if already and not missing and not busy:
            result['ag'] = f'success: all requested slots already in AG {ag_id}'
        else:
            result['ag'] = 'failed: no eligible equipped slots; ' + ', '.join(notes)
            result['teleport'] = 'skipped: no eligible army slots'
        return {**result, 'position_index': position_index}

    if cancel_event is not None and cancel_event.is_set():
        result['teleport'] = 'cancelled before teleport'
        result['ag'] = 'cancelled before AG join'
        return {**result, 'position_index': position_index}

    if target_position:
        target_map = int(target_position.get('map_id') or 0)
        if connection.current_map_id and target_map and connection.current_map_id != target_map:
            result['teleport'] = f'failed: target is on map {target_map}, account is on map {connection.current_map_id}'
        else:
            old_scan_serial = connection.map_scan_reply_serial
            old_error_serial = connection.server_error_serial
            connection.send_map_view_request(target_position['x'], target_position['y'])
            _wait_for_reply(
                connection, 'map_scan_reply_serial', old_scan_serial, old_error_serial,
                timeout=5.0, cancel_event=cancel_event,
            )
            candidates = base_positions_around(
                target_position['x'], target_position['y'], limit=max(120, MASS_BASE_PLACEMENT_ATTEMPTS),
            )
            candidates = _prefer_visible_open_positions(connection, candidates)
            _, result['teleport'], position_index = _deploy_or_rebuild_base(
                connection, candidates, start_index=position_index, cancel_event=cancel_event,
            )

    if cancel_event is not None and cancel_event.is_set():
        result['ag'] = 'cancelled before AG join'
        return {**result, 'position_index': position_index}

    old_army_serial = connection.army_update_reply_serial
    old_error_serial = connection.server_error_serial
    connection.send_join_group_army(ag_id, selected, resolved_group_type)
    join_status, join_error = _wait_for_reply(
        connection, 'army_update_reply_serial', old_army_serial, old_error_serial,
        timeout=10.0, cancel_event=cancel_event,
    )
    if join_status == 'reply':
        joined = [army_id for army_id in selected if connection.armies.get(army_id, {}).get('group_unique_id') == ag_id]
        if len(joined) == len(selected):
            result['ag'] = f'success: joined slots {joined}'
        else:
            result['ag'] = f'unconfirmed: server updated army data; requested {selected}, confirmed {joined}'
    elif join_status == 'error':
        detail = (join_error or {}).get('info') or 'server rejected AG join'
        result['ag'] = f'failed: {detail}'
    elif join_status == 'cancelled':
        result['ag'] = 'unconfirmed: cancellation arrived after AG join was sent'
    else:
        result['ag'] = f'unconfirmed: AG join reply {join_status}; requested {selected}'
    if notes:
        result['ag'] += '; ' + ', '.join(notes)

    return {**result, 'position_index': position_index}
