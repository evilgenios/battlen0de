"""Tests for the real, ported Mass Deploy placement/AG-join algorithm
(app/core/warpath/mass_deploy_ops.py). Uses a fully scripted fake
connection — no sockets, no real Warpath server, ever. Each request_*/
send_* method applies its scripted effect and advances the matching reply
serial immediately, so _wait_for_reply's first poll succeeds with no real
waiting (tests run fast and deterministically)."""

from __future__ import annotations

import threading

from app.core.warpath.mass_deploy_ops import GROUP_ARMY_LAND, GROUP_ARMY_NAVY, deploy_one_account

PLAYER_UID = 99
AG_ID = 42


class ScriptedConnection:
    def __init__(self):
        self.is_active = True
        self.last_error = None
        self.server_error_serial = 0
        self.last_server_error = None
        self.user_position_reply_serial = 0
        self.user_positions = {}
        self.group_list_reply_serial = 0
        self.group_armies = {}
        self.armies = {}
        self.map_scan_reply_serial = 0
        self.current_map_id = 5
        self.known_map_objects = {}
        self.teleport_reply_serial = 0
        self.last_teleport_reply = None
        self.base_move_reply_serial = 0
        self.last_base_move_reply = None
        self.army_update_reply_serial = 0
        self.account_snapshot = {}
        self.calls = []
        self.teleport_replies = None  # optional queue of {'position':..,'is_car':..} or 'error'
        self.join_confirms = None  # optional set of army_ids to actually confirm as joined

    def safe_error_message(self, exc):
        return str(exc)

    def request_user_position(self, uid):
        self.calls.append(('request_user_position', uid))
        self.user_position_reply_serial += 1

    def request_group_army_list(self):
        self.calls.append(('request_group_army_list',))
        self.group_list_reply_serial += 1

    def send_map_view_request(self, x, y):
        self.calls.append(('send_map_view_request', x, y))
        self.map_scan_reply_serial += 1

    def send_teleport_mainbase(self, x, y, use_item=True):
        self.calls.append(('send_teleport_mainbase', x, y, use_item))
        if self.teleport_replies:
            reply = self.teleport_replies.pop(0)
        else:
            reply = {'position': {'x': x, 'y': y}, 'is_car': False}
        if reply == 'error':
            self.last_server_error = {'info': 'no_empty_pos'}
            self.server_error_serial += 1
            return
        self.last_teleport_reply = reply
        self.account_snapshot['base_is_car'] = reply.get('is_car', False)
        self.teleport_reply_serial += 1

    def send_build_mainbase(self, x, y):
        self.calls.append(('send_build_mainbase', x, y))
        reply = {'position': {'x': x, 'y': y}, 'is_car': False}
        self.last_base_move_reply = reply
        self.account_snapshot['base_is_car'] = False
        self.base_move_reply_serial += 1

    def send_join_group_army(self, ag_id, army_ids, group_type):
        self.calls.append(('send_join_group_army', ag_id, list(army_ids), group_type))
        confirm = self.join_confirms if self.join_confirms is not None else set(army_ids)
        for army_id in army_ids:
            if army_id in self.armies and army_id in confirm:
                self.armies[army_id]['group_unique_id'] = ag_id
        self.army_update_reply_serial += 1


def make_connection(*, army_ids=(1, 2, 3, 4, 5)):
    connection = ScriptedConnection()
    connection.user_positions[PLAYER_UID] = {'player_id': PLAYER_UID, 'map_id': 5, 'x': 100, 'y': 100}
    connection.group_armies[AG_ID] = {
        'unique_id': AG_ID, 'group_type': GROUP_ARMY_LAND, 'max_num': 20, 'army_count': 2,
    }
    connection.armies = {
        aid: {'army_id': aid, 'equipment_id': 1, 'reserves': 3, 'master_obj_id': 0, 'group_unique_id': 0}
        for aid in army_ids
    }
    return connection


def test_successful_deploy_teleports_and_joins():
    connection = make_connection()
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1, 2], group_type=GROUP_ARMY_LAND,
    )
    assert result['teleport'].startswith('success')
    assert result['ag'].startswith('success')
    assert result['error'] is None
    # Teleport items only — never a premium-currency fallback exists to call.
    teleport_calls = [c for c in connection.calls if c[0] == 'send_teleport_mainbase']
    assert teleport_calls and all(c[3] is True for c in teleport_calls)


def test_unknown_ag_fails_without_teleporting():
    connection = make_connection()
    connection.group_armies = {}  # AG_ID not in the alliance's AG list
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    assert 'not in this account' in result['ag']
    assert result['teleport'] == 'skipped: AG validation failed'
    assert not any(c[0] == 'send_teleport_mainbase' for c in connection.calls)


def test_group_type_mismatch_is_rejected():
    connection = make_connection()
    connection.group_armies[AG_ID]['group_type'] = GROUP_ARMY_NAVY
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    assert 'AG type is' in result['ag']
    assert not any(c[0] == 'send_teleport_mainbase' for c in connection.calls)


def test_full_ag_is_rejected():
    connection = make_connection()
    connection.group_armies[AG_ID]['max_num'] = 2
    connection.group_armies[AG_ID]['army_count'] = 2
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    assert 'already full' in result['ag']


def test_invalid_army_slot_for_group_type_raises_and_is_reported():
    connection = make_connection()
    result = deploy_one_account(
        # 2001 is a navy slot, requested against a land AG.
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[2001], group_type=GROUP_ARMY_LAND,
    )
    assert 'do not belong to this AG type' in result['ag']
    assert not any(c[0] == 'send_teleport_mainbase' for c in connection.calls)


def test_already_joined_slots_report_success_without_rejoining():
    connection = make_connection()
    connection.armies[1]['group_unique_id'] = AG_ID  # already in this exact AG
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    assert result['ag'] == f'success: all requested slots already in AG {AG_ID}'
    assert not any(c[0] == 'send_join_group_army' for c in connection.calls)


def test_placement_retries_on_a_retryable_server_error_then_succeeds():
    connection = make_connection()
    connection.teleport_replies = ['error', {'position': {'x': 5, 'y': 5}, 'is_car': False}]
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    teleport_calls = [c for c in connection.calls if c[0] == 'send_teleport_mainbase']
    assert len(teleport_calls) == 2  # first rejected, second accepted
    assert result['teleport'].startswith('success')


def test_disconnect_mid_flow_is_reported_not_crashed():
    connection = make_connection()

    def request_then_disconnect(uid):
        # No reply ever arrives (serial never advances, no position gets
        # cached) — the connection just drops, which _wait_for_reply must
        # notice via is_active.
        connection.calls.append(('request_user_position', uid))
        connection.user_positions.pop(uid, None)
        connection.is_active = False

    connection.request_user_position = request_then_disconnect

    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
    )
    assert result['teleport'].startswith('failed:')
    assert result['error'] is None  # per-account failure text lives in teleport/ag, not error


def test_cancellation_before_start_never_sends_any_request():
    connection = make_connection()
    cancel_event = threading.Event()
    cancel_event.set()
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
        cancel_event=cancel_event,
    )
    assert result['error'] == 'cancelled before this account started'
    assert connection.calls == []


def test_position_index_advances_across_multiple_placement_attempts():
    connection = make_connection()
    connection.teleport_replies = ['error', {'position': {'x': 5, 'y': 5}, 'is_car': False}]
    result = deploy_one_account(
        connection, ag_id=AG_ID, player_uid=PLAYER_UID, army_ids=[1], group_type=GROUP_ARMY_LAND,
        position_index=0,
    )
    assert result['position_index'] > 0
