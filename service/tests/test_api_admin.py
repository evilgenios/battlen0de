from __future__ import annotations

import uuid

from app.security.passwords import hash_password


def _create_base(api_client, *, label='Admin Visible Base', app_uid='123456'):
    response = api_client.post('/accounts', json={
        'label': label,
        'app_uid': app_uid,
        'app_token': 'ADMIN-TEST-SECRET-TOKEN',
        'device_id': 'ADMIN-TEST-SECRET-DEVICE',
    })
    assert response.status_code == 201
    return response.json()


def test_admin_summary_and_customer_inventory(api_client, fake_repo):
    response = api_client.get('/admin/summary')
    assert response.status_code == 200
    assert response.json()['users_total'] >= 1

    users = api_client.get('/admin/users')
    assert users.status_code == 200
    assert any(row['email'] == 'dev-user@example.test' for row in users.json())


def test_admin_account_inventory_never_returns_saved_game_secrets(api_client):
    _create_base(api_client)
    response = api_client.get('/admin/accounts')
    assert response.status_code == 200
    assert 'ADMIN-TEST-SECRET-TOKEN' not in response.text
    assert 'ADMIN-TEST-SECRET-DEVICE' not in response.text
    assert response.json()[0]['app_uid'] == '123456'


def test_member_cannot_enter_admin_control_center(api_client, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    assert api_client.get('/admin/summary').status_code == 403
    assert api_client.get('/admin/users').status_code == 403
    assert api_client.get('/admin/accounts').status_code == 403
    assert api_client.get('/admin/audit').status_code == 403


def test_admin_can_disable_base_and_disconnect_runtime(api_client):
    base = _create_base(api_client)
    response = api_client.patch(f"/admin/accounts/{base['id']}", json={'status': 'disabled'})
    assert response.status_code == 200
    assert response.json()['status'] == 'disabled'


def test_admin_can_change_customer_limits(api_client, fake_repo):
    customer = fake_repo.set_user_password(
        'customer@example.test',
        password_hash=hash_password('synthetic-password-for-admin-test'),
        role='member',
    )
    response = api_client.patch(
        f'/admin/users/{customer.id}',
        json={
            'status': 'active',
            'max_accounts': 12,
            'max_sessions': 4,
            'max_active_accounts': 3,
            'player_scout_access': True,
        },
    )
    assert response.status_code == 200
    assert response.json()['max_accounts'] == 12
    assert response.json()['plan'] == 'alliance'
    assert response.json()['player_scout_access'] is True


def test_internal_proxy_token_blocks_direct_backend_requests(api_client, monkeypatch):
    monkeypatch.setenv('INTERNAL_PROXY_TOKEN', 'synthetic-internal-proxy-token')
    blocked = api_client.get('/accounts')
    assert blocked.status_code == 403

    allowed = api_client.get(
        '/accounts',
        headers={'x-battlenode-internal-token': 'synthetic-internal-proxy-token'},
    )
    assert allowed.status_code == 200

    # Health remains usable for infrastructure readiness probes.
    assert api_client.get('/health').status_code == 200
