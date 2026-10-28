"""Phase 3 PostgreSQL contract tests. TEST_DATABASE_URL MUST be disposable.
Drops/recreates tables. No game network or email calls are permitted.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Base, User, WebsiteSession, PilotGrant
from app.db.identity_store import PostgresIdentityStore, digest, now
from app.db.admin_store import AdminSecurityStore
from app.db.repository import SqlAlchemyAccountRepository
from app.db.session import build_engine, build_session_factory
from app.security.crypto import generate_key
from app.security.identity import AccountLimitReached, AccountUnavailable, IdentityConflict, canonical_identity
from app.security.passwords import hash_password, verify_password
from app.main import create_app
from tests.fakes import synthetic_account_manager as AccountManager
from app.core.link_challenge_store import LinkChallengeStore
from app.core.mass_deploy import MassDeployLock
from app.core.warpath.lilith import LinkSession

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='requires disposable PostgreSQL')
PASSWORD = 'synthetic-password-123'


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_MODE', 'session')
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'true')
    engine = build_engine(os.environ['TEST_DATABASE_URL'])
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    repo = SqlAlchemyAccountRepository(factory)
    store = PostgresIdentityStore(factory)
    users = {name: repo.set_user_password(f'{name}@example.com', password_hash=hash_password(PASSWORD), role=role)
             for name, role in [('alice', 'member'), ('bob', 'member'), ('admin', 'admin')]}
    yield store, repo, users
    Base.metadata.drop_all(engine)
    engine.dispose()


def login(store, user):
    return store.create(user_id=user.id, email=user.email, role=user.role, expected_password_hash=user.password_hash)


def account(repo, user, uid='70001'):
    return repo.create_account(owner_user_id=user.id, label='Synthetic', app_uid=uid,
                               app_token='synthetic-token', device_id='synthetic-device')


def relink_fields(uid='70001'):
    return dict(app_uid=uid, app_token='replacement-token', device_id='replacement-device',
                profile_uid=int(uid), platform=22, device_metadata={'os_type': 'win'}, linked_email='player@example.com')


def test_restart_revocation_hashes_and_session_ownership(identity):
    store, repo, users = identity
    a, b = login(store, users['alice']), login(store, users['bob'])
    restarted = PostgresIdentityStore(store.factory)
    assert restarted.get(a.session_id).cache_key == a.cache_key
    with store.factory() as db:
        row = db.get(WebsiteSession, digest(a.session_id))
        assert row.token_hash != a.session_id
    assert len(restarted.inventory(users['alice'].id, a.cache_key)) == 1
    with pytest.raises(HTTPException) as error:
        restarted.revoke(users['bob'].id, a.cache_key)
    assert error.value.status_code == 404
    restarted.destroy(a.session_id)
    assert store.get(a.session_id) is None
    assert store.get(b.session_id)
    restarted.revoke(users['bob'].id)
    assert store.get(b.session_id) is None


@pytest.mark.parametrize('field,value', [('role', None), ('role', 'owner'), ('status', 'disabled'), ('auth_version', 99)])
def test_current_identity_policy_is_authoritative(identity, field, value):
    store, _, users = identity
    session = login(store, users['alice'])
    with store.factory.begin() as db:
        setattr(db.get(User, users['alice'].id), field, value)
    assert store.get(session.session_id) is None
    if field != 'auth_version':
        with pytest.raises(HTTPException):
            login(store, users['alice'])
    else:
        assert login(store, users['alice'])  # fresh password login remains possible


def test_expiry_capacity_and_password_rotation(identity):
    store, repo, users = identity
    user = users['alice']
    with store.factory.begin() as db:
        db.get(User, user.id).max_sessions = 1
    first, second = login(store, user), login(store, user)
    assert store.get(first.session_id) is None
    assert store.get(second.session_id)
    with store.factory.begin() as db:
        db.get(WebsiteSession, digest(second.session_id)).last_used_at = now() - timedelta(hours=3)
    assert store.get(second.session_id) is None
    third = login(store, user)
    with store.factory.begin() as db:
        db.get(WebsiteSession, digest(third.session_id)).expires_at = now() - timedelta(seconds=1)
    assert store.get(third.session_id) is None
    fourth = login(store, user)
    repo.set_user_password(user.email, password_hash=hash_password('new-synthetic-password'), role='member')
    assert store.get(fourth.session_id) is None
    with pytest.raises(HTTPException):
        login(store, user)  # password verification vs rotation race


def test_invite_and_recovery_preserve_role_and_revoke(identity):
    store, repo, users = identity
    grant = store.issue_grant('PILOT@example.com', 'invite')
    pilot = repo.get_user_by_email('pilot@example.com')
    assert pilot.status == 'invited' and pilot.role == 'member' and pilot.password_hash is None
    with store.factory() as db:
        assert db.get(PilotGrant, digest(grant['token'])).token_hash != grant['token']
    store.redeem(grant['token'], PASSWORD)
    pilot = repo.get_user_by_email(pilot.email)
    assert pilot.status == 'active' and verify_password(PASSWORD, pilot.password_hash)
    with pytest.raises(HTTPException):
        store.redeem(grant['token'], PASSWORD)
    admin = users['admin']
    session = login(store, admin)
    recovery = store.issue_grant(admin.email, 'recovery')
    store.redeem(recovery['token'], 'replacement-password')
    assert repo.get_user_by_email(admin.email).role == 'admin'
    assert store.get(session.session_id) is None


@pytest.mark.parametrize('role,status', [(None, 'active'), ('owner', 'active'), ('member', 'disabled')])
def test_grants_cannot_elevate_or_enable_legacy_users(identity, role, status):
    store, _, users = identity
    with store.factory.begin() as db:
        user = db.get(User, users['alice'].id)
        user.role, user.status = role, status
    for kind in ['invite', 'recovery']:
        with pytest.raises(HTTPException):
            store.issue_grant(users['alice'].email, kind)


def test_grant_expiry_rotation_and_concurrent_single_consumption(identity):
    store, repo, users = identity
    first = store.issue_grant(users['alice'].email, 'recovery')
    second = store.issue_grant(users['alice'].email, 'recovery')
    with pytest.raises(HTTPException):
        store.redeem(first['token'], PASSWORD)
    def redeem():
        try:
            store.redeem(second['token'], PASSWORD)
            return 204
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: redeem(), range(2))) == [204, 400]
    expired = store.issue_grant(users['alice'].email, 'recovery')
    with store.factory.begin() as db:
        db.get(PilotGrant, digest(expired['token'])).expires_at = now() - timedelta(seconds=1)
    with pytest.raises(HTTPException):
        store.redeem(expired['token'], PASSWORD)


def test_canonical_identity_dedup_and_owner_bound_relink(identity):
    _, repo, users = identity
    a = account(repo, users['alice'], '00070001')
    repo.save_snapshot(a.id, {'synthetic': True})
    for user in [users['alice'], users['bob']]:
        with pytest.raises(IdentityConflict):
            account(repo, user, '70001')
    with pytest.raises(AccountUnavailable):
        repo.relink_account(a.id, owner_user_id=users['bob'].id, **relink_fields())
    with pytest.raises(IdentityConflict):
        repo.relink_account(a.id, owner_user_id=users['alice'].id, **relink_fields('70002'))
    updated = repo.relink_account(a.id, owner_user_id=users['alice'].id, **relink_fields())
    assert updated.id == a.id and updated.owner_user_id == a.owner_user_id
    assert repo.get_snapshot(a.id) == {'synthetic': True}
    assert repo.get_credentials(a.id).app_token == 'replacement-token'
    repo.update_account(a.id, status='restricted')
    with pytest.raises(AccountUnavailable):
        repo.relink_account(a.id, owner_user_id=users['alice'].id, **relink_fields())


def test_account_cap_under_concurrent_creation(identity):
    store, repo, users = identity
    with store.factory.begin() as db:
        db.get(User, users['alice'].id).max_accounts = 1
    def create(uid):
        try:
            account(repo, users['alice'], uid)
            return 'created'
        except AccountLimitReached:
            return 'limited'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, ['701', '702'])) == ['created', 'limited']
    assert len(repo.list_accounts(users['alice'].id)) == 1


def test_throttle_is_persistent_atomic_and_windowed(identity):
    store, _, _ = identity
    def attempt(_):
        try:
            PostgresIdentityStore(store.factory).throttle('test', 'synthetic', limit=2, seconds=60)
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(attempt, range(4))) == [200, 200, 429, 429]
    store.throttle('test', 'different', limit=2, seconds=60)


@pytest.fixture
def clients(identity, monkeypatch):
    store, repo, users = identity
    app = create_app(lifespan_context=None)
    app.state.repository = repo
    app.state.dashboard_sessions = store
    app.state.admin_store = AdminSecurityStore(store.factory)
    app.state.lifecycle_lock = threading.Lock()
    app.state.account_manager = AccountManager()
    app.state.link_challenges = LinkChallengeStore()
    app.state.mass_deploy_lock = MassDeployLock()
    for key, value in {'APP_UID': '500001', 'APP_TOKEN': 'synthetic-bootstrap', 'APP_ID': 'test',
                       'PACK_NAME': 'test', 'CHANNEL_ID': 'test', 'APP_VERSION': '1', 'PACKAGE_VERSION': '1', 'OS_TYPE': 'win'}.items():
        monkeypatch.setenv('WARPATH_' + key, value)
    # Hard mocks: every upstream operation must be synthetic.
    send = Mock(side_effect=lambda *args: args[2] or LinkSession.new())
    verify = Mock(return_value=('70001', 'synthetic-linked-token'))
    monkeypatch.setattr('app.api.link.lilith.send_login_code', send)
    monkeypatch.setattr('app.api.link.lilith.verify_login_code', verify)
    result = {}
    for name, user in users.items():
        session = login(store, user)
        client = TestClient(app, base_url='https://testserver')
        client.cookies.set('dashboard_session', session.session_id)
        client.cookies.set('dashboard_csrf', session.csrf_token)
        client.headers['x-csrf-token'] = session.csrf_token
        result[name] = client
    yield result, send, verify
    for client in result.values():
        client.close()
    app.state.account_manager.stop_all()


def test_http_link_relink_metadata_status_and_cross_owner(identity, clients, monkeypatch):
    store, repo, users = identity
    clients, send, verify = clients
    a = account(repo, users['alice'])
    for name in ['bob', 'admin']:
        assert clients[name].post('/accounts/link/request', json={'email': 'player@example.com', 'account_id': str(a.id)}).status_code == 404
    send.assert_not_called()
    alice = clients['alice']
    request = alice.post('/accounts/link/request', json={'email': 'player@example.com', 'account_id': str(a.id)})
    assert request.status_code == 202, request.text
    cid = request.json()['challenge_id']
    monkeypatch.setenv('WARPATH_APP_VERSION', 'CHANGED-AFTER-REQUEST')
    assert clients['bob'].post('/accounts/link/verify', json={'challenge_id': cid, 'code': '123456'}).status_code == 410
    verify.assert_not_called()
    response = alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '123456'})
    assert response.status_code == 201, response.text
    assert response.json()['id'] == str(a.id)
    assert repo.get_account(a.id).device_metadata['app_version'] == '1'
    assert alice.post(f'/accounts/{a.id}/status', json={'status': 'disabled'}).status_code == 403
    assert clients['admin'].post(f'/accounts/{a.id}/status', json={'status': 'disabled'}).status_code == 200
    assert alice.post(f'/accounts/{a.id}/connect').status_code == 409
    assert alice.post(f'/accounts/{a.id}/heartbeat').status_code == 409
    assert alice.get(f'/accounts/{a.id}').status_code == 200
    assert alice.post('/accounts/link/request', json={'email': 'player@example.com', 'account_id': str(a.id)}).status_code == 409


def test_http_provisioning_csrf_throttles_and_revocation(identity, clients):
    store, repo, users = identity
    clients, _, _ = clients
    alice, admin = clients['alice'], clients['admin']
    assert alice.post('/auth/pilot/grants', json={'email': 'pilot@example.com', 'kind': 'invite'}).status_code == 403
    grant = admin.post('/auth/pilot/grants', json={'email': 'pilot@example.com', 'kind': 'invite'})
    assert grant.status_code == 201 and grant.headers['cache-control'] == 'no-store'
    anon = TestClient(alice.app, base_url='https://testserver')
    assert anon.get('/accounts').status_code == 401
    assert anon.post('/auth/pilot/redeem', json={'token': grant.json()['token'], 'password': PASSWORD}).status_code == 204
    assert anon.get('/accounts').status_code == 401
    assert anon.post('/auth/login', json={'email': 'pilot@example.com', 'password': PASSWORD}).status_code == 200
    assert anon.get('/auth/me').json()['role'] == 'member'
    assert anon.post('/auth/revoke-all').status_code == 403  # no CSRF header
    assert alice.post('/auth/revoke-all').status_code == 204
    assert alice.get('/accounts').status_code == 401
    for _ in range(5):
        assert anon.post('/auth/login', json={'email': 'missing@example.com', 'password': 'wrong'}).status_code == 401
    assert anon.post('/auth/login', json={'email': 'missing@example.com', 'password': 'wrong'}, headers={'X-Forwarded-For': '203.0.113.2'}).status_code == 429
    anon.close()


def test_metadata_extra_fields_rejected_and_limits_before_lilith(identity, clients, monkeypatch):
    store, repo, users = identity
    clients, send, _ = clients
    alice = clients['alice']
    assert alice.post('/accounts/link/request', json={'email': 'x@example.com', 'server_ip': 'untrusted'}).status_code == 422
    monkeypatch.delenv('WARPATH_APP_VERSION')
    assert alice.post('/accounts/link/request', json={'email': 'x@example.com'}).status_code == 503
    send.assert_not_called()
    with store.factory.begin() as db:
        db.get(User, users['alice'].id).max_accounts = 1
    account(repo, users['alice'])
    assert alice.post('/accounts/link/request', json={'email': 'x@example.com'}).status_code == 409
    send.assert_not_called()


def test_user_policy_revokes_browsers_stops_games_and_preserves_role(identity, clients):
    _, repo, users = identity
    clients, _, _ = clients
    a = account(repo, users['alice'])
    admin = clients['admin']
    manager = admin.app.state.account_manager
    original_get = manager.get_account
    manager.get_account = Mock(return_value=Mock(is_active=True))
    manager.stop = Mock()
    policy = dict(status='disabled', max_accounts=3, max_sessions=2, max_active_accounts=1)
    path = f'/auth/pilot/users/{users["alice"].id}/policy'
    assert clients['bob'].post(path, json=policy).status_code == 403
    assert admin.post(path, json=policy).status_code == 204
    manager.stop.assert_called_once_with(str(a.id))
    assert clients['alice'].get('/accounts').status_code == 401
    assert repo.get_user_by_id(users['alice'].id).role == 'member'
    manager.get_account = original_get


def test_owner_active_limit_prevents_connect_and_reconnect_without_game_io(identity, clients):
    store, repo, users = identity
    clients, _, _ = clients
    a, b = account(repo, users['alice'], '701'), account(repo, users['alice'], '702')
    with store.factory.begin() as db:
        db.get(User, users['alice'].id).max_active_accounts = 1
    manager = clients['alice'].app.state.account_manager
    original_get = manager.get_account
    manager.get_account = Mock(side_effect=lambda key: Mock(is_active=True) if key == str(a.id) else None)
    manager.start = Mock(side_effect=AssertionError('must reject before game start'))
    manager.reconnect = Mock(side_effect=AssertionError('must reject before reconnect'))
    for endpoint in ['connect', 'reconnect']:
        assert clients['alice'].post(f'/accounts/{b.id}/{endpoint}').status_code == 409
    manager.start.assert_not_called()
    manager.reconnect.assert_not_called()
    manager.get_account = original_get


def test_concurrent_cross_owner_identity_claim_has_one_winner(identity):
    _, repo, users = identity
    def claim(user):
        try:
            return account(repo, user, '999').id
        except IdentityConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [users['alice'], users['bob']]))
    assert sum(x is not None for x in results) == 1
    assert len(repo.list_accounts()) == 1


def test_link_throttle_and_pending_cap_before_email(identity, clients):
    _, _, _ = identity
    clients, send, _ = clients
    alice = clients['alice']
    for index in range(3):
        assert alice.post('/accounts/link/request', json={'email': f'player{index}@example.com'}).status_code == 202
    assert alice.post('/accounts/link/request', json={'email': 'player4@example.com'}).status_code == 429
    assert send.call_count == 3


@pytest.mark.parametrize('raw,expected', [(' 00012 ', 'warpath:lilith:12'), ('\t12', None), ('12\n', None), ('１２', None), ('000', None), ('abc', None)])
def test_canonical_python_and_postgres_agree(identity, raw, expected):
    from sqlalchemy import text
    from app.security.identity import CANONICAL_SQL
    store, _, _ = identity
    with store.factory() as db:
        actual = db.scalar(text(f'SELECT {CANONICAL_SQL} FROM (SELECT cast(:uid as text) AS app_uid) identity_input'), {'uid': raw})
    assert actual == canonical_identity(raw) == expected


@pytest.mark.parametrize('status', ['disabled', 'restricted', 'needs_reauth'])
def test_late_game_auth_failure_cannot_weaken_operator_policy(identity, status):
    _, repo, users = identity
    a = account(repo, users['alice'])
    repo.update_account(a.id, status=status)
    repo.mark_account_auth_failure(a.id, restricted=False)
    assert repo.get_account(a.id).status == status


def test_command_report_uses_durable_revocation_owner_and_role_policy(identity, clients):
    store, repo, users = identity
    clients, send, verify = clients
    a = account(repo, users['alice'])
    path = f'/accounts/{a.id}/command-status'
    assert clients['alice'].get(path).status_code == 200
    assert clients['bob'].get(path).status_code == 403
    assert clients['admin'].get(path).status_code == 200
    # Website sessions survive restart; empty game history is explicitly unknown.
    clients['alice'].app.state.dashboard_sessions = PostgresIdentityStore(store.factory)
    body = clients['alice'].get(path).json()
    assert body['history_complete'] is False and body['observation_id'] is None
    repo.update_account(a.id, status='restricted')
    assert clients['alice'].get(path).status_code == 200
    store.destroy(clients['alice'].cookies.get('dashboard_session'))
    assert clients['alice'].get(path).status_code == 401
    with store.factory.begin() as db:
        db.get(User, users['admin'].id).role = None
    assert clients['admin'].get(path).status_code == 401
    send.assert_not_called(); verify.assert_not_called()


@pytest.mark.parametrize('invalid_role', [None, 'owner'])
def test_pilot_activation_durable_auth_status_restart(identity, clients, invalid_role):
    from app.core.account_manager import AccountManager as GuardedManager
    store, repo, users = identity
    clients, send, verify = clients
    app = clients['admin'].app
    app.state.account_manager = GuardedManager()
    a = account(repo, users['alice'])
    path = f'/accounts/{a.id}/pilot-activation'
    assert clients['alice'].post(path, json={'mode': 'observe'}).status_code == 403
    assert clients['bob'].get(path).status_code == 403
    assert clients['admin'].post(path, json={'mode': 'observe', 'minutes': 1}).status_code == 200
    assert clients['alice'].get(path).json()['mode'] == 'observe'
    # Same durable website sessions, entirely new process-local manager/grants.
    app.state.dashboard_sessions = PostgresIdentityStore(store.factory)
    app.state.account_manager = GuardedManager()
    assert clients['alice'].get(path).json()['mode'] == 'off'
    assert clients['alice'].post(f'/accounts/{a.id}/connect').status_code == 409
    repo.update_account(a.id, status='restricted')
    assert clients['admin'].post(path, json={'mode': 'observe'}).status_code == 409
    assert clients['alice'].get(path).status_code == 200
    repo.update_account(a.id, status='active')
    with store.factory.begin() as db:
        db.get(User, users['admin'].id).role = invalid_role
    assert clients['admin'].post(path, json={'mode': 'observe'}).status_code == 401
    store.destroy(clients['alice'].cookies.get('dashboard_session'))
    assert clients['alice'].get(path).status_code == 401
    send.assert_not_called()
    verify.assert_not_called()


def test_pilot_user_policy_revokes_unconnected_grants(identity, clients):
    from app.core.account_manager import AccountManager as GuardedManager
    store, repo, users = identity
    clients, send, verify = clients
    manager = clients['admin'].app.state.account_manager = GuardedManager()
    a = account(repo, users['alice'])
    manager.pilot.activate(str(a.id), str(users['admin'].id), 1)
    body = {'status': 'disabled', 'max_accounts': 5, 'max_sessions': 5, 'max_active_accounts': 2}
    response = clients['admin'].post(f'/auth/pilot/users/{users["alice"].id}/policy', json=body)
    assert response.status_code == 204
    assert manager.pilot.status(str(a.id))['mode'] == 'off'
    assert clients['alice'].get(f'/accounts/{a.id}/pilot-activation').status_code == 401
    assert clients['admin'].post(f'/accounts/{a.id}/pilot-activation', json={'mode': 'observe'}).status_code == 409
    send.assert_not_called()
    verify.assert_not_called()


def test_real_lifespan_registers_without_connecting_or_activating(identity, monkeypatch, scripted_sockets):
    from app.main import lifespan
    store, repo, users = identity
    a = account(repo, users['alice'])
    monkeypatch.setenv('AUTOSTART_ACTIVE_ACCOUNTS', 'false')
    monkeypatch.setenv('INTERNAL_PROXY_TOKEN', 'lifespan-test-internal-proxy-token-32-plus')
    monkeypatch.setattr('app.main.build_engine', lambda: build_engine(os.environ['TEST_DATABASE_URL']))
    sockets = scripted_sockets([])  # any game connection fails this rehearsal
    for _ in range(2):
        with TestClient(create_app(lifespan_context=lifespan)) as client:
            manager = client.app.state.account_manager
            assert manager.get_account(str(a.id)) is not None
            assert manager.list_active() == []
            assert manager.pilot.status(str(a.id))['mode'] == 'off'
            assert manager.get_account(str(a.id)).connection.pilot_policy is manager.pilot
            manager.pilot.activate(str(a.id), str(users['admin'].id), 1)
        assert manager.pilot.status(str(a.id))['mode'] == 'off'
    assert sockets.created == []
