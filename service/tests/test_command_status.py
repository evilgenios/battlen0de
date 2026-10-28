"""Read-only pilot observations: synthetic sockets and identities only."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.core.warpath.connection import WarpathConnection
from tests.fakes import (FakeWarpathSocket, build_gain_all_produce_reply_frame,
    build_try_gather_mine_reply_frame, build_vehicle_list_reply_frame,
    build_map_search_reply_frame, with_sequence)
from tests.test_tenant_isolation import principals, stored_account  # fixture


@pytest.fixture
def connection(make_credentials):
    conn = WarpathConnection(make_credentials('synthetic-report'))
    conn.sock = FakeWarpathSocket()
    conn.authenticated = conn.socket_connected = True
    conn.farm_vehicles = [{'id': 9, 'state': 1}]
    conn.production_building_ids = {107, 108}
    return conn


def deliver(conn, frame, seq):
    conn.observe_account_data(with_sequence(frame, seq)[5:])


def test_report_timeout_is_read_only_and_retains_reservation(connection):
    t = connection.send_farm_vehicle(555, 9)
    assert connection.reply_actions.wait([t], timeout=0) == 'timeout'
    packets = len(connection.sock.sent)
    report = connection.reply_actions.operational_status()
    row = report['active'][0]
    assert (row['status'], row['reason'], row['reservation']) == ('uncertain', 'timeout', 'truck')
    assert len(connection.sock.sent) == packets
    assert connection.send_farm_vehicle(556, 9) is None
    row['status'] = 'confirmed'  # returned projection cannot mutate tickets
    assert t.status == 'pending'


def test_automatic_collection_age_is_uncertain_without_wait_or_releasing(connection, monkeypatch):
    tickets = connection.request_collect_all()
    monkeypatch.setattr('app.core.warpath.reply_actions.time.monotonic', lambda: tickets[0].started_monotonic + 10)
    report = connection.reply_actions.operational_status()
    assert all(r['status'] == 'uncertain' and r['reason'] == 'timeout' for r in report['active'])
    assert all(t.status == 'pending' for t in tickets)
    assert len(connection.reply_actions.collections) == 2


def test_late_collect_is_visible_once_after_it_leaves_active_requests(connection):
    tickets = connection.request_collect_all()
    connection.reply_actions.collect_result(tickets, timeout=0)
    deliver(connection, build_gain_all_produce_reply_frame(107, 3), tickets[0].seq)
    deliver(connection, build_gain_all_produce_reply_frame(107, 3), tickets[0].seq)
    report = connection.reply_actions.operational_status()
    assert [r['building_id'] for r in report['active']] == [108]
    assert len(report['recent']) == 1
    assert report['recent'][0]['status'] == 'confirmed'
    assert report['recent'][0]['operation_id'] == tickets[0].operation_id


def test_late_gather_stays_reserved_until_phase4_idle_reconciliation(connection):
    t = connection.send_farm_vehicle(555, 9)
    connection.reply_actions.wait([t], timeout=0)
    deliver(connection, build_try_gather_mine_reply_frame(9, 3, 555), t.seq)
    row = connection.reply_actions.operational_status()['active'][0]
    assert (row['status'], row['reason'], row['reservation']) == ('confirmed', 'awaiting_idle_observation', 'truck')
    refresh = connection.request_vehicle_list()
    deliver(connection, build_vehicle_list_reply_frame([{'id':9,'state':1}]), refresh.seq)
    report = connection.reply_actions.operational_status()
    assert not report['active']
    assert report['recent'][0]['reason'] == 'idle_observed'
    assert report['recent'][0]['reservation'] == 'none'


def test_cancel_disconnect_reset_cannot_invent_completion(connection):
    t = connection.send_farm_vehicle(555, 9)
    cancel = Event(); cancel.set()
    connection.reply_actions.wait([t], cancel_event=cancel)
    assert connection.reply_actions.operational_status()['active'][0]['reason'] == 'cancelled'
    connection.close()
    before = connection.reply_actions.operational_status()
    assert before['active'][0]['status'] == 'uncertain'
    assert before['active'][0]['reason'] == 'disconnected'
    connection.reset_account_data()
    after = connection.reply_actions.operational_status()
    assert after['observation_id'] != before['observation_id']
    assert not after['active'] and not after['recent']


def test_report_is_bounded_and_does_not_export_payloads_or_sequence(connection):
    for _ in range(53):
        t = connection.send_farm_search('gold', 3)
        deliver(connection, build_map_search_reply_frame(), t.seq)
    t.reply['token'] = 'synthetic-secret'
    report = connection.reply_actions.operational_status()
    assert len(report['recent']) == 50 and report['recent_dropped'] == 3
    serialized = json.dumps(report)
    assert 'synthetic-secret' not in serialized
    assert 'msg_seq_id' not in serialized and '"seq"' not in serialized and '"reply"' not in serialized


def test_concurrent_reads_and_completion_are_consistent(connection):
    tickets = connection.request_collect_all()
    def read():
        for _ in range(40):
            report = connection.reply_actions.operational_status()
            ids = [r['operation_id'] for r in report['active'] + report['recent']]
            assert len(ids) == len(set(ids))
    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(read)
        for t in tickets:
            deliver(connection, build_gain_all_produce_reply_frame(t.entity), t.seq)
        future.result(timeout=2)


def test_endpoint_owner_admin_read_and_cross_owner_anonymous_revoked_denial(api_client, principals, fake_repo, account_manager, make_credentials):
    alice, owner = principals['alice']; bob, _ = principals['bob']; admin, _ = principals['operator']
    a = stored_account(fake_repo, owner)
    # No connect/start: install a session object with a synthetic socket only.
    session = account_manager.add_account(make_credentials(str(a.id)))
    conn = session.connection
    conn.sock = FakeWarpathSocket(); conn.authenticated = conn.socket_connected = True
    conn.farm_vehicles = [{'id':9,'state':1}]
    ticket = conn.send_farm_vehicle(555, 9)
    conn.reply_actions.wait([ticket], timeout=0)
    path = f'/accounts/{a.id}/command-status'
    before = len(conn.sock.sent)
    own = alice.get(path)
    assert own.status_code == 200 and own.headers['cache-control'] == 'no-store'
    assert own.json()['active'][0]['status'] == 'uncertain'
    assert own.json()['upstream_evidence'] == 'unverified'
    assert own.json()['history_complete'] is False
    assert admin.get(path).status_code == 200
    assert bob.get(path).status_code == 403
    assert api_client.get(path).status_code == 401
    assert len(conn.sock.sent) == before
    api_client.app.state.dashboard_sessions.destroy(alice.cookies.get('dashboard_session'))
    assert alice.get(path).status_code == 401


def test_absent_and_restricted_accounts_report_unknown_history_without_mutation(principals, fake_repo):
    alice, user = principals['alice']
    account = stored_account(fake_repo, user)
    fake_repo.update_account(account.id, status='restricted')
    response = alice.get(f'/accounts/{account.id}/command-status')
    assert response.status_code == 200
    body = response.json()
    assert body['observation_id'] is None
    assert body['history_scope'] == 'current_connection_only' and body['history_complete'] is False
    assert body['active'] == [] and body['recent'] == []
    assert alice.post(f'/accounts/{account.id}/command-status').status_code == 405
    assert alice.post(f'/accounts/{account.id}/farm', json={'resource':'gold','level':3}).status_code == 409
