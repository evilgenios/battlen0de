"""Conquest Guard enable/disable/status — state lives on WarpathConnection,
one instance per account, so this suite explicitly proves it never leaks
between two different accounts' connections."""

from __future__ import annotations

from tests.test_api_actions import connect_and_wait
from tests.test_api_sessions import create_account
from tests.test_api_accounts import account_payload


def test_status_before_any_connection_is_disabled(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/conquest-guard')
    assert response.status_code == 200
    assert response.json() == {
        'enabled': False, 'armed_uid': 0, 'connected_uid': None,
        'in_progress': False, 'attempts': 0, 'last_attack': None, 'last_result': None,
    }


def test_enable_requires_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/conquest-guard/enable')
    assert response.status_code == 409


def test_enable_arms_the_currently_logged_in_uid(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    response = api_client.post(f'/accounts/{account_id}/conquest-guard/enable')
    assert response.status_code == 200
    body = response.json()
    assert body['enabled'] is True
    assert body['armed_uid'] > 0
    assert body['armed_uid'] == body['connected_uid']


def test_disable_clears_the_armed_state(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    api_client.post(f'/accounts/{account_id}/conquest-guard/enable')

    response = api_client.post(f'/accounts/{account_id}/conquest-guard/disable')
    assert response.status_code == 200
    body = response.json()
    assert body['enabled'] is False
    assert body['armed_uid'] == 0


def test_guard_state_never_leaks_between_two_accounts(api_client, scripted_sockets):
    from tests.fakes import FakeWarpathSocket, build_login_reply_frame

    account_a = create_account(api_client)
    account_b = api_client.post('/accounts', json=account_payload(label='Second', app_uid='uid-456')).json()['id']

    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])
    api_client.post(f'/accounts/{account_a}/connect')
    api_client.post(f'/accounts/{account_b}/connect')

    from tests.conftest import wait_until
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_a}/status').json()['live']['state'] == 'connected'
    )
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_b}/status').json()['live']['state'] == 'connected'
    )

    api_client.post(f'/accounts/{account_a}/conquest-guard/enable')

    status_a = api_client.get(f'/accounts/{account_a}/conquest-guard').json()
    status_b = api_client.get(f'/accounts/{account_b}/conquest-guard').json()
    assert status_a['enabled'] is True
    assert status_b['enabled'] is False
    assert status_b['armed_uid'] == 0


def test_conquest_guard_ownership_is_enforced(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.com')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='999', app_token='t', device_id='d',
    )
    response = api_client.get(f'/accounts/{other_account.id}/conquest-guard')
    assert response.status_code == 403
