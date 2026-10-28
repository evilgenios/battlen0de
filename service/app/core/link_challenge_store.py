"""Owner-bound, process-local linking challenges. Run exactly ONE worker.

Codes are never stored. A lock claims each send/verification before any
upstream I/O; busy entries cannot be resent, verified, deleted or pruned.
Restarts lose challenges. This is not a durable/distributed job store.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from .warpath.credentials import WarpathCredentials
from .warpath.lilith import LinkSession

DEFAULT_TTL_SECONDS = 600
DEFAULT_MAX_VERIFY_ATTEMPTS = 5
DEFAULT_RESEND_COOLDOWN_SECONDS = 30


class ChallengeError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


@dataclass
class PendingLink:
    challenge_id: str
    owner_user_id: uuid.UUID
    email: str
    vehicle: WarpathCredentials = field(repr=False)
    link_session: LinkSession = field(repr=False)
    created_at: float = field(default_factory=time.time)
    last_sent_at: float = 0
    attempts: int = 0
    operation: str | None = None
    target_account_id: uuid.UUID | None = None
    template: WarpathCredentials | None = field(default=None, repr=False)


class LinkChallengeStore:
    def __init__(self, *, ttl_seconds=DEFAULT_TTL_SECONDS,
                 max_attempts=DEFAULT_MAX_VERIFY_ATTEMPTS,
                 resend_cooldown_seconds=DEFAULT_RESEND_COOLDOWN_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.max_attempts = max_attempts
        self.resend_cooldown_seconds = resend_cooldown_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, PendingLink] = {}

    def _prune_locked(self):
        for cid, pending in list(self._pending.items()):
            if pending.operation is None and time.time() - pending.created_at > self.ttl_seconds:
                del self._pending[cid]

    def _owned_locked(self, challenge_id, owner_user_id):
        self._prune_locked()
        pending = self._pending.get(challenge_id)
        if pending is None or pending.owner_user_id != owner_user_id:
            raise ChallengeError(410, 'This verification request was not found or has expired. Request a new code.')
        return pending

    @staticmethod
    def _idle(pending):
        if pending.operation is not None:
            raise ChallengeError(409, 'This verification request is already in progress.')

    def get(self, challenge_id: str, owner_user_id: uuid.UUID) -> PendingLink | None:
        with self._lock:
            try:
                return self._owned_locked(challenge_id, owner_user_id)
            except ChallengeError:
                return None

    def begin_send(self, *, owner_user_id: uuid.UUID, email: str,
                   vehicle: WarpathCredentials, challenge_id: str | None = None,
                   target_account_id: uuid.UUID | None = None, template: WarpathCredentials | None = None) -> PendingLink:
        with self._lock:
            self._prune_locked()
            if challenge_id is not None:
                pending = self._owned_locked(challenge_id, owner_user_id)
                if pending.email != email or pending.target_account_id != target_account_id:
                    raise ChallengeError(410, 'Verification request does not match this email.')
            else:
                pending = next((p for p in self._pending.values()
                                if p.owner_user_id == owner_user_id and p.email == email and p.target_account_id == target_account_id), None)
            if pending is not None:
                self._idle(pending)
                if time.time() - pending.last_sent_at < self.resend_cooldown_seconds:
                    raise ChallengeError(429, 'Please wait before requesting another code.')
            else:
                if sum(p.owner_user_id == owner_user_id for p in self._pending.values()) >= 3:
                    raise ChallengeError(429, 'Too many pending linking requests.')
                pending = PendingLink(uuid.uuid4().hex, owner_user_id, email, vehicle, LinkSession.new(),
                                      target_account_id=target_account_id, template=template)
                self._pending[pending.challenge_id] = pending
            pending.operation = 'send'
            return pending

    def finish_send(self, challenge_id, owner_user_id, link_session: LinkSession | None):
        with self._lock:
            pending = self._owned_locked(challenge_id, owner_user_id)
            if pending.operation != 'send':
                raise ChallengeError(409, 'No send in progress.')
            if link_session is not None:
                pending.link_session = link_session
                pending.last_sent_at = time.time()
                pending.attempts = 0
            elif not pending.last_sent_at:
                del self._pending[challenge_id]
            pending.operation = None

    def claim_verification(self, challenge_id: str, owner_user_id: uuid.UUID) -> PendingLink:
        with self._lock:
            pending = self._owned_locked(challenge_id, owner_user_id)
            self._idle(pending)
            if pending.attempts >= self.max_attempts:
                del self._pending[challenge_id]
                raise ChallengeError(429, 'Too many incorrect attempts. Request a new verification code.')
            pending.attempts += 1
            pending.operation = 'verify'
            return pending

    def finish_verification(self, challenge_id, owner_user_id, *, success: bool):
        with self._lock:
            pending = self._owned_locked(challenge_id, owner_user_id)
            if pending.operation != 'verify':
                raise ChallengeError(409, 'No verification in progress.')
            if success:
                # Consume BEFORE creating the account: a DB failure cannot replay
                # a successful upstream verification. User must start a new link.
                del self._pending[challenge_id]
            pending.operation = None

    def discard(self, challenge_id: str, owner_user_id: uuid.UUID):
        with self._lock:
            pending = self._owned_locked(challenge_id, owner_user_id)
            self._idle(pending)
            del self._pending[challenge_id]
