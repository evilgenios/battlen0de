"""AccountSession: one account's entire connection lifecycle.

Each AccountSession owns exactly one WarpathConnection and exactly one
background thread. There is no shared/global connection or thread anywhere
in this module — two AccountSessions never touch each other's state, so
starting, stopping, or losing one has no effect on any other.

Reconnection is deliberately conservative and account-scoped:

* A connection that authenticated and then dropped (network blip, server
  restart, etc.) is retried with exponential backoff, up to
  ``ReconnectPolicy.max_retries`` times.
* A connection whose *login itself* was rejected is treated as a possible
  account/device restriction rather than a transient error. By default
  (``max_auth_failures=0``) it is never retried automatically — the session
  moves to RESTRICTED and an event is emitted so a human (or the future
  dashboard) can look at it, instead of hammering Warpath's login endpoint
  from a device that may already be flagged. This is a deliberate anti-abuse
  safeguard, not a bug: see the "Multi-account connection safety" note in
  the module docstring of account_manager.py.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .warpath.connection import WarpathConnection
from .warpath.credentials import WarpathCredentials, redact_secrets

ConnectionFactory = Callable[[WarpathCredentials], WarpathConnection]


class SessionState(str, Enum):
    IDLE = 'idle'                # created, never started
    CONNECTING = 'connecting'    # socket/login in flight
    CONNECTED = 'connected'      # authenticated
    RECONNECTING = 'reconnecting'  # dropped/failed, backing off before retry
    STOPPED = 'stopped'          # stop() was called; not running
    FAILED = 'failed'            # gave up after max_retries transient failures
    RESTRICTED = 'restricted'    # login was rejected; isolated, not retried automatically


@dataclass
class ReconnectPolicy:
    """Backoff policy for one account. Intentionally simple (linear config,
    no jitter tuning knobs beyond one) — this is meant to survive a flaky
    network, not to be a general-purpose retry framework."""

    max_retries: int = 5              # for a connection that HAD authenticated, then dropped
    max_auth_failures: int = 0        # for a login that was rejected outright; 0 = never auto-retry
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 120.0
    multiplier: float = 2.0
    jitter_seconds: float = 1.0

    def delay_for_attempt(self, attempt: int) -> float:
        raw = self.base_delay_seconds * (self.multiplier ** max(0, attempt - 1))
        capped = min(raw, self.max_delay_seconds)
        return capped + random.uniform(0, self.jitter_seconds)


@dataclass
class SessionEvent:
    account_id: str
    kind: str   # 'connected' | 'disconnected' | 'auth_failed' | 'restricted' | 'reconnecting' | 'stopped'
    detail: str
    at: float = field(default_factory=time.time)


EventHandler = Callable[[SessionEvent], None]


class AccountSession:
    """Owns exactly one WarpathConnection and one background thread for
    exactly one account."""

    def __init__(
        self,
        credentials: WarpathCredentials,
        *,
        reconnect_policy: Optional[ReconnectPolicy] = None,
        connection_factory: ConnectionFactory = WarpathConnection,
        on_event: Optional[EventHandler] = None,
    ):
        self.account_id = credentials.account_id
        self.credentials = credentials
        self.reconnect_policy = reconnect_policy or ReconnectPolicy()
        self.connection: WarpathConnection = connection_factory(credentials)
        self._on_event = on_event

        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state: SessionState = SessionState.IDLE
        self.last_error: Optional[str] = None
        self.last_connected_at: Optional[float] = None
        self.started_at: Optional[float] = None
        self._retry_count = 0
        self._auth_failure_count = 0

    # -- status ---------------------------------------------------------
    @property
    def state(self) -> SessionState:
        with self._lock:
            return self._state

    @property
    def is_active(self) -> bool:
        return self.state in (SessionState.CONNECTING, SessionState.CONNECTED, SessionState.RECONNECTING)

    @property
    def is_quiescent(self) -> bool:
        with self._lock:
            return not self.is_active and not (self._thread and self._thread.is_alive())

    def status(self) -> dict:
        with self._lock:
            return {
                'account_id': self.account_id,
                'label': self.credentials.label,
                'state': self._state.value,
                'authenticated': self.connection.authenticated,
                'connection_state': self.connection.connection_state,
                'last_error': self.last_error,
                'last_connected_at': self.last_connected_at,
                'started_at': self.started_at,
                'retry_count': self._retry_count,
                'auth_failure_count': self._auth_failure_count,
            }

    # -- lifecycle --------------------------------------------------------
    def start(self) -> bool:
        """Start this account's connection. Returns False (without raising)
        if it is already running or its credentials are incomplete."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            errors = self.credentials.validation_errors()
            if errors:
                self.last_error = '; '.join(errors)
                self._state = SessionState.FAILED
                self._emit('auth_failed', self.last_error)
                return False
            self._stop_event.clear()
            # WarpathConnection.disconnect() sets connection.stop_requested
            # and nothing in connection.py ever clears it (by design — a
            # bare WarpathConnection's `run()` uses that flag to let a
            # concurrent stop() cancel an attempt that hasn't started yet).
            # AccountSession owns this connection's whole lifecycle, so
            # arming a fresh attempt here is this layer's job: without this,
            # every run() after the first stop()+start()/reconnect() cycle
            # hits `if self.stop_requested: return` at the top of run() and
            # silently no-ops — found while validating the reconnect step of
            # the full account lifecycle (see test_account_lifecycle.py).
            self.connection.stop_requested = False
            self._retry_count = 0
            self._auth_failure_count = 0
            self.started_at = time.time()
            self._state = SessionState.CONNECTING
            self._thread = threading.Thread(
                target=self._supervise,
                name=f'AccountSession-{self.account_id}',
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 10.0) -> None:
        """Stop this account's connection and wait for its thread to exit.
        Never touches any other AccountSession."""
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        self.connection.disconnect()
        if thread is not None:
            thread.join(timeout=timeout)
        with self._lock:
            if self._state not in (SessionState.FAILED, SessionState.RESTRICTED):
                self._state = SessionState.STOPPED
        self._emit('stopped', 'stopped by request')

    def reconnect(self) -> bool:
        """Explicit, human-requested reconnect: resets backoff/failure
        counters and restriction status, unlike the automatic retries in
        the supervisor loop."""
        self.stop()
        with self._lock:
            self._state = SessionState.IDLE
        return self.start()

    # -- internals --------------------------------------------------------
    def _emit(self, kind: str, detail: str) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(SessionEvent(account_id=self.account_id, kind=kind, detail=detail or ''))
        except Exception:
            pass

    def _on_connected(self) -> None:
        # Deliberately does NOT reset _retry_count/_auth_failure_count: a
        # connection that authenticates and then drops again a moment later
        # (flapping) must still count toward max_retries. Resetting on every
        # successful reconnect would make max_retries effectively
        # unreachable in exactly the scenario it exists to bound. The
        # counters only reset on an explicit start()/reconnect().
        with self._lock:
            self._state = SessionState.CONNECTED
            self.last_connected_at = time.time()
            self.last_error = None
        uid = self.connection.account_snapshot.get('uid', '?')
        self._emit('connected', f'authenticated as uid={uid}')

    def _on_failed(self, error: Any) -> None:
        message = redact_secrets(error, self.credentials)
        with self._lock:
            self.last_error = message
            self._auth_failure_count += 1
        self._emit('auth_failed', message)

    def _on_disconnected(self, error: Any) -> None:
        message = redact_secrets(error, self.credentials)
        with self._lock:
            self.last_error = message
        self._emit('disconnected', message)

    def _run_connection_once(self) -> None:
        self.connection.run(
            on_connected=self._on_connected,
            on_failed=self._on_failed,
            on_disconnected=self._on_disconnected,
        )

    def _supervise(self) -> None:
        """The one background thread this session owns. Runs the connection,
        and on an unexpected exit, decides — based on this account's own
        history only — whether to back off and retry or to stop."""
        try:
            while not self._stop_event.is_set():
                auth_failures_before = self._auth_failure_count
                retries_before = self._retry_count

                try:
                    self._run_connection_once()
                except Exception as exc:
                    with self._lock:
                        self.last_error = redact_secrets(exc, self.credentials)

                if self._stop_event.is_set():
                    break
                pilot = getattr(self.connection, 'pilot_policy', None)
                if pilot is not None and getattr(pilot, 'requires_fresh_connection', True):
                    # A closed observation connection needs a fresh operator grant.
                    # Never reset its tracker or retry after uncertainty.
                    if self._auth_failure_count > auth_failures_before:
                        with self._lock:
                            self._state = SessionState.RESTRICTED
                        self._emit('restricted', 'login failed; fresh operator review required')
                    break

                auth_failed_this_round = self._auth_failure_count > auth_failures_before
                if auth_failed_this_round:
                    if self._auth_failure_count > self.reconnect_policy.max_auth_failures:
                        with self._lock:
                            self._state = SessionState.RESTRICTED
                        self._emit(
                            'restricted',
                            'Login was rejected; isolating this account instead of retrying '
                            f'automatically (possible credential or account/device restriction). '
                            f'Last error: {self.last_error}',
                        )
                        return
                    attempt = self._auth_failure_count
                else:
                    self._retry_count += 1
                    if self._retry_count > self.reconnect_policy.max_retries:
                        with self._lock:
                            self._state = SessionState.FAILED
                        self._emit(
                            'stopped',
                            f'Giving up after {self._retry_count - 1} reconnect attempt(s). '
                            f'Last error: {self.last_error}',
                        )
                        return
                    attempt = self._retry_count

                delay = self.reconnect_policy.delay_for_attempt(attempt)
                with self._lock:
                    self._state = SessionState.RECONNECTING
                self._emit('reconnecting', f'retrying in {delay:.1f}s (attempt {attempt})')
                self._stop_event.wait(delay)
        finally:
            with self._lock:
                if self._state not in (SessionState.FAILED, SessionState.RESTRICTED):
                    self._state = SessionState.STOPPED

