"""Process-local observation grants. No production action/evidence override."""
from contextlib import contextmanager
from dataclasses import dataclass
import os
import threading
import time
import uuid


class PilotBlocked(RuntimeError):
    pass


EVIDENCE_GATE = 'game actions unavailable: upstream confirmation evidence is unverified'


def observation_access_mode() -> str:
    mode = os.environ.get('OBSERVATION_ACCESS_MODE', 'pilot').strip().lower()
    if mode not in ('pilot', 'customer'):
        raise RuntimeError('OBSERVATION_ACCESS_MODE must be pilot or customer')
    return mode


def validate_pilot_configuration():
    value = os.environ.get('AUTOSTART_ACTIVE_ACCOUNTS', 'false').strip().lower()
    if value not in ('', '0', 'false', 'no'):
        raise RuntimeError('AUTOSTART_ACTIVE_ACCOUNTS must remain false')
    observation_access_mode()


def observation_packet(message):
    """Exactly one allowlisted request; reject unknown and mixed fields too."""
    clean = type(message)()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    if clean.SerializeToString(deterministic=True) != message.SerializeToString(deterministic=True):
        return False
    fields = [f.name for f, _ in message.ListFields() if f.name != 'msg_seq_id']
    if len(fields) != 1:
        return False
    name = fields[0]
    if name in ('sdk_login', 'heartbeat'):
        return True
    if name == 'power_req':
        return not message.power_req.ListFields()
    nested = {
        'map_mine_req': 'get_vehicle_list_req',
        'common_skin_req': 'get_user_skin_req',
        'group_army_req': 'get_group_army_info_req',
        'get_user_info_req': 'get_user_personal_page',
    }
    allowed = nested.get(name)
    return allowed is not None and [f.name for f, _ in getattr(message, name).ListFields()] == [allowed]


@dataclass(frozen=True)
class ObservationGrant:
    actor_id: str
    issued_at: float
    expires_at: float
    deadline: float


class PilotActivation:
    observation_only = True

    def __init__(self, *, clock=time.monotonic, wall_clock=time.time, customer_observation=None):
        self.instance_id = str(uuid.uuid4())
        self._clock, self._wall_clock = clock, wall_clock
        self._customer_observation = (
            observation_access_mode() == 'customer'
            if customer_observation is None else bool(customer_observation)
        )
        self.requires_fresh_connection = not self._customer_observation
        self._lock = threading.RLock()
        self._grants = {}

    def activate(self, account_id, actor_id, minutes):
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 60:
            raise ValueError('observation duration must be 1–60 minutes')
        with self._lock:
            now = self._wall_clock()
            self._grants[account_id] = ObservationGrant(str(actor_id), now, now + minutes * 60,
                                                        self._clock() + minutes * 60)

    def revoke(self, account_id):
        # Shares the transmission lock: returns only after any admitted write.
        with self._lock:
            self._grants.pop(account_id, None)

    def revoke_all(self):
        with self._lock:
            self._grants.clear()

    def require_observation(self, account_id):
        if self._customer_observation:
            return
        with self._lock:
            grant = self._grants.get(account_id)
            if grant is None or self._clock() >= grant.deadline:
                raise PilotBlocked('pilot is off or expired; a fresh admin observation grant is required')

    def require_actions(self):
        raise PilotBlocked(EVIDENCE_GATE)

    def automatic_enabled(self, account_id):
        return False  # No user/env acknowledgement can substitute for reviewed evidence.

    def check_http(self, account_id, action):
        if action in ('connect', 'reconnect', 'refresh', 'heartbeat'):
            self.require_observation(account_id)
        else:
            self.require_actions()

    @contextmanager
    def transmission(self, account_id, message=None):
        with self._lock:
            self.require_observation(account_id)
            if message is not None and not observation_packet(message):
                self.require_actions()
            yield

    def status(self, account_id):
        with self._lock:
            grant = self._grants.get(account_id)
            active = grant is not None and self._clock() < grant.deadline
            if self._customer_observation:
                return {
                    'mode': 'observe', 'reason': 'customer_mode',
                    'instance_id': self.instance_id,
                    'issued_by': None, 'issued_at': None, 'expires_at': None,
                    'automatic_actions': False, 'game_actions': False,
                    'upstream_evidence': 'unverified', 'restart_policy': 'auto',
                }
            return {
                'mode': 'observe' if active else 'off',
                'reason': 'operator_grant' if active else ('expired' if grant else 'not_activated'),
                'instance_id': self.instance_id,
                'issued_by': grant.actor_id if grant else None,
                'issued_at': grant.issued_at if grant else None,
                'expires_at': grant.expires_at if grant else None,
                'automatic_actions': False, 'game_actions': False,
                'upstream_evidence': 'unverified', 'restart_policy': 'off',
            }
