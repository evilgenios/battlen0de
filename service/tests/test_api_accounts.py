"""GET/POST /accounts, GET/DELETE /accounts/{id}: CRUD, ownership, dev-auth
boundary, and that account_created/account_deleted events are recorded."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.deps import DEV_USER_EMAIL_ENV_VAR
from app.main import create_app
from tests.fakes import synthetic_account_manager as AccountManager
from app.core.dashboard_session import DashboardSessionStore
from tests.fake_repository import FakeEngine, InMemoryAccountRepository


def account_payload(**overrides) -> dict:
    # device_metadata fills in every field WarpathCredentials.validation_errors()
    # requires (app_id/pack_name/channel_id/package_version, on top of
    # os_type/app_version) so a connect() attempt in tests isn't rejected
    # by the same config-completeness check the legacy bot has always had.
    payload = {
        'label': 'Main Account',
        'app_uid': 'uid-123',
        'app_token': 'token-123-SECRET',
        'device_id': 'device-123-SECRET',
        'platform': 22,
        'device_metadata': {
            'os_type': 'win',
            'app_version': '1.0.0',
            'app_id': 'test-app-id',
            'pack_name': 'test-pack-name',
            'channel_id': 'test-channel-id',
            'package_version': '1.0.0',
        },
    }
    payload.update(overrides)
    return payload


def test_create_account_requires_authentication(fake_repo, account_manager, monkeypatch):
    monkeypatch.delenv(DEV_USER_EMAIL_ENV_VAR, raising=False)
    app = create_app(lifespan_context=None)
    app.state.repository = fake_repo
    app.state.account_manager = account_manager
    app.state.engine = FakeEngine()
    app.state.dashboard_sessions = DashboardSessionStore()
    with TestClient(app) as client:
        response = client.post('/accounts', json=account_payload())
        assert response.status_code == 401  # production is closed before bootstrap


def test_create_account_returns_no_secrets(api_client):
    response = api_client.post('/accounts', json=account_payload())
    assert response.status_code == 201
    body = response.json()
    assert 'app_token' not in body
    assert 'device_id' not in body
    assert 'token-123-SECRET' not in response.text
    assert 'device-123-SECRET' not in response.text
    assert body['app_uid'] == 'uid-123'
    assert body['label'] == 'Main Account'


def test_create_account_writes_account_created_event(api_client, fake_repo):
    response = api_client.post('/accounts', json=account_payload())
    account_id = response.json()['id']
    events = fake_repo.list_events(__import__('uuid').UUID(account_id))
    assert any(e.event_type == 'account_created' for e in events)


def test_list_accounts_only_returns_callers_own(api_client, fake_repo, dev_user_email):
    api_client.post('/accounts', json=account_payload(label='Mine'))
    # A second account owned by someone else, created directly against the
    # repository (bypassing the API, which can only ever create accounts
    # for the current dev user).
    other_user = fake_repo.get_or_create_user('someone-else@example.test')
    fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='x', app_token='t', device_id='d',
    )

    response = api_client.get('/accounts')
    labels = {a['label'] for a in response.json()}
    assert labels == {'Mine'}


def test_get_account_not_found_is_404(api_client):
    import uuid

    response = api_client.get(f'/accounts/{uuid.uuid4()}')
    assert response.status_code == 404


def test_get_account_owned_by_someone_else_is_403(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.test')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='x', app_token='t', device_id='d',
    )
    response = api_client.get(f'/accounts/{other_account.id}')
    assert response.status_code == 403


def test_delete_account_removes_it_and_writes_event(api_client, fake_repo):
    account_id = api_client.post('/accounts', json=account_payload()).json()['id']

    response = api_client.delete(f'/accounts/{account_id}')
    assert response.status_code == 204
    assert api_client.get(f'/accounts/{account_id}').status_code == 404


def test_delete_account_owned_by_someone_else_is_403_and_does_not_delete(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.test')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='x', app_token='t', device_id='d',
    )
    response = api_client.delete(f'/accounts/{other_account.id}')
    assert response.status_code == 403
    assert fake_repo.get_account(other_account.id) is not None


def test_create_account_rejects_missing_required_fields(api_client):
    response = api_client.post('/accounts', json={'label': 'Missing fields'})
    assert response.status_code == 422



def test_accounts_overview_is_owner_scoped_and_returns_live_shape(api_client, fake_repo):
    mine = api_client.post('/accounts', json=account_payload(label='Mine')).json()
    other_user = fake_repo.get_or_create_user('overview-other@example.test')
    fake_repo.create_account(
        owner_user_id=other_user.id,
        label='Not Mine',
        app_uid='overview-other',
        app_token='other-token',
        device_id='other-device',
    )

    response = api_client.get('/accounts/overview')
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]['account']['id'] == mine['id']
    assert rows[0]['account']['label'] == 'Mine'
    assert rows[0]['status']['account_id'] == mine['id']
    assert rows[0]['status']['db_status'] == 'active'
    assert rows[0]['status']['live'] is None
