"""POST /accounts/mass-deploy: multi-account teleport + army-group-join.
Lilith/Warpath are never touched for real — the game operation itself is
gated behind app.core.mass_deploy.DeployExecutor, which these tests replace
with a fake to exercise the full execute path safely."""

from __future__ import annotations

import pytest

from app.core import mass_deploy as mass_deploy_core
from tests.fakes import build_group_army_list_reply_frame, build_user_position_reply_frame
from tests.test_api_accounts import account_payload
from tests.test_api_actions import connect_and_wait
from tests.test_api_sessions import create_account


def mass_deploy_body(account_ids, **overrides):
    body = {
        'account_ids': account_ids,
        'ag_id': '12345',
        'player_uid': '67890',
        'army_ids': 'auto',
        'group_type': 'auto',
        'execute': False,
    }
    body.update(overrides)
    return body


class FakeSuccessExecutor:
    def __init__(self):
        self.calls = []

    def deploy(self, connection, *, ag_id, player_uid, army_ids, group_type, cancel_event, position_index):
        self.calls.append((ag_id, player_uid, army_ids, group_type, position_index))
        return {
            'teleport': 'success: airlifted at (1, 1) after 1 position attempt(s)',
            'ag': f'success: joined slots {army_ids}',
            'error': None,
            'position_index': position_index + 1,
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_invalid_ag_id_rejected(api_client):
    account_id = create_account(api_client)
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], ag_id='-1'))
    assert response.status_code == 422


def test_invalid_player_uid_rejected(api_client):
    account_id = create_account(api_client)
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], player_uid='abc'))
    assert response.status_code == 422


def test_invalid_army_ids_rejected(api_client):
    account_id = create_account(api_client)
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], army_ids='1,,2'))
    assert response.status_code == 422


def test_invalid_group_type_rejected(api_client):
    account_id = create_account(api_client)
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], group_type='air'))
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def test_dry_run_returns_preview_and_sends_zero_game_requests(api_client, monkeypatch):
    account_id = create_account(api_client)

    class ExplodingExecutor:
        def deploy(self, *a, **k):
            raise AssertionError('dry run must never call the executor')

    monkeypatch.setattr(mass_deploy_core, 'DEFAULT_EXECUTOR', ExplodingExecutor())

    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id]))
    assert response.status_code == 200
    body = response.json()
    assert body['execute'] is False
    assert body['results'][0]['teleport'] == 'skipped (dry run)'
    assert body['results'][0]['ag'] == 'skipped (dry run)'


# ---------------------------------------------------------------------------
# Execute (fake executor — never the real Warpath API)
# ---------------------------------------------------------------------------

def test_execute_calls_mocked_executor_and_produces_per_account_results(api_client, scripted_sockets, monkeypatch):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    fake_executor = FakeSuccessExecutor()
    monkeypatch.setattr(mass_deploy_core, 'DEFAULT_EXECUTOR', fake_executor)

    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], execute=True))
    assert response.status_code == 200
    body = response.json()
    assert body['execute'] is True
    assert body['results'][0]['teleport'].startswith('success')
    assert body['results'][0]['ag'].startswith('success')
    assert body['complete_count'] == 1
    assert fake_executor.calls == [(12345, 67890, None, 0, 0)]


def test_execute_never_uses_a_premium_currency_fallback(api_client, scripted_sockets, monkeypatch):
    """The executor interface has no premium-currency parameter or method at
    all — there is no code path capable of spending premium currency."""
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    fake_executor = FakeSuccessExecutor()
    monkeypatch.setattr(mass_deploy_core, 'DEFAULT_EXECUTOR', fake_executor)
    assert not hasattr(fake_executor, 'use_premium_currency')
    assert not hasattr(mass_deploy_core.DeployExecutor, 'use_premium_currency')

    api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], execute=True))
    for call in fake_executor.calls:
        assert 'premium' not in str(call).lower()


def test_execute_reports_disconnected_account_without_aborting_others(api_client, scripted_sockets, monkeypatch):
    connected_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, connected_id)
    disconnected_id = api_client.post('/accounts', json=account_payload(label='Second', app_uid='uid-456')).json()['id']

    fake_executor = FakeSuccessExecutor()
    monkeypatch.setattr(mass_deploy_core, 'DEFAULT_EXECUTOR', fake_executor)

    response = api_client.post(
        '/accounts/mass-deploy', json=mass_deploy_body([connected_id, disconnected_id], execute=True)
    )
    assert response.status_code == 200
    by_id = {row['account_id']: row for row in response.json()['results']}
    assert by_id[connected_id]['teleport'].startswith('success')
    assert by_id[disconnected_id]['error'] == 'account is not connected'
    assert response.json()['complete_count'] == 1
    assert response.json()['total_count'] == 2


# ---------------------------------------------------------------------------
# Real executor against a REAL, connected WarpathConnection (no fake
# executor here) — every other execute test above injects a fake executor,
# which proves the API/orchestration layer but can never catch a bug in the
# real deploy_one_account/_wait_for_reply path itself (a missing
# server_error_serial attribute on WarpathConnection did exactly that
# during this stage — mass_deploy_ops' own unit tests used a hand-written
# fake connection that happened to already define it, so only an
# integration test against the real class could have caught it). This one
# runs the REAL DEFAULT_EXECUTOR against a REAL, connected WarpathConnection
# (scripted_sockets, no real network) through the "AG not found" path,
# which needs only two scripted replies to exercise the real position
# lookup + AG lookup + failure handling end to end.
# ---------------------------------------------------------------------------

def test_real_executor_against_a_real_connection_reaches_the_ag_lookup_and_fails_cleanly(api_client, scripted_sockets):
    import threading
    import time

    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)

    # Pushed from a background thread, staggered, while the mass-deploy
    # request below is in flight: pushing both frames upfront would let the
    # connection's own background read thread consume them (and advance
    # both serials) BEFORE deploy_one_account ever calls
    # request_user_position()/request_group_army_list() to capture its
    # baseline serial — _wait_for_reply then waits for a NEW increment past
    # a baseline that already includes these replies, and times out. This
    # bit the first version of this test.
    def push_replies():
        time.sleep(0.2)
        socket.push_frame(build_user_position_reply_frame(67890))
        time.sleep(0.2)
        socket.push_frame(build_group_army_list_reply_frame([]))  # AG 12345 is not in the list

    threading.Thread(target=push_replies, daemon=True).start()

    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], execute=True))

    assert response.status_code == 200
    row = response.json()['results'][0]
    assert row['error'] is None
    assert 'not in this account' in row['ag']
    assert row['teleport'] == 'skipped: AG validation failed'


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

def test_second_concurrent_execute_is_rejected_while_first_is_running(api_client, scripted_sockets, monkeypatch):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    # Grab the real lock instance the app is using and hold it, simulating
    # a mass deployment already in flight.
    real_lock = api_client.app.state.mass_deploy_lock
    assert real_lock.try_acquire() is True
    try:
        response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([account_id], execute=True))
        assert response.status_code == 409
    finally:
        real_lock.release()


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

def test_cannot_mass_deploy_another_users_account(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.com')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='999', app_token='t', device_id='d',
    )
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([str(other_account.id)]))
    assert response.status_code == 403


def test_unknown_account_id_is_404(api_client):
    import uuid
    response = api_client.post('/accounts/mass-deploy', json=mass_deploy_body([str(uuid.uuid4())]))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Mass cancel
# ---------------------------------------------------------------------------

def test_mass_cancel_with_nothing_running_does_not_pretend_to_cancel(api_client):
    response = api_client.post('/accounts/mass-deploy/cancel')
    assert response.status_code == 200
    body = response.json()
    assert body['cancelled'] is False


def test_mass_cancel_signals_the_running_deployment(api_client):
    real_lock = api_client.app.state.mass_deploy_lock
    assert real_lock.try_acquire() is True
    try:
        response = api_client.post('/accounts/mass-deploy/cancel')
        assert response.status_code == 200
        assert response.json()['cancelled'] is True
        assert real_lock.cancel_event.is_set()
    finally:
        real_lock.release()


def test_cancellation_stops_the_batch_before_the_next_account_starts(api_client, scripted_sockets, monkeypatch):
    account_a = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_a)
    account_b = api_client.post('/accounts', json=account_payload(label='Second', app_uid='uid-456')).json()['id']
    connect_and_wait(api_client, scripted_sockets, account_b)

    class CancelOnFirstCallExecutor:
        def __init__(self, lock):
            self.lock = lock
            self.calls = []

        def deploy(self, connection, *, ag_id, player_uid, army_ids, group_type, cancel_event, position_index):
            self.calls.append(connection)
            self.lock.request_cancel()  # simulate /mass-cancel arriving mid-batch
            return {'teleport': 'success: x', 'ag': 'success: x', 'error': None, 'position_index': position_index}

    from app.core import mass_deploy as mass_deploy_core

    real_lock = api_client.app.state.mass_deploy_lock
    executor = CancelOnFirstCallExecutor(real_lock)
    monkeypatch.setattr(mass_deploy_core, 'DEFAULT_EXECUTOR', executor)

    response = api_client.post(
        '/accounts/mass-deploy', json=mass_deploy_body([account_a, account_b], execute=True)
    )

    assert response.status_code == 200
    results = response.json()['results']
    # Exactly one account was actually deployed before the cancellation was
    # observed; the other must be reported as cancelled, never silently
    # skipped or falsely reported as completed.
    assert len(executor.calls) == 1
    statuses = {row['account_id']: row for row in results}
    cancelled_rows = [row for row in statuses.values() if row['teleport'] == 'cancelled']
    assert len(cancelled_rows) == 1
