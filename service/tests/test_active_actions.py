"""Tests for the Active Actions normalization (app/core/warpath/
active_actions.py). production_lines holds real protobuf objects in
production (see connection.py's _observe_playerdata), so these tests build
genuine down_pb2 messages for it rather than a plain stub — a plain dict/
stub would hide a HasField()-usage bug the way a hand-written fake once hid
a missing WarpathConnection attribute (see the earlier audit note in
account_manager.py). Everything else uses a lightweight stub, matching
test_mass_deploy_ops.py's ScriptedConnection pattern."""

from __future__ import annotations

import time

from app.core.warpath.active_actions import build_active_actions, list_production_cells
from app.core.warpath.protobuf import down_pb2


class StubConnection:
    def __init__(self):
        self.farm_vehicles = []
        self.production_lines = {}
        self.officer_tasks = []
        self.conquest_guard_enabled = False
        self.conquest_guard_in_progress = False
        self.conquest_guard_last_attack = None


def make_production_line(line_id: int, *, item_type_id: str, quantity: int, start_time: int, end_time: int):
    """Builds a real produce_line protobuf object — the same type
    connection.production_lines actually stores."""
    line = down_pb2.msg_playerdata_reply().building_produce.add().produce_line.add()
    line.line_id = line_id
    cell = line.produce_cell.add()
    cell.item_type_id = item_type_id
    cell.item_produce_num = quantity
    cell.time_unit.start_time = start_time
    cell.time_unit.end_time = end_time
    return line


def test_idle_and_destroyed_vehicles_are_not_active_actions():
    conn = StubConnection()
    conn.farm_vehicles = [{'id': 1, 'state': 1}, {'id': 2, 'state': 5}]
    assert build_active_actions(conn) == []


def test_gathering_vehicle_reports_real_position_and_timing():
    conn = StubConnection()
    conn.farm_vehicles = [{
        'id': 9, 'state': 3, 'mine_id': 555, 'map_id': 25045,
        'x': 47830, 'y': 50954, 'target_x': 47830, 'target_y': 50954,
        'max_gather_num': 2020000, 'start_time': 1789442955, 'end_time': 1789457136,
    }]
    [activity] = build_active_actions(conn)
    assert activity['activity_type'] == 'vehicle_gathering'
    assert activity['status'] == 'Gathering'
    assert activity['vehicle_id'] == 9
    assert activity['mine_id'] == 555
    assert activity['start_time'] == 1789442955
    assert activity['end_time'] == 1789457136
    assert activity['quantity'] == 2020000


def test_traveling_and_returning_vehicles_map_to_distinct_activity_types():
    conn = StubConnection()
    conn.farm_vehicles = [
        {'id': 1, 'state': 2},  # traveling to resource
        {'id': 2, 'state': 4},  # returning
    ]
    activities = {a['vehicle_id']: a['activity_type'] for a in build_active_actions(conn)}
    assert activities == {1: 'vehicle_traveling', 2: 'vehicle_returning'}


def test_production_with_future_end_time_is_in_progress():
    conn = StubConnection()
    conn.production_lines[(108, 1)] = make_production_line(
        1, item_type_id='steel', quantity=100, start_time=int(time.time()), end_time=int(time.time()) + 3600,
    )
    [activity] = build_active_actions(conn)
    assert activity['activity_type'] == 'production'
    assert activity['status'] == 'in_progress'
    assert activity['building_id'] == 108
    assert activity['item_type_id'] == 'steel'
    assert activity['quantity'] == 100


def test_production_with_past_end_time_is_finished_not_invented_as_pending():
    conn = StubConnection()
    conn.production_lines[(108, 1)] = make_production_line(
        1, item_type_id='steel', quantity=100, start_time=int(time.time()) - 7200, end_time=int(time.time()) - 3600,
    )
    [activity] = build_active_actions(conn)
    assert activity['status'] == 'finished'


def test_production_with_no_end_time_is_omitted_not_fabricated():
    """Defensive coverage, not a scenario the real wire can produce: time_unit's
    start_time/end_time are proto2 REQUIRED fields (confirmed by attempting to
    serialize one without them — protobuf refuses), so a real server can never
    actually send a produce_cell missing them. This only guards the parsing
    code itself against ever reporting a cell as an active action without a
    real end_time, in case that assumption is ever wrong."""
    conn = StubConnection()
    line = down_pb2.msg_playerdata_reply().building_produce.add().produce_line.add()
    line.line_id = 1
    line.produce_cell.add().item_type_id = 'steel'  # no time_unit set at all
    conn.production_lines[(108, 1)] = line
    assert build_active_actions(conn) == []


def test_officer_task_status_is_surfaced_raw_not_decoded():
    """task_id is a string on the wire, not numeric — confirmed live on a
    real account (task_id='f1'). Coercing it to int is exactly the bug a
    live-browser check caught after this endpoint shipped: the schema
    rejected the real value with a 500, silently rendered by the frontend
    as an empty "no activity" list instead of a visible error."""
    conn = StubConnection()
    conn.officer_tasks = [{'task_id': 'f1', 'status': 2}]
    [activity] = build_active_actions(conn)
    assert activity == {
        'activity_type': 'officer_task', 'status': 'status 2', 'task_id': 'f1', 'task_status': 2,
        'start_time': None, 'end_time': None,
    }


def test_officer_task_real_timing_is_surfaced_when_present():
    conn = StubConnection()
    conn.officer_tasks = [{'task_id': 'f1', 'status': 1, 'start_time': 1000, 'end_time': 2000}]
    [activity] = build_active_actions(conn)
    assert activity['start_time'] == 1000
    assert activity['end_time'] == 2000


def test_conquest_guard_disabled_produces_no_activity():
    conn = StubConnection()
    conn.conquest_guard_enabled = False
    assert build_active_actions(conn) == []


def test_conquest_guard_armed_reports_status():
    conn = StubConnection()
    conn.conquest_guard_enabled = True
    conn.conquest_guard_in_progress = False
    [activity] = build_active_actions(conn)
    assert activity == {'activity_type': 'conquest_guard', 'status': 'armed', 'detail': None}


def test_conquest_guard_exit_pending_is_distinguished_from_armed():
    conn = StubConnection()
    conn.conquest_guard_enabled = True
    conn.conquest_guard_in_progress = True
    [activity] = build_active_actions(conn)
    assert activity['status'] == 'exit_pending'


def test_multiple_activity_sources_combine_into_one_list():
    conn = StubConnection()
    conn.farm_vehicles = [{'id': 1, 'state': 3, 'mine_id': 1}]
    conn.officer_tasks = [{'task_id': 'f1', 'status': 0}]
    conn.conquest_guard_enabled = True
    activities = build_active_actions(conn)
    assert {a['activity_type'] for a in activities} == {'vehicle_gathering', 'officer_task', 'conquest_guard'}


def test_list_production_cells_includes_cells_with_no_end_time():
    """Defensive coverage (see the identical note on
    test_production_with_no_end_time_is_omitted_not_fabricated — a real
    cell always has start_time/end_time, this just proves the parser
    degrades to status 'unknown' instead of crashing or fabricating a
    timer if that guarantee were ever violated)."""
    conn = StubConnection()
    line = down_pb2.msg_playerdata_reply().building_produce.add().produce_line.add()
    line.line_id = 2
    line.produce_cell.add().item_type_id = 'oil'  # no time_unit at all
    conn.production_lines[(108, 2)] = line

    cells = list_production_cells(conn)
    assert cells == [{
        'building_id': 108, 'line_id': 2, 'item_type_id': 'oil', 'quantity': None,
        'start_time': None, 'end_time': None, 'status': 'unknown',
    }]
    # And Active Actions correctly excludes it, same as before the refactor.
    assert build_active_actions(conn) == []


def test_list_production_cells_matches_active_actions_status_for_timed_cells():
    conn = StubConnection()
    conn.production_lines[(108, 1)] = make_production_line(
        1, item_type_id='steel', quantity=50, start_time=int(time.time()) - 100, end_time=int(time.time()) + 100,
    )
    [cell] = list_production_cells(conn)
    [activity] = build_active_actions(conn)
    assert cell['status'] == activity['status'] == 'in_progress'
