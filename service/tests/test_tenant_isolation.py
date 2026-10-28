"""Phase 2 security regressions: two members and an admin, synthetic only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.warpath.lilith import LilithLoginError, LinkSession
from app.main import create_app
from app.security.passwords import hash_password
from tests.test_api_accounts import account_payload


@pytest.fixture
def principals(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_MODE', 'session')
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'true')
    result = {}
    for name, role in [('alice', 'member'), ('bob', 'member'), ('operator', 'admin')]:
        user = fake_repo.get_or_create_user(f'{name}@example.test')
        session = api_client.app.state.dashboard_sessions.create(user_id=user.id, email=user.email, role=role)
        client = TestClient(api_client.app, base_url='https://testserver')
        client.cookies.set('dashboard_session', session.session_id)
        client.cookies.set('dashboard_csrf', session.csrf_token)
        client.headers['x-csrf-token'] = session.csrf_token
        result[name] = (client, user)
    yield result
    for client, _ in result.values():
        client.close()


@pytest.fixture
def linking(monkeypatch):
    monkeypatch.setenv('WARPATH_APP_UID', '500000123')
    monkeypatch.setenv('WARPATH_APP_TOKEN', 'synthetic-operator-token')
    send = Mock(side_effect=lambda *args: args[2] or LinkSession.new())
    verify = Mock(return_value=('700001', 'synthetic-linked-token'))
    monkeypatch.setattr('app.api.link.lilith.send_login_code', send)
    monkeypatch.setattr('app.api.link.lilith.verify_login_code', verify)
    return send, verify


def stored_account(repo, user):
    return repo.create_account(owner_user_id=user.id, label='Synthetic account', app_uid='900001',
                               app_token='synthetic-customer-token', device_id='synthetic-device')


def test_anonymous_production_denied_without_password_users(api_client, principals, fake_repo):
    assert not fake_repo.list_dashboard_users()
    for method, path in [('GET', '/accounts'), ('POST', '/accounts'), ('POST', '/accounts/link/request'),
                         ('POST', '/accounts/mass-deploy/cancel'), ('GET', '/auth/me')]:
        assert api_client.request(method, path, json={}).status_code == 401
    assert api_client.get('/health').json()['auth_required'] is True


@pytest.mark.parametrize('mode,environment,secure', [('local', 'production', 'true'),
    ('typo', 'production', 'true'), ('session', 'staging', 'true'), ('session', 'production', 'false')])
def test_production_rejects_unsafe_configuration(monkeypatch, mode, environment, secure):
    monkeypatch.setenv('AUTH_MODE', mode)
    monkeypatch.setenv('APP_ENV', environment)
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', secure)
    with pytest.raises(RuntimeError):
        create_app(lifespan_context=None)


def test_explicit_local_mode_defaults_to_member(api_client, monkeypatch):
    monkeypatch.delenv('DEV_USER_ROLE')
    assert api_client.get('/auth/me').json()['role'] == 'member'
    assert api_client.get('/accounts').status_code == 200
    assert api_client.post('/accounts', json=account_payload()).status_code == 403
    assert api_client.post('/accounts/mass-deploy/cancel').status_code == 403


@pytest.mark.parametrize('role', [None, '', 'viewer', 'ADMIN', 'owner'])
def test_invalid_roles_cannot_login_or_authorize_existing_session(api_client, principals, fake_repo, role):
    user = fake_repo.set_user_password('invalid@example.test', password_hash=hash_password('synthetic-password'), role=role)
    assert api_client.post('/auth/login', json={'email': user.email, 'password': 'synthetic-password'}).status_code == 401
    session = api_client.app.state.dashboard_sessions.create(user_id=user.id, email=user.email, role=role)
    api_client.cookies.set('dashboard_session', session.session_id)
    assert api_client.get('/accounts').status_code == 403
    assert api_client.app.state.dashboard_sessions.get(session.session_id) is None


@pytest.mark.parametrize('method,suffix', [('GET', ''), ('DELETE', ''), ('GET', '/status'),
    ('GET', '/events'), ('GET', '/command-status'), ('GET', '/summary'), ('GET', '/vehicles'), ('GET', '/active-actions'),
    ('GET', '/production'), ('GET', '/armies'), ('GET', '/army-groups'), ('GET', '/skins'),
    ('GET', '/map-objects'), ('GET', '/profile/123'), ('GET', '/locate-bases/123'),
    ('GET', '/conquest-guard'), ('POST', '/connect'), ('POST', '/disconnect'), ('POST', '/reconnect'),
    ('POST', '/collect'), ('POST', '/scan'), ('POST', '/farm'), ('POST', '/recall'),
    ('POST', '/recall-all'), ('POST', '/scout'), ('POST', '/refresh'), ('POST', '/heartbeat'),
    ('POST', '/army-groups/refresh'), ('POST', '/army-groups/1/join'), ('POST', '/army-groups/leave'),
    ('POST', '/profile/123/refresh'), ('POST', '/locate-bases'),
    ('POST', '/conquest-guard/enable'), ('POST', '/conquest-guard/disable')])
def test_cross_owner_routes_denied_before_actions(principals, fake_repo, method, suffix):
    alice, owner = principals['alice']
    bob, _ = principals['bob']
    account = stored_account(fake_repo, owner)
    assert alice.get(f'/accounts/{account.id}').status_code == 200
    assert bob.request(method, f'/accounts/{account.id}{suffix}', json={}).status_code == 403
    assert fake_repo.get_account(account.id) is not None


def test_list_is_owner_scoped_and_admin_override_is_explicit(principals, fake_repo):
    alice, owner = principals['alice']
    bob, other = principals['bob']
    admin, _ = principals['operator']
    a, b = stored_account(fake_repo, owner), stored_account(fake_repo, other)
    assert [x['id'] for x in alice.get('/accounts').json()] == [str(a.id)]
    assert [x['id'] for x in bob.get('/accounts').json()] == [str(b.id)]
    assert admin.get(f'/accounts/{a.id}').status_code == 200
    assert admin.post('/accounts', json=account_payload()).status_code == 201
    assert admin.get(f'/accounts/{a.id}/raw-snapshot').status_code == 200
    assert admin.post('/accounts/mass-deploy/cancel').status_code == 200


@pytest.mark.parametrize('method,path', [('POST', '/accounts'), ('POST', '/accounts/mass-deploy'),
    ('POST', '/accounts/mass-deploy/cancel'), ('GET', '/accounts/{id}/raw-snapshot'),
    ('GET', '/accounts/{id}/debug-capture/download'), ('POST', '/accounts/{id}/debug-capture/start'),
    ('POST', '/accounts/{id}/debug-capture/stop')])
def test_internal_routes_denied_even_for_member_owner(principals, fake_repo, method, path):
    alice, owner = principals['alice']
    account = stored_account(fake_repo, owner)
    assert alice.request(method, path.format(id=account.id), json={}).status_code == 403


def test_cross_user_challenges_cannot_resend_attempt_verify_delete(principals, linking, link_challenge_store):
    alice, owner = principals['alice']
    bob, _ = principals['bob']
    admin, _ = principals['operator']
    cid = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()['challenge_id']
    for other in [bob, admin]:  # No admin override for linking challenges.
        assert other.post('/accounts/link/request', json={'email': 'player@example.com', 'challenge_id': cid}).status_code == 410
        assert other.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '123456'}).status_code == 410
        assert other.delete(f'/accounts/link/{cid}').status_code == 410
    assert linking[0].call_count == 1
    linking[1].assert_not_called()
    assert link_challenge_store.get(cid, owner.id).attempts == 0
    assert alice.delete(f'/accounts/link/{cid}').status_code == 204


def test_same_email_request_does_not_reuse_another_users_challenge(principals, linking):
    alice, _ = principals['alice']
    bob, _ = principals['bob']
    first = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()
    second = bob.post('/accounts/link/request', json={'email': 'player@example.com'}).json()
    assert first['challenge_id'] != second['challenge_id']


def test_no_customer_credentials_are_selected_for_linking(principals, fake_repo, linking, monkeypatch):
    alice, owner = principals['alice']
    _, other = principals['bob']
    stored_account(fake_repo, other)
    stored_account(fake_repo, owner)
    for name in ['WARPATH_APP_UID', 'WARPATH_APP_TOKEN']:
        monkeypatch.delenv(name)
    monkeypatch.setattr(fake_repo, 'get_credentials', Mock(side_effect=AssertionError('must not read customer credentials')))
    response = alice.post('/accounts/link/request', json={'email': 'player@example.com'})
    assert response.status_code == 503
    assert 'operator must configure' in response.text
    linking[0].assert_not_called()


def test_concurrent_verification_completes_once(principals, fake_repo, linking):
    alice, owner = principals['alice']
    entered, release = Event(), Event()
    def blocking_verify(*args):
        entered.set()
        assert release.wait(5)
        return '700001', 'synthetic-linked-token'
    linking[1].side_effect = blocking_verify
    cid = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()['challenge_id']
    body = {'challenge_id': cid, 'code': '123456'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(alice.post, '/accounts/link/verify', json=body)
        try:
            assert entered.wait(5)
            second = alice.post('/accounts/link/verify', json=body)
            assert second.status_code == 409
        finally:
            release.set()
        assert first.result().status_code == 201
    assert linking[1].call_count == 1
    accounts = fake_repo.list_accounts(owner_user_id=owner.id)
    assert len(accounts) == 1
    assert alice.post('/accounts/link/verify', json=body).status_code == 410


@pytest.mark.parametrize('exception', [LilithLoginError, RuntimeError])
def test_upstream_code_never_echoed_persisted_or_logged(principals, linking, fake_repo, caplog, exception):
    alice, _ = principals['alice']
    cid = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()['challenge_id']
    linking[1].side_effect = exception('code=654321 synthetic-operator-token')
    response = alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '654321'})
    assert response.status_code in (422, 503)
    for text in [response.text, str(fake_repo._events), caplog.text]:
        assert '654321' not in text
        assert 'synthetic-operator-token' not in text
    invalid = alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': 'sensitive-invalid-code'})
    assert invalid.status_code == 422
    assert 'sensitive-invalid-code' not in invalid.text


def test_logout_requires_csrf_and_member_session_count_is_private(principals):
    alice, _ = principals['alice']
    assert alice.get('/auth/me').json()['active_sessions'] == 1
    assert principals['operator'][0].get('/auth/me').json()['active_sessions'] == 3
    assert alice.post('/auth/logout', headers={'x-csrf-token': 'wrong'}).status_code == 403
    assert alice.post('/auth/logout').status_code == 204
    assert alice.get('/accounts').status_code == 401


def test_failed_event_write_cannot_log_upstream_code(principals, linking, fake_repo, caplog, monkeypatch):
    alice, _ = principals['alice']
    cid = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()['challenge_id']
    linking[1].side_effect = LilithLoginError('verification code 654321')
    monkeypatch.setattr(fake_repo, 'add_event', Mock(side_effect=RuntimeError('synthetic DB unavailable')))
    # TestClient rethrows server errors after the app's exception handler logs them.
    with pytest.raises(RuntimeError):
        alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '654321'})
    assert '654321' not in caplog.text


def test_failed_account_write_does_not_replay_successful_verification(principals, linking, fake_repo, monkeypatch):
    alice, _ = principals['alice']
    cid = alice.post('/accounts/link/request', json={'email': 'player@example.com'}).json()['challenge_id']
    monkeypatch.setattr(fake_repo, 'create_account', Mock(side_effect=RuntimeError('synthetic DB unavailable')))
    with pytest.raises(RuntimeError):
        alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '123456'})
    assert alice.post('/accounts/link/verify', json={'challenge_id': cid, 'code': '123456'}).status_code == 410
    assert linking[1].call_count == 1


def test_dotenv_configuration_checked_before_startup_io(monkeypatch):
    import asyncio
    import app.main as main
    def load_unsafe():
        monkeypatch.setenv('APP_ENV', 'production')
        monkeypatch.setenv('AUTH_MODE', 'local')
        monkeypatch.setenv('INTERNAL_PROXY_TOKEN', 'unsafe-config-test-proxy-token-32-plus')
    monkeypatch.setattr(main, '_load_local_dotenv', load_unsafe)
    engine = Mock(side_effect=AssertionError('must not reach DB'))
    monkeypatch.setattr(main, 'build_engine', engine)
    async def start():
        async with main.lifespan(create_app(lifespan_context=None)):
            pytest.fail('unsafe configuration started')
    with pytest.raises(RuntimeError, match='Production rejects'):
        asyncio.run(start())
    engine.assert_not_called()
