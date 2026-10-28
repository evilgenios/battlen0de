from __future__ import annotations

import time
from datetime import datetime, timezone
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from tests.fakes import synthetic_account_manager as AccountManager
from app.core.dashboard_session import DashboardSessionStore
from app.core.link_challenge_store import LinkChallengeStore
from app.core.mass_deploy import MassDeployLock
from app.core.warpath import connection as connection_module
from app.core.warpath.credentials import WarpathCredentials
from app.deps import DEV_USER_EMAIL_ENV_VAR
from app.main import create_app
from tests.fake_repository import FakeEngine, InMemoryAccountRepository
from tests.fakes import ScriptedSocketFactory


def wait_until(predicate, *, timeout: float = 3.0, interval: float = 0.02) -> bool:
    """Poll ``predicate`` until it's truthy or ``timeout`` elapses. Used
    instead of fixed sleeps so tests run fast when things work and fail
    with a clear timeout instead of a flaky race when they don't."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def fake_credentials(account_id: str, **overrides) -> WarpathCredentials:
    """Obviously-fake credentials for tests. Never real values — see the
    Security section of the stage-1/2 instructions."""
    defaults = dict(
        account_id=account_id,
        label=f'label-{account_id}',
        app_uid=f'uid-{account_id}',
        app_token=f'token-{account_id}-SECRET',
        device_id=f'device-{account_id}-SECRET',
        profile_uid=1,
        platform=22,
        app_id='test-app-id',
        pack_name='test-pack-name',
        channel_id='test-channel-id',
        device_model='win',
        os_type='win',
        os_version='10',
        app_version='1.0.0',
        package_version='1.0.0',
        server_ip='127.0.0.1',
        server_port=10000,
        login_timeout=2,
    )
    defaults.update(overrides)
    return WarpathCredentials(**defaults)


@pytest.fixture
def make_credentials():
    return fake_credentials


@pytest.fixture
def scripted_sockets(monkeypatch):
    """Patch WarpathConnection.connect() to hand out scripted
    FakeWarpathSocket instances instead of opening a real TCP socket. Call
    the returned function with a list of FakeWarpathSocket instances (one
    per expected connect() attempt) before starting a session/connection.

    Important: this replaces the `socket` NAME inside
    app.core.warpath.connection's own module namespace with a shim that
    copies every real `socket` module attribute (AF_INET, SOCK_STREAM,
    timeout, ...) except `.socket`, which becomes our factory. It
    deliberately does NOT mutate the real, shared `socket` module's
    `socket` class in place (`monkeypatch.setattr(socket, 'socket', ...)`)
    — Stage 1/2's tests did that safely because they never ran an asyncio
    event loop in the same process. Stage 3's FastAPI TestClient does run a
    real event loop (in a background thread, via anyio's portal), and on
    Windows that loop's ProactorEventLoop creates its own internal sockets
    for cross-thread wakeup. Globally replacing socket.socket breaks that
    and hangs the event loop forever — this scoped patch avoids it
    entirely by leaving the real socket module untouched everywhere except
    inside connection.py."""

    import types

    def _install(sockets):
        factory = ScriptedSocketFactory(sockets)
        shim = types.SimpleNamespace(**vars(connection_module.socket))
        shim.socket = factory
        monkeypatch.setattr(connection_module, 'socket', shim)
        return factory

    return _install


# ---------------------------------------------------------------------------
# Stage 3: FastAPI-layer fixtures. See tests/fake_repository.py's docstring
# for why these use an in-memory AccountRepository rather than Postgres.
# ---------------------------------------------------------------------------

DEV_USER_EMAIL = 'dev-user@example.test'


class FakeAdminSecurityStore:
    def __init__(self, repo):
        self.repo = repo
        self.events = []
        self._mfa = {}

    def audit(self, **kwargs):
        self.events.append(dict(kwargs))

    def verify_login_mfa(self, user_id, code):
        enabled = self._mfa.get(user_id, False)
        return (enabled, not enabled or code == '123456')

    def mfa_status(self, user_id):
        return {'enabled': bool(self._mfa.get(user_id)), 'setup_pending': False}

    def begin_mfa_setup(self, user_id):
        return {'secret': 'JBSWY3DPEHPK3PXP', 'otpauth_uri': 'otpauth://totp/BattleN0de:test?secret=JBSWY3DPEHPK3PXP'}

    def enable_mfa(self, user_id, code):
        if code != '123456':
            from fastapi import HTTPException
            raise HTTPException(422, 'invalid authenticator code')
        self._mfa[user_id] = True

    def disable_mfa(self, user_id, code):
        if code != '123456':
            from fastapi import HTTPException
            raise HTTPException(422, 'invalid authenticator code')
        self._mfa[user_id] = False

    def list_audit(self, **kwargs):
        return []

    def list_users(self, *, query='', limit=200, offset=0):
        rows = list(self.repo._users.values())
        if query:
            rows = [row for row in rows if query.lower() in row.email.lower()]
        result = []
        for row in rows[offset:offset + limit]:
            accounts = self.repo.list_accounts(row.id)
            result.append({
                'id': str(row.id),
                'email': row.email,
                'role': row.role,
                'status': row.status,
                'plan': 'alliance' if row.max_accounts > 1 else 'individual',
                'max_accounts': row.max_accounts,
                'max_sessions': row.max_sessions,
                'max_active_accounts': row.max_active_accounts,
                'mfa_enabled': bool(self._mfa.get(row.id)),
                'player_scout_access': bool(row.player_scout_access),
                'account_count': len(accounts),
                'active_sessions': 0,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
            })
        return result



@pytest.fixture
def dev_user_email(monkeypatch):
    """Explicit test-only local admin for legacy protocol/API fixtures."""
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('AUTH_MODE', 'local')
    monkeypatch.setenv('DEV_USER_ROLE', 'admin')
    monkeypatch.setenv(DEV_USER_EMAIL_ENV_VAR, DEV_USER_EMAIL)
    return DEV_USER_EMAIL


@pytest.fixture
def fake_repo():
    return InMemoryAccountRepository()


@pytest.fixture
def account_manager(fake_repo):
    """Wires the same on_event -> account_events bridge main.py's real
    lifespan uses (app.main._make_event_sink), reused rather than
    reimplemented, so tests actually exercise that wiring instead of only
    the API-request-driven events (account_connect_requested, etc.). Before
    this, no test ever observed a live-session event (account_connected,
    account_auth_failed, ...) landing in the repository at all."""
    from app.main import _make_event_sink

    manager = AccountManager(max_concurrent_sessions=5, on_event=_make_event_sink(fake_repo))
    yield manager
    manager.stop_all()


@pytest.fixture
def link_challenge_store():
    return LinkChallengeStore()


@pytest.fixture
def api_client(dev_user_email, fake_repo, account_manager, link_challenge_store, monkeypatch):
    """A FastAPI TestClient wired with the in-memory repository and a real
    AccountManager (sockets faked via scripted_sockets, same as every other
    Stage 1/2 test) — no lifespan, no database. See app.main.create_app's
    docstring."""
    for key, value in {'APP_ID': 'synthetic-app', 'PACK_NAME': 'synthetic-pack', 'CHANNEL_ID': 'synthetic-channel',
                       'APP_VERSION': '1.0', 'PACKAGE_VERSION': '1.0', 'OS_TYPE': 'win'}.items():
        monkeypatch.setenv('WARPATH_' + key, value)
    app = create_app(lifespan_context=None)
    app.state.repository = fake_repo
    app.state.account_manager = account_manager
    app.state.engine = FakeEngine(healthy=True)
    app.state.link_challenges = link_challenge_store
    app.state.mass_deploy_lock = MassDeployLock()
    app.state.dashboard_sessions = DashboardSessionStore()
    app.state.dashboard_sessions.throttle = lambda *args, **kwargs: None

    def _revoke(user_id, key=None):
        store = app.state.dashboard_sessions
        with store._lock:
            victims = [
                sid for sid, session in store._sessions.items()
                if session.user_id == user_id and (key is None or session.cache_key == key)
            ]
            for sid in victims:
                store._sessions.pop(sid, None)

    def _update_user(user_id, *, status, max_accounts, max_sessions, max_active_accounts, player_scout_access=None):
        current = fake_repo._users.get(user_id)
        if current is None:
            from fastapi import HTTPException
            raise HTTPException(404, 'user not found')
        fake_repo._users[user_id] = replace(
            current,
            status=status,
            max_accounts=max_accounts,
            max_sessions=max_sessions,
            max_active_accounts=max_active_accounts,
            player_scout_access=current.player_scout_access if player_scout_access is None else bool(player_scout_access),
            auth_version=current.auth_version + 1,
        )
        _revoke(user_id)

    app.state.dashboard_sessions.revoke = _revoke
    app.state.dashboard_sessions.update_user = _update_user
    app.state.admin_store = FakeAdminSecurityStore(fake_repo)
    import threading
    app.state.lifecycle_lock = threading.Lock()
    with TestClient(app) as client:
        yield client
