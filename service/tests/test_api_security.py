"""Explicit sweep: the secret values used to create an account must never
appear in ANY API response — success or error — across every endpoint."""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import wait_until
from tests.fakes import FakeWarpathSocket, build_login_reply_frame

SECRET_TOKEN = 'THIS-APP-TOKEN-MUST-NEVER-LEAK-1234567890'
SECRET_DEVICE_ID = 'THIS-DEVICE-ID-MUST-NEVER-LEAK-0987654321'


def _create_account_with_distinctive_secrets(api_client) -> str:
    response = api_client.post('/accounts', json={
        'label': 'Secret Sweep Account',
        'app_uid': 'uid-secret-sweep',
        'app_token': SECRET_TOKEN,
        'device_id': SECRET_DEVICE_ID,
        'device_metadata': {
            'os_type': 'win', 'app_version': '1.0.0', 'app_id': 'test-app-id',
            'pack_name': 'test-pack-name', 'channel_id': 'test-channel-id', 'package_version': '1.0.0',
        },
    })
    assert response.status_code == 201
    return response.json()['id']


def _assert_no_secrets(response) -> None:
    assert SECRET_TOKEN not in response.text
    assert SECRET_DEVICE_ID not in response.text


def test_secrets_never_appear_in_create_response(api_client):
    response = api_client.post('/accounts', json={
        'label': 'X', 'app_uid': 'uid', 'app_token': SECRET_TOKEN, 'device_id': SECRET_DEVICE_ID,
    })
    _assert_no_secrets(response)


def test_secrets_never_appear_in_list_or_get(api_client):
    account_id = _create_account_with_distinctive_secrets(api_client)
    _assert_no_secrets(api_client.get('/accounts'))
    _assert_no_secrets(api_client.get(f'/accounts/{account_id}'))


def test_secrets_never_appear_in_session_status_or_connect_response(api_client, scripted_sockets):
    account_id = _create_account_with_distinctive_secrets(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])

    _assert_no_secrets(api_client.post(f'/accounts/{account_id}/connect'))
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )
    _assert_no_secrets(api_client.get(f'/accounts/{account_id}/status'))
    _assert_no_secrets(api_client.post(f'/accounts/{account_id}/disconnect'))


def test_secrets_never_appear_in_action_responses(api_client, scripted_sockets):
    account_id = _create_account_with_distinctive_secrets(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
    api_client.post(f'/accounts/{account_id}/connect')
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )
    _assert_no_secrets(api_client.post(f'/accounts/{account_id}/collect'))
    _assert_no_secrets(api_client.post(f'/accounts/{account_id}/scan', json={}))


def test_secrets_never_appear_in_404_403_409_422_error_bodies(api_client, fake_repo, dev_user_email, monkeypatch):
    account_id = _create_account_with_distinctive_secrets(api_client)

    # 404: unknown account.
    _assert_no_secrets(api_client.get(f'/accounts/{uuid.uuid4()}'))

    # 403: a real account owned by someone else, with its own distinct
    # secrets, must not leak either.
    other_user = fake_repo.get_or_create_user('someone-else@example.test')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='x',
        app_token='OTHER-ACCOUNT-SECRET-TOKEN', device_id='OTHER-ACCOUNT-SECRET-DEVICE',
    )
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    forbidden = api_client.get(f'/accounts/{other_account.id}')
    assert forbidden.status_code == 403
    assert 'OTHER-ACCOUNT-SECRET-TOKEN' not in forbidden.text
    assert 'OTHER-ACCOUNT-SECRET-DEVICE' not in forbidden.text

    # 409: invalid lifecycle operation (not connected yet).
    _assert_no_secrets(api_client.post(f'/accounts/{account_id}/disconnect'))

    # 422: incomplete credentials on a DIFFERENT account (empty secrets, so
    # nothing to leak, but confirms the validation-error path stays clean).
    user = fake_repo.get_or_create_user(dev_user_email)
    incomplete = fake_repo.create_account(
        owner_user_id=user.id, label='Incomplete', app_uid='', app_token='', device_id='',
    )
    _assert_no_secrets(api_client.post(f'/accounts/{incomplete.id}/connect'))


def test_secrets_never_appear_in_events_list(api_client, scripted_sockets):
    account_id = _create_account_with_distinctive_secrets(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
    api_client.post(f'/accounts/{account_id}/connect')
    wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )
    _assert_no_secrets(api_client.get(f'/accounts/{account_id}/events'))


def test_account_response_schema_has_no_secret_fields(api_client):
    from app.schemas.accounts import AccountResponse

    field_names = set(AccountResponse.model_fields.keys())
    assert 'app_token' not in field_names
    assert 'device_id' not in field_names


def test_production_requires_strong_internal_proxy_token(monkeypatch):
    from app.main import _validate_internal_proxy_configuration

    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('INTERNAL_PROXY_TOKEN', raising=False)
    with pytest.raises(RuntimeError, match='INTERNAL_PROXY_TOKEN'):
        _validate_internal_proxy_configuration()

    monkeypatch.setenv('INTERNAL_PROXY_TOKEN', 'launch-test-proxy-token-with-32-plus-chars')
    _validate_internal_proxy_configuration()


def test_production_disables_interactive_api_docs(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.fake_repository import FakeEngine, InMemoryAccountRepository
    from tests.fakes import synthetic_account_manager as AccountManager
    from app.core.dashboard_session import DashboardSessionStore

    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_MODE', 'session')
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'true')
    monkeypatch.setenv('INTERNAL_PROXY_TOKEN', 'test-internal-proxy-token-at-least-32-chars')

    app = create_app(lifespan_context=None)
    app.state.repository = InMemoryAccountRepository()
    app.state.account_manager = AccountManager()
    app.state.engine = FakeEngine(healthy=True)
    app.state.dashboard_sessions = DashboardSessionStore()

    headers = {'x-battlenode-internal-token': 'test-internal-proxy-token-at-least-32-chars'}
    with TestClient(app) as client:
        assert client.get('/docs', headers=headers).status_code == 404
        assert client.get('/redoc', headers=headers).status_code == 404
        assert client.get('/openapi.json', headers=headers).status_code == 404
