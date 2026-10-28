"""Synthetic sockets and explicit lower-level action-policy test injection.

Per the stage-1/2 instructions: mock the socket, not the architecture.
Everything from WarpathConnection.connect() up through AccountManager is the
real code under test; only the OS TCP socket is replaced, with a fake that
speaks the exact same framing real Warpath does (see build_login_reply_frame
/ build_err_info_frame), so the real recv_packet()/observe_account_data()
parsing path is genuinely exercised.
"""

from __future__ import annotations

import socket as socket_module
import struct
import threading
from collections import deque
from typing import List, Optional

from app.core.warpath.protobuf import down_pb2


def build_login_reply_frame(
    uid: int, name: str = 'TestPlayer', camp_type: int = 1,
    production_building_ids: Optional[List[int]] = None,
    production_lines: Optional[List[dict]] = None,
    officer_tasks: Optional[List[dict]] = None,
) -> bytes:
    """A minimal, valid down_msg the real client accepts as a successful
    login: down_op_code == 3 with login_reply.playerdata_reply populated.
    Server->client frames are NOT AES encrypted in this protocol (only
    client->server is) — just length-prefixed, optionally zlib-compressed
    protobuf. Flag byte 0 here means "not compressed".

    production_building_ids populates player.building_produce, which is
    what request_collect_all() actually iterates over — omitting it (the
    default) reproduces a freshly-connected account that doesn't know about
    any production buildings yet.

    officer_tasks populates player.client_officer_task_data — each dict
    needs 'task_id' (a STRING on the real wire, e.g. 'f1' — never numeric;
    this is exactly the field a live account's real reply broke the
    Active Actions endpoint on when it was typed as int) and 'status'.

    production_lines populates player.building_produce with real
    produce_line/produce_cell data (bld_id, line_id, item_type_id,
    quantity, start_time, end_time) — the /production and Active Actions
    production entries both read this same structure."""
    down = down_pb2.down_msg()
    down.down_op_code = 3
    playerdata = down.login_reply.playerdata_reply
    playerdata.uid = uid
    playerdata.camp_type = camp_type
    playerdata.name_card.name = name
    playerdata.bag_data.SetInParent()  # proto2 `required` field on playerdata_reply
    for task in officer_tasks or ():
        entry = playerdata.client_officer_task_data.client_officer_task_list.add()
        entry.task_id = task['task_id']
        entry.status = task.get('status', 0)
        if 'start_time' in task:
            entry.time_unit.start_time = task['start_time']
        if 'end_time' in task:
            entry.time_unit.end_time = task['end_time']
    for bld_id in production_building_ids or ():
        playerdata.building_produce.add().bld_id = bld_id
    buildings_by_id: dict[int, object] = {}
    for pl in production_lines or ():
        group = buildings_by_id.get(pl['bld_id'])
        if group is None:
            group = playerdata.building_produce.add()
            group.bld_id = pl['bld_id']
            buildings_by_id[pl['bld_id']] = group
        line = group.produce_line.add()
        line.line_id = pl['line_id']
        cell = line.produce_cell.add()
        if 'item_type_id' in pl:
            cell.item_type_id = pl['item_type_id']
        if 'quantity' in pl:
            cell.item_produce_num = pl['quantity']
        cell.time_unit.SetInParent()  # proto2 `required` field on produce_cell
        if 'start_time' in pl:
            cell.time_unit.start_time = pl['start_time']
        if 'end_time' in pl:
            cell.time_unit.end_time = pl['end_time']
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_vehicle_list_reply_frame(vehicles: List[dict]) -> bytes:
    """A mine_reply.get_vehicle_list_reply down_msg — each dict in
    `vehicles` needs at least {'id', 'state'}; 'mine_id'/'is_lock' default
    to 0/False if omitted. 'x'/'y'/'start_time'/'end_time'/'max_gather_num'
    (info submessage) and 'target_x'/'target_y' (move_target_pos) are
    optional — confirmed present on the real reply via a live protocol
    capture on 2026-09-15. Used by recall-all tests to exercise the real
    request_vehicle_list -> _wait_for_reply -> farm_vehicles round trip,
    and by Active Actions tests to prove the full wire path for real
    position/timing data."""
    down = down_pb2.down_msg()
    reply = down.mine_reply.get_vehicle_list_reply
    for v in vehicles:
        wrapper = reply.mine_vehicle.add()
        wrapper.mine_vehicle.id = v['id']
        wrapper.mine_vehicle.state = v['state']
        wrapper.mine_vehicle.mine_id = v.get('mine_id', 0)
        wrapper.mine_vehicle.is_lock = v.get('is_lock', False)
        if any(k in v for k in ('x', 'y', 'start_time', 'end_time', 'max_gather_num')):
            info = wrapper.mine_vehicle.info
            info.x = v.get('x', 0)
            info.y = v.get('y', 0)
            info.start_time = v.get('start_time', 0)
            info.end_time = v.get('end_time', 0)
            info.max_gather_num = v.get('max_gather_num', 0)
        if 'target_x' in v or 'target_y' in v:
            wrapper.mine_vehicle.move_target_pos.x = v.get('target_x', 0)
            wrapper.mine_vehicle.move_target_pos.y = v.get('target_y', 0)
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_user_position_reply_frame(player_id: int, *, map_id: int = 5, x: int = 100, y: int = 100) -> bytes:
    """guild_reply.get_user_pos_reply — what request_user_position() waits
    for (user_position_reply_serial)."""
    down = down_pb2.down_msg()
    reply = down.guild_reply.get_user_pos_reply
    reply.player_id = player_id
    reply.map_id = map_id
    reply.pos.x = x
    reply.pos.y = y
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_group_army_list_reply_frame(groups: Optional[List[dict]] = None) -> bytes:
    """group_army_reply.get_guild_group_army_list_reply — what
    request_group_army_list() waits for (group_list_reply_serial). An
    empty/omitted `groups` list reproduces the "AG not found" case."""
    down = down_pb2.down_msg()
    reply = down.group_army_reply.get_guild_group_army_list_reply
    reply.SetInParent()  # mark present even with zero entries — see build_login_reply_frame's note on proto2 presence
    for g in groups or ():
        entry = reply.group_army_info_list.add()
        entry.unique_id = g['unique_id']
        entry.group_type = g.get('group_type', 0)
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_gain_all_produce_reply_frame(bld_id: int, gained_item_count: int = 0) -> bytes:
    """bld_produce_reply.gain_all_produce_reply — what request_collect_all()
    waits for per building (gain_all_produce_reply_serial). Shape confirmed
    via a live protocol capture on 2026-09-15."""
    down = down_pb2.down_msg()
    reply = down.bld_produce_reply.gain_all_produce_reply
    reply.building_produce.bld_id = bld_id
    for _ in range(gained_item_count):
        item = reply.gain_list.add()
        item.type_id = 'steel'
        item.num = 1
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_map_search_reply_frame(result: int = 0, mine_id: int = 0, mine_type: int = 0, x: int = 0, y: int = 0) -> bytes:
    """map_search_reply.search_finished — the REAL reply to
    send_farm_search()'s find_and_refresh_req (map_search_reply_serial).
    Not find_mine_reply, a same-shaped but unused sibling field on down_msg
    — confirmed via a live protocol capture on 2026-09-15 that find_mine_reply
    never arrives while map_search_reply does. mine_id == 0 reproduces "no
    matching mine found"."""
    down = down_pb2.down_msg()
    reply = down.map_search_reply.search_finished
    reply.result = result
    if mine_id:
        reply.mine.id = mine_id
        reply.mine.type = mine_type
        reply.mine.pos.x = x
        reply.mine.pos.y = y
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_try_gather_mine_reply_frame(vehicle_id: int, state: int = 3, mine_id: int = 0) -> bytes:
    """mine_reply.try_gather_mine_reply — the REAL reply to
    gather_map_mine_req (send_farm_vehicle()), waited on via
    gather_mine_reply_serial. Not start_gather_mine_reply, a same-shaped but
    unused sibling field — confirmed via a live protocol capture on
    2026-09-15 dispatching a real vehicle to a real mine. mine_vehicle is a
    repeated client_mine_vehicle wrapper list, same double-nesting as
    get_vehicle_list_reply — see build_vehicle_list_reply_frame."""
    down = down_pb2.down_msg()
    reply = down.mine_reply.try_gather_mine_reply
    wrapper = reply.mine_vehicle.add()
    wrapper.mine_vehicle.id = vehicle_id
    wrapper.mine_vehicle.state = state
    wrapper.mine_vehicle.mine_id = mine_id
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_gather_mine_return_reply_frame(vehicle_id: int, state: int = 1) -> bytes:
    """mine_reply.gather_mine_return_reply — what send_recall_vehicle()
    waits for (vehicle_return_reply_serial). Same repeated wrapper shape as
    build_start_gather_mine_reply_frame."""
    down = down_pb2.down_msg()
    reply = down.mine_reply.gather_mine_return_reply
    wrapper = reply.mine_vehicle.add()
    wrapper.mine_vehicle.id = vehicle_id
    wrapper.mine_vehicle.state = state
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_army_list_reply_frame(armies: List[dict]) -> bytes:
    """group_army_reply.user_army_group_data_reply.army_list — what
    _update_army_snapshot() consumes into connection.armies, and what
    join_army_group()/leave_army_group() wait for (army_update_reply_serial)
    to confirm a join/leave actually changed group_unique_id. Each dict
    needs 'army_id'; 'equipment_id'/'group_unique_id' default to 0."""
    down = down_pb2.down_msg()
    reply = down.group_army_reply.user_army_group_data_reply
    for a in armies:
        entry = reply.army_list.add()
        entry.army_id = a['army_id']
        entry.equipment_id = a.get('equipment_id', 0)
        entry.has_num = a.get('has_num', 0)
        entry.master_obj_id = a.get('master_obj_id', 0)
        group_unique_id = a.get('group_unique_id', 0)
        if group_unique_id:
            entry.group_data.unique_id = group_unique_id
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


def build_err_info_frame(code: int = 401, info: str = 'invalid token') -> bytes:
    """A server rejection — what a real auth/token failure looks like on
    the wire. WarpathConnection.run() turns this into a WarpathLoginError
    during the authentication phase."""
    down = down_pb2.down_msg()
    down.down_op_code = 99
    down.err_info.code = code
    down.err_info.info = info
    body = down.SerializeToString()
    payload = bytes([0]) + body
    return struct.pack('>I', len(payload)) + payload


class FakeWarpathSocket:
    """Stands in for a real TCP socket to the Warpath game server: fed
    pre-built server frames, records what was sent, and never touches a
    real network interface."""

    def __init__(
        self,
        frames: Optional[List[bytes]] = None,
        *,
        fail_connect: bool = False,
        idle_reads_before_close: Optional[int] = None,
    ):
        self._buffer = bytearray()
        for frame in frames or ():
            self._buffer.extend(frame)
        self.sent: List[bytes] = []
        self.closed = False
        self.fail_connect = fail_connect
        self.idle_reads_before_close = idle_reads_before_close
        self._idle_reads = 0
        self._closed_by_peer = False
        self._lock = threading.Lock()

    def push_frame(self, frame: bytes) -> None:
        with self._lock:
            self._buffer.extend(frame)

    # -- socket.socket interface used by WarpathConnection -------------------
    def settimeout(self, timeout):
        pass

    def setsockopt(self, *args, **kwargs):
        pass

    def connect(self, address):
        if self.fail_connect:
            raise ConnectionRefusedError('fake connection refused')

    def sendall(self, data):
        with self._lock:
            self.sent.append(bytes(data))

    def recv(self, n):
        with self._lock:
            if self._buffer:
                chunk = bytes(self._buffer[:n])
                del self._buffer[:n]
                return chunk
            if self._closed_by_peer:
                return b''
            if self.idle_reads_before_close is not None:
                self._idle_reads += 1
                if self._idle_reads > self.idle_reads_before_close:
                    self._closed_by_peer = True
                    return b''
            raise socket_module.timeout('no data queued')

    def shutdown(self, *args):
        pass

    def close(self):
        self.closed = True


class ScriptedSocketFactory:
    """Monkeypatched in place of socket.socket; hands out pre-built
    FakeWarpathSocket instances in order, one per real connect() attempt
    (i.e. one per WarpathConnection.connect() call, including reconnects)."""

    def __init__(self, sockets: List[FakeWarpathSocket]):
        self._sockets = deque(sockets)
        self.created: List[FakeWarpathSocket] = []

    def __call__(self, *args, **kwargs):
        if not self._sockets:
            raise AssertionError('ScriptedSocketFactory ran out of scripted sockets')
        sock = self._sockets.popleft()
        self.created.append(sock)
        return sock



def decode_request(packet):
    """Decode synthetic client traffic for deterministic response-on-send tests."""
    from app.core.warpath.protocol import aes_decrypt
    from app.core.warpath.protobuf import up_pb2
    plaintext = aes_decrypt(packet[4:])
    size = struct.unpack('<I', plaintext[:4])[0]
    request = up_pb2.up_msg()
    request.ParseFromString(plaintext[4:4 + size])
    return request


def with_sequence(frame, sequence):
    reply = down_pb2.down_msg()
    reply.ParseFromString(frame[5:])
    reply.msg_seq_id = sequence
    payload = b'\x00' + reply.SerializeToString()
    return struct.pack('>I', len(payload)) + payload


def respond_on_send(sock, callback):
    original = sock.sendall

    def send(packet):
        original(packet)
        request = decode_request(packet)
        for frame in callback(request) or ():
            sock.push_frame(with_sequence(frame, request.msg_seq_id))

    sock.sendall = send


class SyntheticPilotPolicy:
    """Explicit engine-test injection, never selectable through app/env config.

    Existing protocol/API fixtures exercise actions below the production gate.
    Phase 6 security tests use the real PilotActivation and default manager.
    """
    requires_fresh_connection = False
    observation_only = False

    def require_observation(self, account_id):
        pass

    def require_actions(self):
        pass

    def check_http(self, account_id, action):
        pass

    def automatic_enabled(self, account_id):
        return True

    def revoke(self, account_id):
        pass

    def revoke_all(self):
        pass

    def transmission(self, account_id, message=None):
        from contextlib import nullcontext
        return nullcontext()


def synthetic_account_manager(**kwargs):
    from app.core.account_manager import AccountManager
    return AccountManager(pilot_policy=SyntheticPilotPolicy(), **kwargs)
