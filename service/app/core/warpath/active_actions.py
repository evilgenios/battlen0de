"""Normalizes an account's currently-in-progress activity into one flat
list, for the dashboard's Active Actions view.

This is a pure read of state WarpathConnection already collects from real
server replies (see connection.py) — it sends no protocol requests of its
own and invents no client-side countdowns. Every field on ActiveActionInfo
either comes straight off a server reply or is derived by comparing two
real server timestamps to the current time (e.g. "in_progress" vs
"finished" for a production line whose end_time has already passed).

What backs each activity_type, and why it's trustworthy:

- vehicle_* (traveling/gathering/returning/repairing/building/demolishing/
  delivering): connection.farm_vehicles, populated from
  mine_reply.get_vehicle_list_reply — a live protocol capture on
  2026-09-15 confirmed the per-vehicle `info` submessage really does carry
  x/y/start_time/end_time/max_gather_num, and `move_target_pos` the
  vehicle's destination. Idle (state 1) and destroyed (state 5) vehicles
  are not "active" and are excluded.
- production: connection.production_lines, populated from
  login_reply.playerdata_reply.building_produce — confirmed via the same
  2026-09-15 capture that verified Collect's gain_all_produce_reply shares
  this exact building_produce/produce_line/produce_cell shape.
- officer_task: connection.officer_tasks, populated from
  playerdata_reply.client_officer_task_data — real task_id/status pairs
  from the same trusted login-sync path. The `status` integer's meaning is
  NOT decoded anywhere in the reference material, so it's surfaced as-is
  rather than guessed at.
- conquest_guard: connection's own conquest_guard_* attributes — already a
  fully real, already-exposed state machine (see api/conquest_guard.py);
  included here only when armed, so it shows up in the same operations
  view as everything else actually happening on the account.

Explicitly NOT included, because there is no proven evidence for it (see
the capability audit from 2026-09-16): army "gathering" timers, alloy
production as a distinct category, task/garrison/officer-request systems,
retrain/reform.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from .labels import vehicle_state_label

# Vehicle states that represent real, currently-in-progress activity.
# Idle (1) and destroyed (5) are excluded — see labels.VEHICLE_STATE_NAMES.
_ACTIVE_VEHICLE_STATES = {2, 3, 4, 6, 7, 8, 9, 10}

_VEHICLE_ACTIVITY_TYPES = {
    2: 'vehicle_traveling',
    3: 'vehicle_gathering',
    4: 'vehicle_returning',
    6: 'vehicle_repairing',
    7: 'vehicle_building',
    8: 'vehicle_demolishing',
    9: 'vehicle_gathering',
    10: 'vehicle_delivering',
}


def _vehicle_activities(connection) -> List[Dict[str, Any]]:
    activities = []
    for vehicle in connection.farm_vehicles:
        state = vehicle.get('state', 0)
        if state not in _ACTIVE_VEHICLE_STATES:
            continue
        activities.append({
            'activity_type': _VEHICLE_ACTIVITY_TYPES.get(state, 'vehicle_active'),
            'status': vehicle_state_label(state),
            'vehicle_id': vehicle.get('id'),
            'mine_id': vehicle.get('mine_id') or None,
            'map_id': vehicle.get('map_id') or None,
            'x': vehicle.get('x') or None,
            'y': vehicle.get('y') or None,
            'target_x': vehicle.get('target_x') or None,
            'target_y': vehicle.get('target_y') or None,
            'quantity': vehicle.get('max_gather_num') or None,
            'start_time': vehicle.get('start_time') or None,
            'end_time': vehicle.get('end_time') or None,
        })
    return activities


def list_production_cells(connection) -> List[Dict[str, Any]]:
    """Every known produce_cell across every production line, regardless of
    whether it has a real end_time — the shared extraction both
    _production_activities() (Active Actions, which only cares about cells
    with a real timer) and the dedicated /production endpoint (which wants
    the complete picture) build on, so the wire parsing exists in exactly
    one place."""
    cells = []
    now = time.time()
    for (bld_id, line_id), line in connection.production_lines.items():
        for cell in line.produce_cell:
            end_time = int(cell.time_unit.end_time) if cell.time_unit.HasField('end_time') else 0
            start_time = int(cell.time_unit.start_time) if cell.time_unit.HasField('start_time') else 0
            # A real, timestamp-derived status — not a client-invented
            # countdown: just comparing two server-provided times to now.
            status = 'in_progress' if end_time > now else ('finished' if end_time else 'unknown')
            cells.append({
                'building_id': bld_id,
                'line_id': line_id,
                'item_type_id': cell.item_type_id or None,
                'quantity': int(cell.item_produce_num) if cell.HasField('item_produce_num') else None,
                'start_time': start_time or None,
                'end_time': end_time or None,
                'status': status,
            })
    return cells


def _production_activities(connection) -> List[Dict[str, Any]]:
    activities = []
    for cell in list_production_cells(connection):
        if not cell['end_time']:
            continue
        activities.append({'activity_type': 'production', **cell})
    return activities


def _officer_task_activities(connection) -> List[Dict[str, Any]]:
    return [
        {
            'activity_type': 'officer_task',
            # The status integer's meaning isn't decoded in any reference
            # material available — surfaced as-is rather than guessed at.
            'status': f'status {task["status"]}',
            # task_id is a string on the wire (e.g. 'f1'), confirmed live —
            # never coerce it to int.
            'task_id': task.get('task_id') or None,
            'task_status': task.get('status'),
            'start_time': task.get('start_time') or None,
            'end_time': task.get('end_time') or None,
        }
        for task in connection.officer_tasks
    ]


def _conquest_guard_activity(connection) -> List[Dict[str, Any]]:
    if not connection.conquest_guard_enabled:
        return []
    status = 'exit_pending' if connection.conquest_guard_in_progress else 'armed'
    detail = None
    if connection.conquest_guard_last_attack:
        detail = f'last attack: {connection.conquest_guard_last_attack}'
    return [{
        'activity_type': 'conquest_guard',
        'status': status,
        'detail': detail,
    }]


def build_active_actions(connection) -> List[Dict[str, Any]]:
    """Real-time snapshot of everything this account is actually doing
    right now, per the protocol state WarpathConnection already tracks.
    Sends no requests; call a refresh endpoint first if the caller wants
    fresher upstream data."""
    return [
        *_vehicle_activities(connection),
        *_production_activities(connection),
        *_officer_task_activities(connection),
        *_conquest_guard_activity(connection),
    ]
