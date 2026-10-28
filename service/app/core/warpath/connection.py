"""Low-level Warpath game-server connection.

This is the original WarpathConnection from warpath_bot.py, moved as-is
except for one deliberate change: it now takes a WarpathCredentials object
at construction and reads `self.credentials.*` everywhere it used to read
module-level globals (WARPATH_APP_UID, SERVER_IP, WARPATH_PLATFORM, ...).
The protobuf encoding, AES framing, TCP packet format, heartbeat behavior,
and inbound-message decoding are unchanged.

Every other piece of state here (account_snapshot, farm_vehicles,
known_map_objects, skin_data, profile_cache, the three locks, the socket
itself) was already an instance attribute in the original code — that part
of the design was already multi-instance-safe. This file just finishes the
job for the credential/session-identity half.
"""

from contextlib import nullcontext
from ..pilot_activation import PilotBlocked

import base64
import json
import os
import socket
import struct
import threading
import time
import zlib

from google.protobuf.json_format import MessageToDict

from .credentials import WarpathCredentials, redact_secrets
from .protobuf import down_pb2, up_pb2
from .protocol import aes_encrypt_zero_padded
from .reply_actions import ReplyActions


class WarpathLoginError(ConnectionError):
    """Raised when TCP succeeds but the game server rejects authentication."""


class WarpathConnection:
    """Low-level game-server connection for exactly one account, run by one
    background thread. Construct one per account; never share an instance
    or reuse it for a different WarpathCredentials."""

    def __init__(self, credentials: WarpathCredentials):
        self.credentials = credentials
        self.sock = None
        self.socket_connected = False
        self.authenticated = False
        self.connecting = False
        self.running = False
        self.stop_requested = False
        self.seq_id = 0
        self.hb_cnt = 0
        self.hb_delay = 50
        self.timeout_cnt = 20
        self.timeout_length = 59
        self.hb_down_delay = 0
        self.last_heartbeat_reply = None
        self.session_started = None
        self.auth_required = False
        self.last_error = None
        self._loop = None
        self._send_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._debug_lock = threading.RLock()
        self.debug_capture_until = 0.0
        self.debug_log_path = None
        self.debug_message_count = 0
        self.debug_console = False
        # Conquest Guard: opt-in automation, bound to the UID that enabled
        # it (armed_uid) so a later connect to a DIFFERENT account can never
        # inherit a guard armed for someone else — this lives on the
        # connection instance (one per account) rather than any shared
        # state, which is what "account-specific, never leaks" means here.
        # NOT reset by reset_account_data(): enabling the guard is a
        # deliberate standing choice that should survive a transient
        # reconnect, unlike the per-connection observation caches below.
        self.conquest_guard_enabled = False
        self.conquest_guard_armed_uid = 0
        self.conquest_guard_in_progress = False
        self.conquest_guard_last_request_at = 0.0
        self.conquest_guard_last_attack = None
        self.conquest_guard_last_result = None
        self.conquest_guard_attempts = 0
        self.reset_account_data()

    @property
    def account_id(self):
        return self.credentials.account_id

    @property
    def connected(self):
        """Compatibility alias: connected now means fully authenticated."""
        return self.authenticated

    @property
    def is_active(self):
        return self.connecting or self.socket_connected or self.authenticated

    @property
    def connection_state(self):
        if self.authenticated:
            return 'authenticated'
        if self.socket_connected:
            return 'authenticating'
        if self.connecting:
            return 'connecting'
        return 'disconnected'

    def configuration_errors(self):
        return self.credentials.validation_errors()

    def safe_error_message(self, error):
        return redact_secrets(error, self.credentials)

    def reset_account_data(self):
        if hasattr(self, 'reply_actions'):
            self.reply_actions.close()
        self.reply_actions = ReplyActions(self)
        self.account_snapshot = {}
        self.production_building_ids = set()
        self.production_lines = {}
        self.tech_state = {}
        self.known_map_objects = {}
        self.farm_vehicles = []
        self.scout_planes = []
        self.officer_tasks = []
        self.officer_roster = {}
        self.roles = []
        self.current_map_id = 0
        self.self_mainbase_object_ids = set()
        # Skin collection data
        self.skin_data = {}
        # Other player profile cache: uid -> profile dict
        self.profile_cache = {}
        # Full army records (army_id -> {equipment_id, reserves,
        # master_obj_id, group_unique_id}) and the Army Group list.
        self.armies = {}
        self.group_armies = {}
        self.user_positions = {}
        # The league-village position reply contains only x/y, not the UID
        # that was requested, so exact base lookups are serialized and
        # paired with this pending UID.
        self.mainbase_positions = {}
        self.pending_mainbase_position_uid = 0
        self.last_mainbase_position = None
        self.server_error_serial = 0
        self.last_server_error = None
        self.group_list_reply_serial = 0
        self.army_update_reply_serial = 0
        self.vehicle_list_reply_serial = 0
        self.map_scan_reply_serial = 0
        self.user_position_reply_serial = 0
        self.mainbase_position_reply_serial = 0
        self.teleport_reply_serial = 0
        self.last_teleport_reply = None
        self.base_move_reply_serial = 0
        self.last_base_move_reply = None
        # Per-action reply tracking for collect/farm/recall/scout — added so
        # these endpoints can wait for the real server reply instead of
        # reporting "requested" the moment the packet is sent, which gave no
        # signal on whether the action actually did anything (confirmed via
        # a live protocol capture on 2026-09-15: collect's gain_all_produce
        # replies came back fine, they just weren't being waited on).
        self.gain_all_produce_reply_serial = 0
        self.last_gain_all_produce_reply = None
        self.map_search_reply_serial = 0
        self.last_map_search_reply = None
        self.gather_mine_reply_serial = 0
        self.last_gather_mine_reply = None
        self.vehicle_return_reply_serial = 0
        self.last_vehicle_return_reply = None
        self.plane_explore_reply_serial = 0
        self.last_plane_explore_reply = None
        self.conquest_exit_reply_serial = 0
        # A fresh connection has no exit request in flight, even if the
        # guard itself (armed_uid, enabled) is a standing choice — see
        # __init__'s comment for why those two live outside this reset.
        self.conquest_guard_in_progress = False

    # -- Socket layer -------------------------------------------------------
    def _pilot_transmission(self, message=None):
        policy = getattr(self, 'pilot_policy', None)
        return policy.transmission(self.account_id, message) if policy is not None else nullcontext()

    def automatic_actions_enabled(self):
        policy = getattr(self, 'pilot_policy', None)
        return policy is None or policy.automatic_enabled(self.account_id)

    def connect(self):
        with self._pilot_transmission():
            self._connect_socket()

    def _connect_socket(self):
        server_ip = self.credentials.server_ip
        server_port = self.credentials.server_port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f'[{self.credentials.account_id}] Connecting to {server_ip}:{server_port}...')
        try:
            sock.connect((server_ip, server_port))
        except Exception:
            sock.close()
            raise
        with self._state_lock:
            self.sock = sock
            self.socket_connected = True
            self.session_started = time.time()
        print(f'[{self.credentials.account_id}] TCP connection established; authenticating...')

    def close(self):
        policy = getattr(self, 'pilot_policy', None)
        if policy is not None:
            policy.revoke(self.account_id)
        self.reply_actions.close()
        with self._state_lock:
            sock = self.sock
            self.sock = None
            self.socket_connected = False
            self.authenticated = False
            self.connecting = False
            self.running = False
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

    def disconnect(self):
        self.stop_requested = True
        self.close()

    def _recv_exact(self, n):
        data = b''
        while len(data) < n:
            try:
                sock = self.sock
                if sock is None:
                    return None
                chunk = sock.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                if data:
                    continue
                raise
        return data

    def recv_packet(self):
        length_data = self._recv_exact(4)
        if not length_data:
            return None, None
        pkt_len = struct.unpack('>I', length_data)[0]
        if pkt_len < 1 or pkt_len > 2 * 1024 * 1024:
            raise ConnectionError(f'invalid server packet length: {pkt_len}')
        payload = self._recv_exact(pkt_len)
        if not payload:
            return None, None
        flag = payload[0]
        data = payload[1:]
        if flag > 0:
            try:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
            except zlib.error as exc:
                raise ConnectionError('server sent invalid compressed data') from exc
            flag = 0
        return flag, data

    def send_raw(self, data):
        if getattr(self, 'pilot_policy', None) is not None:
            raise PilotBlocked('raw sends are unavailable in the pilot')
        with self._send_lock:
            sock = self.sock
            if sock is None or not self.socket_connected:
                raise ConnectionError('socket is not connected')
            sock.sendall(data)

    def send_message(self, proto_data, *, before_send=None):
        if isinstance(proto_data, up_pb2.up_msg):
            up = proto_data
        else:
            up = up_pb2.up_msg()
            up.ParseFromString(proto_data)

        with self._send_lock, self._pilot_transmission(up):
            sock = self.sock
            if sock is None or not self.socket_connected:
                raise ConnectionError('socket is not connected')
            self.seq_id = (self.seq_id % 0xFFFFFFFF) + 1
            up.msg_seq_id = self.seq_id
            serialized = up.SerializeToString()
            data = struct.pack('<I', len(serialized)) + serialized
            encrypted = aes_encrypt_zero_padded(data)
            if before_send is not None:
                before_send(self.seq_id)
            sock.sendall(struct.pack('>I', len(encrypted)) + encrypted)
            return self.seq_id

    def send_keepalive(self):
        self.hb_cnt += 1
        up = up_pb2.up_msg()
        up.heartbeat.hb_cnt = self.hb_cnt
        up.heartbeat.hb_delay = self.hb_delay
        up.heartbeat.timeout_cnt = self.timeout_cnt
        up.heartbeat.timeout_length = self.timeout_length
        up.heartbeat.timestamp = int(time.time() * 1000)
        up.heartbeat.hb_down_delay = self.hb_down_delay
        self.send_message(up)

    # -- Login --------------------------------------------------------------
    def build_login_message(self):
        creds = self.credentials
        up = up_pb2.up_msg()
        login = up.sdk_login
        login.plat = creds.platform
        login.sdk_session_key = creds.app_token
        common = login.oss_common
        common.open_id = creds.app_uid
        common.game_id = creds.game_id
        common.pack_name = creds.pack_name
        common.channel_id = creds.channel_id
        common.idfa = creds.device_id
        common.android_id = ''
        common.google_aid = ''
        common.device_model = creds.device_model
        common.app_version = creds.app_version
        common.os_type = creds.os_type
        common.os_version = creds.os_version
        common.os_lang = creds.os_language
        common.pack_lang = creds.pack_language
        common.timezone = creds.timezone
        common.app_id = creds.app_id
        common.net_route_type = creds.net_route_type
        common.start_login_time = int(time.time() * 1000)
        common.package_version = creds.package_version
        if creds.env_id:
            common.env_id = creds.env_id
        common.device_id = creds.device_id
        if creds.net_route_info:
            common.net_route_info = creds.net_route_info
        if creds.client_ip:
            common.client_ip = creds.client_ip
        return up.SerializeToString()

    def send_login(self):
        self.send_message(self.build_login_message())
        print(f'[{self.credentials.account_id}] Login sent')

    # -- Server wrapper decode ----------------------------------------------
    def parse_server_wrapper(self, data):
        from .protocol import parse_pb

        msg = parse_pb(data, max_depth=2)
        op_code = None
        inner_data = None
        for fn, entries in msg.items():
            for wt, val in entries:
                if fn == 2 and wt == 'v':
                    op_code = val
                elif wt == 'd' and fn != 2:
                    inner_data = val
        return op_code, inner_data, msg

    # -- Bounded protocol diagnostics --------------------------------------
    def start_protocol_debug(self, duration=10, console=False):
        duration = max(1, min(int(duration), 60))
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        filename = f"warpath_protocol_{self.credentials.account_id}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        path = os.path.join(logs_dir, filename)
        with self._debug_lock:
            if self.debug_capture_until > time.monotonic():
                raise RuntimeError('a protocol capture is already running')
            self.debug_capture_until = time.monotonic() + duration
            self.debug_log_path = path
            self.debug_message_count = 0
            self.debug_console = bool(console)
            header = {
                'event': 'capture_started',
                'timestamp': time.time(),
                'duration_seconds': duration,
                'console_mirror': self.debug_console,
            }
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(json.dumps(header, separators=(',', ':')) + '\n')
        return path

    def stop_protocol_debug(self):
        with self._debug_lock:
            path = self.debug_log_path
            count = self.debug_message_count
            was_active = self.debug_capture_until > 0
            self.debug_capture_until = 0.0
            self.debug_console = False
            if was_active and path:
                footer = {
                    'event': 'capture_stopped',
                    'timestamp': time.time(),
                    'message_count': count,
                }
                with open(path, 'a', encoding='utf-8') as handle:
                    handle.write(json.dumps(footer, separators=(',', ':')) + '\n')
            return path, count

    @staticmethod
    def _redact_protocol_secrets(value):
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                normalized = key.lower()
                if any(word in normalized for word in ('token', 'password', 'session_key')):
                    redacted[key] = '<redacted>'
                else:
                    redacted[key] = WarpathConnection._redact_protocol_secrets(item)
            return redacted
        if isinstance(value, list):
            return [WarpathConnection._redact_protocol_secrets(item) for item in value]
        return value

    def _record_protocol_debug(self, data, down=None, parse_error=None):
        with self._debug_lock:
            if self.debug_capture_until <= 0:
                return
            if time.monotonic() > self.debug_capture_until:
                self.debug_capture_until = 0.0
                self.debug_console = False
                return
            path = self.debug_log_path
            if not path:
                return

            record = {
                'event': 'down_message',
                'timestamp': time.time(),
                'wire_size': len(data),
            }
            if down is not None:
                op_code = int(down.down_op_code)
                try:
                    op_name = down_pb2.msg_down_op_code.Name(op_code)
                except (AttributeError, ValueError):
                    op_name = 'unknown'
                record['op_code'] = op_code
                record['op_name'] = op_name
                record['top_level_fields'] = [
                    field.name for field, _ in down.ListFields()
                ]
                try:
                    decoded = MessageToDict(
                        down,
                        preserving_proto_field_name=True,
                        use_integers_for_enums=True,
                    )
                    record['message'] = self._redact_protocol_secrets(decoded)
                except Exception as error:
                    record['conversion_error'] = self.safe_error_message(error)
                    record['raw_base64'] = base64.b64encode(data).decode('ascii')
            else:
                record['parse_error'] = parse_error or 'protobuf parsing returned no message'
                record['raw_base64'] = base64.b64encode(data).decode('ascii')

            line = json.dumps(record, ensure_ascii=False, separators=(',', ':'), default=str)
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(line + '\n')
            self.debug_message_count += 1
            if self.debug_console:
                print(f'[PROTOCOL DEBUG {self.credentials.account_id}] {line}')

    def request_debug_snapshots(self):
        """Send the safe read-only requests supported by this client. Also
        backs the dashboard's Refresh button (see api/intel.py)."""
        requests = [
            ('vehicle_list', self.request_vehicle_list),
            ('power_snapshot', self.request_power_snapshot),
            ('skin_data', self.request_user_skin_data),
            ('group_armies', self.request_group_army_list),
        ]
        profile_uid = int(self.account_snapshot.get('uid') or self.credentials.profile_uid or 0)
        if profile_uid:
            requests.append(
                ('own_profile', lambda: self.request_player_profile(profile_uid))
            )
        policy = getattr(self, 'pilot_policy', None)
        if self.current_map_id and not (policy and policy.observation_only):
            requests.append(('map_view', self.send_map_view_request))

        sent = []
        failures = []
        for name, request in requests:
            try:
                request()
                sent.append(name)
            except Exception as error:
                failures.append(f'{name}: {self.safe_error_message(error)}')
        return sent, failures

    # -- Observation: decode server messages into account_snapshot -----------
    def observe_account_data(self, data):
        """Decode account updates without letting one schema mismatch kill TCP."""
        down = None
        parse_error = None
        try:
            down = self._observe_account_data_unchecked(data)
        except Exception as exc:
            parse_error = self.safe_error_message(exc)
            self.account_snapshot['last_parse_error'] = parse_error
            print(f'  [OBSERVE {self.credentials.account_id}] non-fatal message error: {parse_error}')
            try:
                down = down_pb2.down_msg()
                down.ParseFromString(data)
            except Exception as fallback_error:
                parse_error = (
                    f'{parse_error}; fallback parse failed: '
                    f'{self.safe_error_message(fallback_error)}'
                )
                down = None
        self._record_protocol_debug(data, down, parse_error)
        return down

    def _observe_account_data_unchecked(self, data):
        try:
            down = down_pb2.down_msg()
            down.ParseFromString(data)
        except Exception:
            return None

        if down.HasField('err_info'):
            self.reply_actions.reject(int(down.msg_seq_id))
            info = down.err_info.info
            code = down.err_info.code
            error_entry = {'code': int(code), 'info': info}
            self.account_snapshot['last_server_error'] = error_entry
            self.last_server_error = error_entry
            self.server_error_serial += 1
            if self.conquest_guard_in_progress:
                self.conquest_guard_in_progress = False
                self.conquest_guard_last_result = {
                    'status': 'failed',
                    'detail': info or f'server error #{int(code)}',
                    'at': time.time(),
                }
            if any(w in info.lower() for w in ('token', 'session', 'login', 'auth')):
                self.auth_required = True
            return down

        if down.HasField('login_reply'):
            self._observe_playerdata(down.login_reply.playerdata_reply)
            if down.login_reply.HasField('general_data_reply'):
                self._observe_general_data(down.login_reply.general_data_reply)
            if down.login_reply.HasField('user_self_map_objects'):
                for obj in down.login_reply.user_self_map_objects.user_objects:
                    self._track_map_object(obj)
            if down.login_reply.playerdata_reply.HasField('around_data_aggr'):
                for ad in down.login_reply.playerdata_reply.around_data_aggr.around_data_list:
                    for obj in ad.object_list:
                        self._track_map_object(obj)

        if down.HasField('reconnect_reply') and down.reconnect_reply.HasField('playerdata_reply'):
            self._observe_playerdata(down.reconnect_reply.playerdata_reply)
            if down.reconnect_reply.HasField('general_data_reply'):
                self._observe_general_data(down.reconnect_reply.general_data_reply)

        if down.HasField('general_data_reply'):
            self._observe_general_data(down.general_data_reply)

        if down.HasField('group_army_reply'):
            reply = down.group_army_reply
            if reply.HasField('get_guild_group_army_list_reply'):
                groups = {}
                for group in reply.get_guild_group_army_list_reply.group_army_info_list:
                    unique_id = int(group.unique_id) if group.HasField('unique_id') else 0
                    if not unique_id:
                        continue
                    creator_uid = 0
                    creator_name = ''
                    if group.HasField('creator_info') and group.creator_info.HasField('ubi_info'):
                        creator_uid = int(group.creator_info.ubi_info.uid)
                        creator_name = group.creator_info.ubi_info.name
                    groups[unique_id] = {
                        'unique_id': unique_id,
                        'group_type': int(group.group_type) if group.HasField('group_type') else 0,
                        'map_id': int(group.map_id) if group.HasField('map_id') else 0,
                        'city_id': int(group.city_id) if group.HasField('city_id') else 0,
                        'creator_uid': creator_uid,
                        'creator_name': creator_name,
                        'announcement': group.announcement if group.HasField('announcement') else '',
                        'state': int(group.state) if group.HasField('state') else 0,
                        'army_count': sum(len(user.army_info) for user in group.user_army_data),
                        'max_num': int(group.max_num) if group.HasField('max_num') else 0,
                    }
                self.group_armies = groups
                self.group_list_reply_serial += 1
            if reply.HasField('user_army_group_data_reply'):
                self._update_army_snapshot(reply.user_army_group_data_reply.army_list, replace=False)
                self.army_update_reply_serial += 1

        if (
            down.HasField('league_village_reply')
            and down.league_village_reply.HasField('msg_get_user_mainbase_pos_reply')
        ):
            reply = down.league_village_reply.msg_get_user_mainbase_pos_reply
            requested_uid = int(self.pending_mainbase_position_uid or 0)
            position = None
            if reply.HasField('int_pos'):
                position = {
                    'player_id': requested_uid,
                    'x': int(reply.int_pos.x),
                    'y': int(reply.int_pos.y),
                    'received_at': time.monotonic(),
                }
                if requested_uid:
                    self.mainbase_positions[requested_uid] = position
            self.last_mainbase_position = position
            self.pending_mainbase_position_uid = 0
            self.mainbase_position_reply_serial += 1

        if down.HasField('guild_reply') and down.guild_reply.HasField('get_user_pos_reply'):
            reply = down.guild_reply.get_user_pos_reply
            player_id = int(reply.player_id) if reply.HasField('player_id') else 0
            position = {
                'player_id': player_id,
                'map_id': int(reply.map_id) if reply.HasField('map_id') else 0,
                'x': int(reply.pos.x) if reply.HasField('pos') else 0,
                'y': int(reply.pos.y) if reply.HasField('pos') else 0,
                'received_at': time.monotonic(),
            }
            if player_id:
                self.user_positions[player_id] = position
            self.user_position_reply_serial += 1

        if down.HasField('msg_base_reply') and down.msg_base_reply.HasField('teleport_mainbase_reply'):
            reply = down.msg_base_reply.teleport_mainbase_reply
            position = None
            if reply.HasField('base_data'):
                self._observe_base_data(reply.base_data)
                if reply.base_data.HasField('base_coord'):
                    position = {'x': int(reply.base_data.base_coord.x), 'y': int(reply.base_data.base_coord.y)}
            for obj in reply.objlists:
                self._track_map_object(obj)
            self.last_teleport_reply = {
                'position': position,
                'is_car': bool(self.account_snapshot.get('base_is_car', False)),
                'received_at': time.monotonic(),
            }
            self.teleport_reply_serial += 1

        if down.HasField('msg_base_reply') and down.msg_base_reply.HasField('move_base_reply'):
            reply = down.msg_base_reply.move_base_reply
            position = None
            if reply.HasField('base_data'):
                self._observe_base_data(reply.base_data)
                if reply.base_data.HasField('base_coord'):
                    position = {'x': int(reply.base_data.base_coord.x), 'y': int(reply.base_data.base_coord.y)}
            if reply.HasField('obj'):
                self._track_map_object(reply.obj)
            self.last_base_move_reply = {
                'position': position,
                'is_car': bool(self.account_snapshot.get('base_is_car', False)),
                'received_at': time.monotonic(),
            }
            self.base_move_reply_serial += 1

        if down.HasField('msg_base_reply') and down.msg_base_reply.HasField('transfer_city_reply'):
            reply = down.msg_base_reply.transfer_city_reply
            if reply.HasField('playerdata_reply'):
                self._observe_playerdata(reply.playerdata_reply)
            if reply.HasField('general_data_reply'):
                self._observe_general_data(reply.general_data_reply)
            if reply.HasField('base_data'):
                self._observe_base_data(reply.base_data)
            if reply.HasField('city_id'):
                self.account_snapshot['city_id'] = int(reply.city_id)
            if reply.HasField('map_id'):
                self.current_map_id = int(reply.map_id)
                self.account_snapshot['map_id'] = int(reply.map_id)
            for obj in reply.objlists:
                self._track_map_object(obj)
            self.conquest_exit_reply_serial += 1
            guard_exit_was_recent = bool(
                self.conquest_guard_last_request_at
                and time.monotonic() - self.conquest_guard_last_request_at < 30.0
            )
            if self.conquest_guard_in_progress or guard_exit_was_recent:
                self.conquest_guard_in_progress = False
                self.conquest_guard_last_result = {
                    'status': 'success',
                    'detail': 'left the Theater of Conquest',
                    'city_id': int(reply.city_id) if reply.HasField('city_id') else 0,
                    'map_id': int(reply.map_id) if reply.HasField('map_id') else 0,
                    'at': time.time(),
                }

        if down.HasField('map_reply') and down.map_reply.HasField('get_around_data_reply'):
            reply = down.map_reply.get_around_data_reply
            if reply.HasField('around_data_aggr'):
                for ad in reply.around_data_aggr.around_data_list:
                    for obj in ad.object_list:
                        self._track_map_object(obj)
            self.map_scan_reply_serial += 1

        if down.HasField('mine_reply'):
            mr = down.mine_reply
            if mr.HasField('get_vehicle_list_reply'):
                vehicles = []
                for client_vehicle in mr.get_vehicle_list_reply.mine_vehicle:
                    # client_mine_vehicle is a wrapper. The actual id/state
                    # fields live on its nested mine_vehicle message.
                    if not client_vehicle.HasField('mine_vehicle'):
                        continue
                    vehicle = client_vehicle.mine_vehicle
                    # info/move_target_pos confirmed present via a live
                    # protocol capture on 2026-09-15 (the same capture that
                    # confirmed the real farm dispatch reply) — start_time/
                    # end_time there are what Active Actions needs for a
                    # real ETA instead of a frontend-invented timer.
                    info = vehicle.info if vehicle.HasField('info') else None
                    target = vehicle.move_target_pos if vehicle.HasField('move_target_pos') else None
                    vehicles.append({
                        'id': int(vehicle.id) if vehicle.HasField('id') else 0,
                        'state': int(vehicle.state) if vehicle.HasField('state') else 0,
                        'mine_id': int(vehicle.mine_id) if vehicle.HasField('mine_id') else 0,
                        'map_vehicle_id': (
                            int(vehicle.map_vehicle_id)
                            if vehicle.HasField('map_vehicle_id') else 0
                        ),
                        'type_id': int(vehicle.type_id) if vehicle.HasField('type_id') else 0,
                        'map_id': int(vehicle.map_id) if vehicle.HasField('map_id') else 0,
                        'is_locked': (
                            bool(vehicle.is_lock) if vehicle.HasField('is_lock') else False
                        ),
                        'x': int(info.x) if info is not None and info.HasField('x') else 0,
                        'y': int(info.y) if info is not None and info.HasField('y') else 0,
                        'start_time': int(info.start_time) if info is not None and info.HasField('start_time') else 0,
                        'end_time': int(info.end_time) if info is not None and info.HasField('end_time') else 0,
                        'max_gather_num': (
                            int(info.max_gather_num) if info is not None and info.HasField('max_gather_num') else 0
                        ),
                        'target_x': int(target.x) if target is not None and target.HasField('x') else 0,
                        'target_y': int(target.y) if target is not None and target.HasField('y') else 0,
                    })
                if not down.HasField('err_info'):
                    idle_ids = {int(w.mine_vehicle.id) for w in mr.get_vehicle_list_reply.mine_vehicle
                                if w.HasField('mine_vehicle') and w.mine_vehicle.HasField('state')
                                and w.mine_vehicle.state == 1 and w.mine_vehicle.HasField('mine_id')
                                and w.mine_vehicle.mine_id == 0}
                    self.reply_actions.snapshot(int(down.msg_seq_id), vehicles, idle_ids)
                self.vehicle_list_reply_serial += 1

        if down.HasField('bld_produce_reply'):
            br = down.bld_produce_reply
            if br.HasField('gain_all_produce_reply'):
                gain = br.gain_all_produce_reply
                self.last_gain_all_produce_reply = {
                    'bld_id': int(gain.building_produce.bld_id) if gain.HasField('building_produce') else 0,
                    'gained_item_count': len(gain.gain_list),
                }
                self.gain_all_produce_reply_serial += 1
                if not down.HasField('err_info') and self.reply_actions.receive(
                        int(down.msg_seq_id), 'collect', self.last_gain_all_produce_reply):
                    self.account_snapshot['last_collection_at'] = time.time()
                    self.account_snapshot['last_collection_items'] = len(gain.gain_list)

        if down.HasField('map_search_reply') and down.map_search_reply.HasField('search_finished'):
            # This, not find_mine_reply (a same-shadowed but unused sibling
            # field), is the real reply to find_and_refresh_req — confirmed
            # via a live protocol capture on 2026-09-15: find_mine_reply
            # never arrived after 30+ seconds, while map_search_reply came
            # back within a couple seconds carrying the found mine.
            reply = down.map_search_reply.search_finished
            mine = reply.mine if reply.HasField('mine') else None
            self.last_map_search_reply = {
                'result': int(reply.result) if reply.HasField('result') else None,
                'mine_id': int(mine.id) if mine is not None and mine.HasField('id') else 0,
                'mine_type': int(mine.type) if mine is not None and mine.HasField('type') else 0,
                'x': int(mine.pos.x) if mine is not None and mine.HasField('pos') else 0,
                'y': int(mine.pos.y) if mine is not None and mine.HasField('pos') else 0,
            }
            self.map_search_reply_serial += 1
            if not down.HasField('err_info'):
                self.reply_actions.receive(int(down.msg_seq_id), 'search', self.last_map_search_reply)

        if down.HasField('mine_reply'):
            if down.mine_reply.HasField('try_gather_mine_reply'):
                # Not start_gather_mine_reply (a same-shaped but unused
                # sibling field) — confirmed via a live protocol capture on
                # 2026-09-15 sending a vehicle to a real mine: the server's
                # actual reply to gather_map_mine_req is try_gather_mine_reply,
                # and the vehicle really does start moving toward the mine
                # (move_target_pos matches the mine's position).
                reply = down.mine_reply.try_gather_mine_reply
                # mine_vehicle is a repeated client_mine_vehicle wrapper list
                # (same double-nesting as get_vehicle_list_reply above) —
                # take the first entry, matching the single vehicle a dispatch
                # request targets.
                wrapper = reply.mine_vehicle[0] if reply.mine_vehicle else None
                vehicle = wrapper.mine_vehicle if wrapper is not None and wrapper.HasField('mine_vehicle') else None
                self.last_gather_mine_reply = {
                    'vehicle_id': int(vehicle.id) if vehicle is not None and vehicle.HasField('id') else 0,
                    'state': int(vehicle.state) if vehicle is not None and vehicle.HasField('state') else 0,
                    'mine_id': int(vehicle.mine_id) if vehicle is not None and vehicle.HasField('mine_id') else 0,
                }
                self.gather_mine_reply_serial += 1
                vehicles = [self._vehicle_patch(w.mine_vehicle) for w in reply.mine_vehicle if w.HasField('mine_vehicle')]
                for vehicle in vehicles:
                    if not down.HasField('err_info'):
                        self.reply_actions.receive(int(down.msg_seq_id), 'gather', {
                            'vehicle_id': vehicle.get('id'), 'state': vehicle.get('state'),
                            'mine_id': vehicle.get('mine_id'), 'need_verify': bool(reply.need_verify),
                            'vehicle': vehicle,
                        })
            if down.mine_reply.HasField('gather_mine_return_reply'):
                reply = down.mine_reply.gather_mine_return_reply
                wrapper = reply.mine_vehicle[0] if reply.mine_vehicle else None
                vehicle = wrapper.mine_vehicle if wrapper is not None and wrapper.HasField('mine_vehicle') else None
                self.last_vehicle_return_reply = {
                    'vehicle_id': int(vehicle.id) if vehicle is not None and vehicle.HasField('id') else 0,
                    'state': int(vehicle.state) if vehicle is not None and vehicle.HasField('state') else 0,
                }
                self.vehicle_return_reply_serial += 1

        if (
            down.HasField('fog_reply')
            and down.fog_reply.HasField('plane_explore_fog_reply')
            and down.fog_reply.plane_explore_fog_reply.HasField('single_plane_info_reply')
        ):
            reply = down.fog_reply.plane_explore_fog_reply.single_plane_info_reply
            plane = reply.plane_info if reply.HasField('plane_info') else None
            self.last_plane_explore_reply = {
                'plane_id': int(plane.plane_id) if plane is not None and plane.HasField('plane_id') else 0,
                'plane_state': int(plane.plane_state) if plane is not None and plane.HasField('plane_state') else 0,
                'finished': bool(plane.finished) if plane is not None and plane.HasField('finished') else False,
            }
            self.plane_explore_reply_serial += 1

        # Skin collection reply (own skins with levels/progress)
        if down.HasField('common_skin_reply'):
            cr = down.common_skin_reply
            if cr.HasField('get_user_skin_reply'):
                reply = cr.get_user_skin_reply
                if reply.HasField('user_skin_data'):
                    sd = reply.user_skin_data
                    self.skin_data = {}
                    skin_fields = {
                        'base_car_skin': sd.base_car_skin,
                        'collect_car_list_skin': sd.collect_car_list_skin,
                        'collect_ship_list_skin': sd.collect_ship_list_skin,
                        'commander_dressup_skin': sd.commander_dressup_skin,
                        'radiant_base_skin': sd.radiant_base_skin,
                        'title_skin_list': sd.title_skin_list,
                    }
                    for label, skin_list in skin_fields.items():
                        if skin_list:
                            parsed = []
                            for s in skin_list:
                                entry = {
                                    'id': int(s.id) if s.HasField('id') else 0,
                                    'is_wearing': bool(s.is_wearing) if s.HasField('is_wearing') else False,
                                    'level': int(s.level) if s.HasField('level') else 0,
                                    'cumulative_progress': int(s.cumulative_progress) if s.HasField('cumulative_progress') else 0,
                                    'group_id': int(s.group_id) if s.HasField('group_id') else 0,
                                    'colour_id': int(s.colour_id) if s.HasField('colour_id') else 0,
                                }
                                parsed.append(entry)
                            self.skin_data[label] = parsed

        # Other player profile reply (skin_point, commander_skin, title_skin)
        if down.HasField('user_info_reply'):
            reply = down.user_info_reply
            if reply.HasField('user_personal_page_reply'):
                page = reply.user_personal_page_reply
                if page.HasField('page_data'):
                    pd = page.page_data
                    uid = int(pd.map_ubi.uid) if pd.HasField('map_ubi') else 0
                    entry = {
                        'uid': uid,
                        'name': pd.map_ubi.name if pd.HasField('map_ubi') else '',
                        'guild_id': int(pd.guild_id) if pd.HasField('guild_id') else 0,
                        'guild_name': pd.guild_short_name if pd.HasField('guild_short_name') else '',
                        'power': int(pd.power) if pd.HasField('power') else 0,
                        'skin_point': int(pd.skin_point) if pd.HasField('skin_point') else 0,
                        'commander_skin': int(pd.commander_dressup_skin) if pd.HasField('commander_dressup_skin') else 0,
                        'title_skin': int(pd.map_ubi.title_skin_id) if pd.HasField('map_ubi') and pd.map_ubi.HasField('title_skin_id') else 0,
                        'icon': pd.map_ubi.ico if pd.HasField('map_ubi') and pd.map_ubi.HasField('ico') else '',
                        'frame': pd.map_ubi.frame if pd.HasField('map_ubi') and pd.map_ubi.HasField('frame') else '',
                    }
                    self.profile_cache[uid] = entry

        self._observe_conquest_guard_attacks(down)

        return down

    def _observe_playerdata(self, player):
        if not player:
            return
        try:
            self.account_snapshot['uid'] = int(player.uid)
            self.account_snapshot['camp_type'] = int(player.camp_type)
            if player.HasField('name_card'):
                self.account_snapshot['name'] = player.name_card.name
            if player.HasField('account_data'):
                self.account_snapshot['account_level'] = int(player.account_data.level)
                self.account_snapshot['mainbase_level'] = int(player.account_data.mainbase_level)
            if player.HasField('base_data'):
                self._observe_base_data(player.base_data)
            if player.HasField('bag_data'):
                inventory = {}
                bag = player.bag_data
                for field in bag.DESCRIPTOR.fields:
                    if field.is_repeated and field.message_type and field.message_type.name == 'item':
                        for item in getattr(bag, field.name):
                            if item.type_id:
                                inventory[item.type_id] = int(item.num)
                self.account_snapshot['inventory'] = inventory
            if player.building_produce:
                for group in player.building_produce:
                    if group.bld_id:
                        self.production_building_ids.add(int(group.bld_id))
                        for line in group.produce_line:
                            self.production_lines[(int(group.bld_id), int(line.line_id))] = line
            if player.HasField('tech_reply'):
                for tech in player.tech_reply.tech_data:
                    self.tech_state[int(tech.id)] = tech
            if player.user_explore_plane:
                self.scout_planes = [{
                    'id': int(p.plane_id),
                    'state': int(p.plane_state),
                } for p in player.user_explore_plane]
            if player.HasField('client_officer_task_data'):
                # task_id is a string (protobuf field type 9), not numeric —
                # a live account's real reply included e.g. task_id='f1'.
                # time_unit is the same start_time/end_time/speed_up_time
                # shape already confirmed for production (produce_cell) on
                # this same trusted login-sync message.
                self.officer_tasks = [{
                    'task_id': t.task_id,
                    'status': int(t.status),
                    'start_time': int(t.time_unit.start_time) if t.HasField('time_unit') and t.time_unit.HasField('start_time') else 0,
                    'end_time': int(t.time_unit.end_time) if t.HasField('time_unit') and t.time_unit.HasField('end_time') else 0,
                } for t in player.client_officer_task_data.client_officer_task_list]
            if player.HasField('all_army'):
                self._update_army_snapshot(player.all_army.army_list)
        except Exception as exc:
            print(f'  [OBSERVE {self.credentials.account_id}] playerdata error: {exc}')

    def _observe_base_data(self, base_data):
        """Ported from the latest Discord bot: tracks which map-object id is
        THIS account's own main base (self_mainbase_object_ids) and its
        damage/season state — the data Conquest Guard's detection logic
        below depends on."""
        if not base_data:
            return
        if base_data.HasField('base_id'):
            base_id = int(base_data.base_id)
            self.account_snapshot['base_id'] = base_id
            if base_id:
                self.self_mainbase_object_ids.add(base_id)
        if base_data.HasField('city_id'):
            self.account_snapshot['base_city_id'] = int(base_data.city_id)
        if base_data.HasField('base_bld_id'):
            self.account_snapshot['base_building_id'] = int(base_data.base_bld_id)
        # A proto2 false value may be omitted on the wire, so reading only
        # HasField() here would leave a stale True after a successful rebuild.
        self.account_snapshot['base_is_car'] = bool(base_data.is_car)
        if base_data.HasField('base_state'):
            state = base_data.base_state
            self.account_snapshot['base_is_destroyed'] = bool(state.is_destroyed)
            if state.HasField('attacker_name'):
                self.account_snapshot['base_attacker_name'] = state.attacker_name
            if state.HasField('destroy_time'):
                self.account_snapshot['base_destroy_time'] = int(state.destroy_time)
        if base_data.HasField('base_coord'):
            self.account_snapshot['base_x'] = int(base_data.base_coord.x)
            self.account_snapshot['base_y'] = int(base_data.base_coord.y)

    def _observe_general_data(self, general_data):
        """Season/Theater-of-Conquest placement — is_in_conquest() below
        reads these fields to decide whether a main-base attack is actually
        happening inside a Conquest map."""
        if not general_data:
            return
        if general_data.HasField('season_base_info'):
            season = general_data.season_base_info
            self.account_snapshot['season_id'] = int(season.season_id) if season.HasField('season_id') else 0
            self.account_snapshot['season_city_id'] = (
                int(season.season_city_id) if season.HasField('season_city_id') else 0
            )
            self.account_snapshot['season_map_id'] = (
                int(season.season_map_id) if season.HasField('season_map_id') else 0
            )
        if general_data.HasField('last_season_city_id'):
            self.account_snapshot['last_season_city_id'] = int(general_data.last_season_city_id)

    def is_in_conquest(self):
        """Return True only when cached login data places the base in a
        season (Theater of Conquest) map."""
        snap = self.account_snapshot
        current_city = int(snap.get('city_id') or snap.get('base_city_id') or 0)
        current_map = int(snap.get('map_id') or self.current_map_id or 0)
        season_cities = {int(snap.get('season_id') or 0), int(snap.get('season_city_id') or 0)}
        season_cities.discard(0)
        season_map = int(snap.get('season_map_id') or 0)
        return bool(
            (current_city and current_city in season_cities)
            or (current_map and season_map and current_map == season_map)
        )

    def _is_self_mainbase_target(self, owner_id, object_id):
        owner_id = int(owner_id or 0)
        object_id = int(object_id or 0)
        own_uid = int(self.account_snapshot.get('uid') or 0)
        if not own_uid or owner_id != own_uid or not object_id:
            return False
        if object_id in self.self_mainbase_object_ids:
            return True
        base_id = int(self.account_snapshot.get('base_id') or 0)
        if base_id and object_id == base_id:
            return True
        known = self.known_map_objects.get(object_id)
        return bool(known and known.get('is_mainbase') and int(known.get('owner_id') or 0) == own_uid)

    def _maybe_exit_conquest_for_attack(self, pair=None, defender=None, source='battle'):
        """Conquest Guard's core decision: on a confirmed attack against
        THIS account's own main base, while enabled/armed for the currently
        logged-in UID and actually inside a Conquest map, send the same
        exit request a human would send — once, with a cooldown, never
        retried aggressively. Ported as-is from the reference implementation;
        see module docstring for what was intentionally NOT changed."""
        if pair is not None:
            if not pair.HasField('def'):
                return
            defender = getattr(pair, 'def')
        if defender is None:
            return
        if not self._is_self_mainbase_target(defender.owner_id, defender.obj_id):
            return

        attacker_id = 0
        attacker_object_id = 0
        if pair is not None and pair.HasField('att'):
            attacker_id = int(pair.att.owner_id)
            attacker_object_id = int(pair.att.obj_id)
        self.conquest_guard_last_attack = {
            'attacker_uid': attacker_id,
            'attacker_object_id': attacker_object_id,
            'source': source,
            'at': time.time(),
        }

        own_uid = int(self.account_snapshot.get('uid') or 0)
        if not self.automatic_actions_enabled():
            return
        if not self.conquest_guard_enabled or self.conquest_guard_armed_uid != own_uid:
            return
        if not self.is_in_conquest():
            self.conquest_guard_last_result = {
                'status': 'ignored',
                'detail': 'main base was attacked, but it is not in a Theater of Conquest map',
                'at': time.time(),
            }
            return

        now = time.monotonic()
        if self.conquest_guard_in_progress:
            if now - self.conquest_guard_last_request_at < 20.0:
                return
            self.conquest_guard_in_progress = False
            self.conquest_guard_last_result = {
                'status': 'timeout',
                'detail': 'the previous conquest-exit request was not confirmed',
                'at': time.time(),
            }
        if self.conquest_guard_last_request_at and now - self.conquest_guard_last_request_at < 30.0:
            return

        self.conquest_guard_in_progress = True
        self.conquest_guard_last_request_at = now
        self.conquest_guard_attempts += 1
        self.conquest_guard_last_result = {
            'status': 'requested',
            'detail': 'main-base damage detected; conquest exit sent',
            'at': time.time(),
        }
        print(
            f'[{self.credentials.account_id}] Conquest guard: main-base attack detected '
            f'(source={source}, attacker_uid={attacker_id or "unknown"}); leaving conquest.'
        )
        try:
            self.send_season_transfer_out()
        except Exception as exc:
            self.conquest_guard_in_progress = False
            self.conquest_guard_last_result = {
                'status': 'failed',
                'detail': self.safe_error_message(exc),
                'at': time.time(),
            }

    def _observe_conquest_guard_attacks(self, down):
        """Inspect normal, compact, special, and merged damage
        notifications for an attack landing on this account's own base."""
        messages = [down]
        for merge_name in ('battle_msg_merge_notify', 'battle_lua_msg_merge_notify'):
            if down.HasField(merge_name):
                messages.extend(getattr(down, merge_name).down_msg_list)

        for message in messages:
            if message.HasField('battle_reply'):
                battle = message.battle_reply
                if battle.HasField('attack_reply'):
                    for attack in battle.attack_reply.att_list:
                        if attack.HasField('att_def_pair'):
                            self._maybe_exit_conquest_for_attack(pair=attack.att_def_pair, source='normal_damage')
                if battle.HasField('attack_simple_reply'):
                    attack = battle.attack_simple_reply
                    if attack.HasField('att_def_pair'):
                        self._maybe_exit_conquest_for_attack(pair=attack.att_def_pair, source='compact_damage')

            if message.HasField('special_action_reply'):
                special = message.special_action_reply
                for field_name in (
                    'air_damage', 'rocket_damage', 'officer_damage',
                    'direct_damage', 'tactic_damage', 'battle_building_damage',
                ):
                    if not special.HasField(field_name):
                        continue
                    damage = getattr(special, field_name)
                    if damage.HasField('att_info') and damage.att_info.HasField('att_def_pair'):
                        self._maybe_exit_conquest_for_attack(pair=damage.att_info.att_def_pair, source=field_name)
                if special.HasField('trap_damage'):
                    trap = special.trap_damage
                    if trap.HasField('att_info') and trap.att_info.HasField('uniq_id'):
                        self._maybe_exit_conquest_for_attack(defender=trap.att_info.uniq_id, source='trap_damage')

    def _update_army_snapshot(self, army_list, *, replace=True):
        armies = {} if replace else dict(self.armies)
        for army in army_list:
            army_id = int(army.army_id)
            group_unique_id = 0
            if army.HasField('group_data') and army.group_data.HasField('unique_id'):
                group_unique_id = int(army.group_data.unique_id)
            armies[army_id] = {
                'army_id': army_id,
                'equipment_id': int(army.equipment_id),
                'reserves': int(army.has_num),
                'master_obj_id': int(army.master_obj_id),
                'group_unique_id': group_unique_id,
            }
        self.armies = armies
        self.account_snapshot['army_reserves'] = [
            {'army_id': army_id, 'reserves': entry['reserves']} for army_id, entry in sorted(armies.items())
        ]

    def _track_map_object(self, map_obj):
        uid = int(map_obj.unique_id)
        entry = {
            'unique_id': uid,
            'owner_id': int(map_obj.owner_id),
            'x': int(map_obj.x),
            'y': int(map_obj.y),
            'object_type': int(map_obj.object_type),
            'map_id': int(map_obj.map_id),
            'received_at': time.monotonic(),
        }
        is_mainbase = False
        if map_obj.HasField('client_building'):
            bld = map_obj.client_building
            is_mainbase = bld.HasField('client_mainbase')
            entry['client_building'] = {
                'sub_type': int(bld.sub_type),
                'is_mainbase': is_mainbase,
            }
        if map_obj.HasField('client_monster'):
            entry['client_monster'] = {
                'monster_id': int(map_obj.client_monster.monster_id),
                'is_monster': True,
            }
        if map_obj.HasField('client_army'):
            army = map_obj.client_army
            entry['client_army'] = {
                'army_id': int(army.army_id),
                'army_status': int(army.army_status),
                'total_power': int(army.total_power),
            }
        entry['is_mainbase'] = is_mainbase
        self.known_map_objects[uid] = entry
        own_uid = int(self.account_snapshot.get('uid') or 0)
        if is_mainbase and own_uid and int(map_obj.owner_id) == own_uid:
            self.self_mainbase_object_ids.add(uid)
        map_id = int(map_obj.map_id or 0)
        if map_id:
            self.current_map_id = map_id

    # -- Request helpers ----------------------------------------------------
    def request_power_snapshot(self):
        from .protocol import encode_bytes_field

        self.send_message(encode_bytes_field(18, b''))

    @staticmethod
    def _vehicle_patch(vehicle):
        """Present fields only: partial gather replies must not erase telemetry."""
        result = {}
        for name in ('id', 'state', 'mine_id', 'map_vehicle_id', 'type_id', 'map_id'):
            if vehicle.HasField(name):
                result[name] = int(getattr(vehicle, name))
        if vehicle.HasField('is_lock'):
            result['is_locked'] = bool(vehicle.is_lock)
        if vehicle.HasField('info'):
            for name in ('x', 'y', 'start_time', 'end_time', 'max_gather_num'):
                if vehicle.info.HasField(name):
                    result[name] = int(getattr(vehicle.info, name))
        if vehicle.HasField('move_target_pos'):
            for name in ('x', 'y'):
                if vehicle.move_target_pos.HasField(name):
                    result['target_' + name] = int(getattr(vehicle.move_target_pos, name))
        return result

    def request_vehicle_list(self):
        return self.reply_actions.vehicle_list()

    def request_collect_all(self):
        # Non-blocking: the receive loop's automatic collector must keep
        # draining replies. Manual collection waits on these SAME tickets.
        return self.reply_actions.collection()

    def send_farm_search(self, resource, level):
        return self.reply_actions.search_mine(resource, level)

    def send_farm_vehicle(self, mine_id, vehicle_id):
        return self.reply_actions.gather(mine_id, vehicle_id)

    def send_recall_vehicle(self, vehicle_id):
        up = up_pb2.up_msg()
        up.map_mine_req.call_back_vehicle_req.vehicle_id = int(vehicle_id)
        self.send_message(up.SerializeToString())

    def send_continuous_scout(self, plane_id):
        up = up_pb2.up_msg()
        req = up.fog_req.fog_explore_request
        req.plane_id = int(plane_id)
        req.fog_cell_id = 0
        req.is_user_control = False
        self.send_message(up.SerializeToString())

    def send_map_around_request(self, center_x=None, center_y=None, radius_cells=5):
        up = up_pb2.up_msg()
        req = up.map_request.get_around_data
        req.layer = 1
        if center_x is None:
            center_x = int(self.account_snapshot.get('base_x', 0))
        if center_y is None:
            center_y = int(self.account_snapshot.get('base_y', 0))
        gx0, gy0 = center_x // 1000, center_y // 1000
        for gx in range(max(0, gx0 - radius_cells), gx0 + radius_cells + 1):
            for gy in range(max(0, gy0 - radius_cells), gy0 + radius_cells + 1):
                cell = req.around_indexes.add()
                cell.x = gx
                cell.y = gy
        self.send_message(up.SerializeToString())

    def send_map_view_request(self, center_x=None, center_y=None):
        if center_x is None:
            center_x = int(self.account_snapshot.get('base_x', 0))
        if center_y is None:
            center_y = int(self.account_snapshot.get('base_y', 0))
        if self.current_map_id:
            up = up_pb2.up_msg()
            view = up.map_request.set_view_index
            # center_pos is in the same grid-cell units as get_around_data's
            # around_indexes below (raw world coordinates divided by 1000) —
            # sending the raw base_x/base_y here made the server reject
            # every scan with err_info code 10000 "invalid_center_pos" (a
            # coordinate like 47820 is nowhere near a valid grid index),
            # confirmed via a live protocol capture on 2026-09-15.
            view.center_pos.x = max(0, int(center_x) // 1000)
            view.center_pos.y = max(0, int(center_y) // 1000)
            view.layer = 1
            view.map_id = int(self.current_map_id)
            self.send_message(up.SerializeToString())
        self.send_map_around_request(center_x, center_y)

    # -- Skin requests ------------------------------------------------------
    def request_user_skin_data(self):
        """Request full skin inventory for the logged-in player (includes levels/progress)."""
        up = up_pb2.up_msg()
        up.common_skin_req.get_user_skin_req.SetInParent()
        self.send_message(up.SerializeToString())

    def request_player_profile(self, uid):
        """Query any player's profile by UID. Returns skin_point, equipped commander/title skins."""
        up = up_pb2.up_msg()
        up.get_user_info_req.get_user_personal_page.uid = int(uid)
        self.send_message(up.SerializeToString())

    # -- Army Groups ----------------------------------------------------------
    def request_group_army_list(self):
        up = up_pb2.up_msg()
        up.group_army_req.get_group_army_info_req.SetInParent()
        self.send_message(up.SerializeToString())

    def send_join_group_army(self, unique_id, army_ids, group_type):
        up = up_pb2.up_msg()
        request = up.group_army_req.join_group_army_req
        request.unique_id = int(unique_id)
        request.army_id.extend(int(army_id) for army_id in army_ids)
        request.group_type = int(group_type)
        self.send_message(up.SerializeToString())

    def send_exit_group_army(self, army_id):
        up = up_pb2.up_msg()
        up.group_army_req.exit_group_army_req.army_id = int(army_id)
        self.send_message(up.SerializeToString())

    # -- Locate bases -----------------------------------------------------------
    def request_user_position(self, player_uid):
        up = up_pb2.up_msg()
        up.guild_req.get_user_pos.player_id = int(player_uid)
        self.send_message(up.SerializeToString())

    def request_mainbase_position(self, player_uid):
        """Request a player's main-base x/y using the non-guild UID lookup."""
        uid = int(player_uid)
        self.mainbase_positions.pop(uid, None)
        self.last_mainbase_position = None
        self.pending_mainbase_position_uid = uid
        up = up_pb2.up_msg()
        up.league_village_req.msg_get_user_mainbase_pos_req.uid = uid
        try:
            self.send_message(up.SerializeToString())
        except Exception:
            self.pending_mainbase_position_uid = 0
            raise

    # -- Base teleport / Conquest exit ------------------------------------------
    def send_teleport_mainbase(self, x, y, use_item=True):
        up = up_pb2.up_msg()
        request = up.base_req.teleport_mainbase_req
        request.x = int(x)
        request.y = int(y)
        # True mirrors the official client's item button. Mass Deploy
        # intentionally never falls back to the premium-currency path.
        request.use_obj = bool(use_item)
        self.send_message(up.SerializeToString())

    def send_build_mainbase(self, x, y):
        """Turn an airlifted base car back into a main base at x/y."""
        up = up_pb2.up_msg()
        request = up.base_req.move_base_req
        request.x = int(x)
        request.y = int(y)
        self.send_message(up.SerializeToString())

    def send_season_transfer_out(self):
        """Leave the current Theater of Conquest using the official empty
        request — this is what Conquest Guard sends automatically."""
        up = up_pb2.up_msg()
        up.base_req.season_transfer_out_req.SetInParent()
        self.send_message(up.SerializeToString())

    # -- Main loop (runs in background thread) ------------------------------
    def _schedule_callback(self, callback, *args):
        """Invoke a lifecycle callback (on_connected/on_failed/on_disconnected).

        The original bot only ever ran inside py-cord's asyncio loop, so this
        used asyncio.run_coroutine_threadsafe exclusively and was a silent
        no-op without a loop. AccountSession/AccountManager also need to run
        headless (dev scripts, pytest, a future non-async worker) with plain
        synchronous callbacks, so: schedule onto self._loop if one has been
        set (unchanged Discord-bot behavior), otherwise call directly.
        """
        if callback is None:
            return
        if self._loop is not None and not self._loop.is_closed():
            import asyncio
            try:
                asyncio.run_coroutine_threadsafe(callback(*args), self._loop)
            except Exception as exc:
                print(f'Callback scheduling failed: {self.safe_error_message(exc)}')
            return
        try:
            callback(*args)
        except Exception as exc:
            print(f'Callback invocation failed: {self.safe_error_message(exc)}')

    @staticmethod
    def _format_server_error(down):
        code = int(down.err_info.code)
        info = down.err_info.info or 'unspecified server error'
        return f'Warpath server error #{code}: {info}'

    def run(self, on_connected=None, on_failed=None, on_disconnected=None):
        authenticated_once = False
        try:
            with self._state_lock:
                if self.stop_requested:
                    return
                self.connecting = True
                self.running = True
                self.authenticated = False
                self.auth_required = False
                self.last_error = None
                self.seq_id = 0
                self.hb_cnt = 0
                self.last_heartbeat_reply = None
                self.reset_account_data()

            self.connect()
            self.send_login()

            # Phase 1: authenticate. A TCP socket alone is not a login.
            deadline = time.monotonic() + self.credentials.login_timeout
            last_keepalive = time.monotonic()
            while not self.stop_requested and time.monotonic() < deadline:
                sock = self.sock
                if sock is None:
                    raise ConnectionError('socket closed during authentication')
                sock.settimeout(min(2.0, max(0.1, deadline - time.monotonic())))
                down = None
                try:
                    flag, data = self.recv_packet()
                    if flag is None:
                        raise ConnectionError('server closed the connection during authentication')
                    if flag == 0:
                        down = self.observe_account_data(data)
                except socket.timeout:
                    pass

                if down is not None:
                    op = int(down.down_op_code)
                    if down.HasField('err_info'):
                        raise WarpathLoginError(self._format_server_error(down))
                    if op == 2:
                        self.last_heartbeat_reply = time.time()
                    if op == 3 and down.HasField('login_reply'):
                        with self._state_lock:
                            self.authenticated = True
                            self.connecting = False
                        authenticated_once = True
                        break

                now = time.monotonic()
                if now - last_keepalive >= 5.5:
                    self.send_keepalive()
                    last_keepalive = now

            if self.stop_requested:
                return
            if not self.authenticated:
                raise WarpathLoginError(
                    f'authentication timed out after {self.credentials.login_timeout} seconds; '
                    'check the token, device ID, platform metadata, server, and client versions'
                )

            print(f'[{self.credentials.account_id}] Warpath authentication succeeded.')
            self._schedule_callback(on_connected)

            # Initial snapshots are useful but should not invalidate a valid login
            # if one optional request is unavailable in this protocol version.
            for request in (
                self.request_vehicle_list,
                self.request_power_snapshot,
                self.request_user_skin_data,
            ):
                try:
                    request()
                except Exception as exc:
                    print(f'[{self.credentials.account_id}] Initial request failed: {self.safe_error_message(exc)}')

            # Phase 2: authenticated main loop.
            last_keepalive = time.monotonic()
            last_collect = time.monotonic()
            while self.running and not self.stop_requested:
                now = time.monotonic()
                drained = 0
                sock = self.sock
                if sock is None:
                    raise ConnectionError('socket closed')
                sock.settimeout(0.02)

                while drained < 500 and not self.stop_requested:
                    try:
                        flag, data = self.recv_packet()
                    except socket.timeout:
                        break
                    if flag is None:
                        raise ConnectionError('server closed the connection')
                    drained += 1
                    if flag != 0:
                        continue
                    down = self.observe_account_data(data)
                    if down is None:
                        continue
                    op = int(down.down_op_code)
                    if op == 2:
                        self.last_heartbeat_reply = time.time()
                    if down.HasField('err_info') and self.auth_required:
                        raise WarpathLoginError(self._format_server_error(down))

                if now - last_keepalive >= 5.5:
                    self.send_keepalive()
                    last_keepalive = now

                if self.automatic_actions_enabled() and now - last_collect >= 240:
                    try:
                        self.request_collect_all()
                    except Exception as exc:
                        print(f'[{self.credentials.account_id}] Automatic collection failed: {self.safe_error_message(exc)}')
                    last_collect = now

                if drained == 0:
                    time.sleep(0.05)

        except Exception as exc:
            if not self.stop_requested:
                self.last_error = self.safe_error_message(exc)
                print(f'[{self.credentials.account_id}] Warpath connection failed: {self.last_error}')
                callback = on_disconnected if authenticated_once else on_failed
                self._schedule_callback(callback, self.last_error)
        finally:
            self.close()

