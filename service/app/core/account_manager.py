"""AccountManager: the registry of every linked account's AccountSession.

There is deliberately no notion of "the" active account anywhere in this
file — that concept (a single global `warpath` connection + module-level
credential globals in the original warpath_bot.py) is exactly what made
multi-account operation impossible. Here every account is addressed
explicitly by account_id, and any number of them can be active at once, up
to ``max_concurrent_sessions``.

Multi-account connection safety
--------------------------------
Warpath (like most game backends) may flag accounts that share a device
identity or IP in ways that look automated. This module does not try to
evade that: it does not rotate device IDs, spoof fingerprints, or rotate
IPs/proxies to hide multiple accounts from Warpath. Instead:

* Each AccountSession's WarpathConnection builds its login from that
  account's own WarpathCredentials only (see connection.py /
  credentials.py) — accounts never borrow each other's device_id/app_uid.
* ``max_concurrent_sessions`` is an explicit, operator-set ceiling, not a
  performance knob dressed up as a safety feature.
* A session whose login is outright rejected moves to RESTRICTED and stays
  there (AccountSession's default reconnect policy does not retry auth
  failures) instead of being retried aggressively — see the module
  docstring of account_session.py.
* Nothing here masks or auto-resolves a RESTRICTED session; it is surfaced
  through status()/list_accounts()/the on_event callback so a human decides
  what to do about it.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from .account_session import (
    AccountSession,
    ConnectionFactory,
    EventHandler,
    ReconnectPolicy,
)
from .pilot_activation import PilotActivation, PilotBlocked
from .warpath.connection import WarpathConnection
from .warpath.credentials import WarpathCredentials

BroadcastAction = Callable[[AccountSession], Any]


class AccountManager:
    def __init__(
        self,
        *,
        max_concurrent_sessions: int = 5,
        on_event: Optional[EventHandler] = None,
        pilot_policy=None,
    ):
        self.max_concurrent_sessions = max_concurrent_sessions
        self._sessions: Dict[str, AccountSession] = {}
        self._lock = threading.RLock()
        self._on_event = on_event
        self.pilot = pilot_policy if pilot_policy is not None else PilotActivation()

    # -- registry -----------------------------------------------------------
    def add_account(
        self,
        credentials: WarpathCredentials,
        *,
        reconnect_policy: Optional[ReconnectPolicy] = None,
        connection_factory: ConnectionFactory = WarpathConnection,
    ) -> AccountSession:
        with self._lock:
            if credentials.account_id in self._sessions:
                raise ValueError(f'account {credentials.account_id!r} is already registered')
            session = AccountSession(
                credentials,
                reconnect_policy=reconnect_policy,
                connection_factory=connection_factory,
                on_event=self._on_event,
            )
            session.connection.pilot_policy = self.pilot
            self._sessions[credentials.account_id] = session
            return session

    def remove_account(self, account_id: str, *, timeout: float = 10.0) -> None:
        with self._lock:
            session = self._sessions.pop(account_id, None)
        self.pilot.revoke(account_id)
        if session is not None and session.is_active:
            session.stop(timeout=timeout)

    def get_account(self, account_id: str) -> Optional[AccountSession]:
        with self._lock:
            return self._sessions.get(account_id)

    def list_accounts(self) -> List[dict]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [session.status() for session in sessions]

    def list_active(self) -> List[dict]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [session.status() for session in sessions if session.is_active]

    # -- lifecycle ------------------------------------------------------------
    def _raise_if_at_capacity(self, *, excluding: AccountSession) -> None:
        """Call only while holding self._lock. Shared by every path that can
        bring a session to CONNECTING/CONNECTED, so the cap can't drift out
        of sync between them again (see start()/reconnect() below).

        `excluding` is left out of the count on purpose: a session that is
        already active isn't asking for a *new* slot by reconnecting — it's
        cycling the one it already holds (AccountSession.reconnect() stops
        it and starts it again). Excluding it makes that a no-op against the
        cap either way: for an already-active session the count below it is
        always < max_concurrent_sessions (the cap held before this call, by
        induction), and for an inactive one `excluding` was never counted in
        the first place, so this is identical to the old start()-only check.
        """
        active_count = sum(
            1 for session in self._sessions.values()
            if session is not excluding and session.is_active
        )
        if active_count >= self.max_concurrent_sessions:
            raise RuntimeError(
                f'max_concurrent_sessions ({self.max_concurrent_sessions}) reached; '
                'stop another account before starting a new one'
            )

    def start(self, account_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(account_id)
            if session is None:
                raise KeyError(f'unknown account {account_id!r}')
            if session.is_active:
                return False
            self.pilot.require_observation(account_id)
            self._raise_if_at_capacity(excluding=session)
            return session.start()

    def stop(self, account_id: str, *, timeout: float = 10.0) -> None:
        self.pilot.revoke(account_id)
        session = self.get_account(account_id)
        if session is None:
            raise KeyError(f'unknown account {account_id!r}')
        session.stop(timeout=timeout)

    def reconnect(self, account_id: str) -> bool:
        # The capacity check happens under self._lock (fast: it only reads
        # is_active on every session), but session.reconnect() itself is
        # NOT called while holding it: AccountSession.reconnect() calls
        # stop() first, which can block for up to its `timeout` (default
        # 10s) joining the old thread — holding the manager lock for that
        # long would stall every other account's start/stop/status/list
        # call for the duration, which is exactly the kind of cross-account
        # interference this whole architecture exists to avoid. There is a
        # narrow window here where a concurrent start()/reconnect() on
        # another account could be admitted in between the check and the
        # actual (re)start, transiently allowing max_concurrent_sessions+1
        # active sessions; closing that fully would need a reservation
        # scheme this stage's instructions don't ask for ("do not redesign
        # the architecture"). This closes the actual reported gap — no
        # check at all — down to the same check-then-act window start()
        # always had for a single caller.
        with self._lock:
            session = self._sessions.get(account_id)
            if session is None:
                raise KeyError(f'unknown account {account_id!r}')
            self._raise_if_at_capacity(excluding=session)
        if getattr(self.pilot, 'requires_fresh_connection', True):
            if not session.is_quiescent:
                raise PilotBlocked('pause the current session before requesting a fresh observation grant')
            return self.start(account_id)
        return session.reconnect()

    def stop_all(self, *, timeout: float = 10.0) -> None:
        self.pilot.revoke_all()
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            if session.is_active:
                session.stop(timeout=timeout)

    # -- fan-out --------------------------------------------------------------
    def broadcast(self, action: BroadcastAction, *, only_active: bool = True) -> Dict[str, Any]:
        """Run ``action(session)`` for every (or every active) session. One
        account raising never stops or skips the others — its exception is
        collected as that account's result instead of propagating."""
        with self._lock:
            sessions = list(self._sessions.values())
        results: Dict[str, Any] = {}
        for session in sessions:
            if only_active and not session.is_active:
                continue
            try:
                results[session.account_id] = action(session)
            except Exception as exc:  # noqa: BLE001 - intentionally broad, isolated per account
                results[session.account_id] = exc
        return results

