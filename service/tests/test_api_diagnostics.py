"""Diagnostics use an explicit test-local admin; member sessions are denied."""

from __future__ import annotations

from app.security.passwords import hash_password
from tests.test_api_actions import connect_and_wait
from tests.test_api_sessions import create_account


def test_raw_snapshot_before_connection_is_empty(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/raw-snapshot')
    assert response.status_code == 200
    assert response.json() == {'snapshot': {}}


def test_raw_snapshot_never_contains_secrets(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.get(f'/accounts/{account_id}/raw-snapshot')
    assert response.status_code == 200
    assert 'SECRET' not in response.text
    assert 'app_token' not in response.json()['snapshot']
    assert 'device_id' not in response.json()['snapshot']


def test_debug_capture_requires_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/debug-capture/start', json={'seconds': 5})
    assert response.status_code == 409


def test_debug_capture_start_and_stop(api_client, scripted_sockets, tmp_path, monkeypatch):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    start_response = api_client.post(f'/accounts/{account_id}/debug-capture/start', json={'seconds': 5})
    assert start_response.status_code == 200
    assert start_response.json()['started'] is True

    stop_response = api_client.post(f'/accounts/{account_id}/debug-capture/stop')
    assert stop_response.status_code == 200
    assert stop_response.json()['message_count'] >= 0


def test_debug_capture_download_without_a_capture_is_404(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/debug-capture/download')
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin gating (real dashboard auth active)
# ---------------------------------------------------------------------------

def test_explicit_admin_can_use_diagnostics(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'false')
    account_id = create_account(api_client)

    fake_repo.set_user_password('admin@example.com', password_hash=hash_password('correct horse battery staple'), role='admin')
    login = api_client.post('/auth/login', json={'email': 'admin@example.com', 'password': 'correct horse battery staple'})
    assert login.status_code == 200

    response = api_client.get(f'/accounts/{account_id}/raw-snapshot')
    assert response.status_code == 200  # admin role passes


def test_diagnostics_reject_non_admin_dashboard_sessions(api_client, fake_repo, monkeypatch):
    """A hypothetical non-admin dashboard user (this 3-person model doesn't
    create these, but the check must not silently trust any session)."""
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'false')
    account_id = create_account(api_client)

    fake_repo.set_user_password('viewer@example.com', password_hash=hash_password('correct horse battery staple'), role='member')
    login = api_client.post('/auth/login', json={'email': 'viewer@example.com', 'password': 'correct horse battery staple'})
    assert login.status_code == 200

    response = api_client.get(f'/accounts/{account_id}/raw-snapshot')
    assert response.status_code == 403
