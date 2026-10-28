"""Website-session DTO and in-memory TEST DOUBLE.

Production uses db.identity_store.PostgresIdentityStore exclusively. The
memory implementation is retained for isolated API/protocol unit fixtures;
there is no environment flag or runtime fallback that enables it.
"""

from __future__ import annotations

import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException

DEFAULT_SESSION_TTL_SECONDS = 24 * 60 * 60  # 24h absolute expiry
DEFAULT_IDLE_TIMEOUT_SECONDS = 2 * 60 * 60  # 2h since last use, whichever comes first


@dataclass
class DashboardSession:
    session_id: str
    user_id: uuid.UUID
    email: str
    role: str
    csrf_token: str
    # Public cache namespace; never an authentication credential.
    cache_key: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)


class DashboardSessionStore:
    def __init__(
        self, *, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
    ):
        self.ttl_seconds = ttl_seconds
        self.idle_timeout_seconds = idle_timeout_seconds
        self._lock = threading.Lock()
        self._sessions: dict[str, DashboardSession] = {}
        self._throttles: dict[str, tuple[float, int]] = {}

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.created_at > self.ttl_seconds or now - s.last_used_at > self.idle_timeout_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

    def create(self, *, user_id: uuid.UUID, email: str, role: str, expected_password_hash=None) -> DashboardSession:
        with self._lock:
            self._prune_locked()
            session = DashboardSession(
                session_id=secrets.token_urlsafe(32),
                user_id=user_id,
                email=email,
                role=role,
                csrf_token=secrets.token_urlsafe(32),
            )
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> DashboardSession | None:
        if not session_id:
            return None
        with self._lock:
            self._prune_locked()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_used_at = time.time()
            return session

    def destroy(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def throttle(self, scope, subject, *, limit: int, seconds: int) -> None:
        """In-memory fixed-window throttle for unit tests only."""
        key = f'{scope}:{subject}'
        now = time.monotonic()
        with self._lock:
            started, count = self._throttles.get(key, (now, 0))
            if now - started >= seconds:
                started, count = now, 0
            if count >= limit:
                raise HTTPException(
                    status_code=429,
                    detail='too many attempts; try again later',
                    headers={'Retry-After': str(seconds)},
                )
            self._throttles[key] = (started, count + 1)

    def active_count(self, user_id: uuid.UUID | None = None) -> int:
        """Backs /auth/me's active_sessions field (Settings' 'session
        capacity' display); members receive only their own count. Not used
        for auth gating, which is entirely
        deps.require_dashboard_auth's job."""
        with self._lock:
            self._prune_locked()
            return sum(user_id is None or s.user_id == user_id for s in self._sessions.values())
