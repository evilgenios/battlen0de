"""Real production gate; synthetic identities/sockets only, no bypass fixture."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from app.core.account_manager import AccountManager
from app.core.pilot_activation import PilotActivation, PilotBlocked, observation_packet
from app.core.warpath.protobuf import up_pb2
from app.main import create_app
from tests.conftest import wait_until
from tests.fakes import FakeWarpathSocket, build_login_reply_frame, decode_request
from tests.test_api_accounts import account_payload
from tests.test_tenant_isolation import principals  # noqa: F401 - shared two members/admin fixture


@pytest.fixture
def pilot_api(api_client, principals, fake_repo):
    manager = AccountManager()
    api_client.app.state.account_manager = manager
    alice = fake_repo.create_account(owner_user_id=principals['alice'][1].id,
                                     **account_payload(app_uid='901'))
    bob = fake_repo.create_account(owner_user_id=principals['bob'][1].id,
                                   **account_payload(app_uid='902'))
    yield manager, alice, bob
    manager.stop_all()


def test_default_off_owner_admin_csrf_and_read_only(pilot_api, principals, api_client, monkeypatch):
    manager, account, _ = pilot_api
    owner, _ = principals['alice']
    foreign, _ = principals['bob']
    admin, _ = principals['operator']
    base = f'/accounts/{account.id}'
    socket = Mock(side_effect=AssertionError('no game connection allowed'))
    from types import SimpleNamespace
    from app.core.warpath import connection as module
    monkeypatch.setattr(module, 'socket', SimpleNamespace(**{**vars(module.socket), 'socket': socket}))
    assert owner.get(base + '/pilot-activation').json()['mode'] == 'off'
    assert owner.get(base + '/command-status').json()['history_complete'] is False
    assert owner.post(base + '/connect').status_code == 409
    assert api_client.get(base + '/pilot-activation').status_code == 401
    assert foreign.get(base + '/pilot-activation').status_code == 403
    assert foreign.post(base + '/pilot-pause').status_code == 403
    assert owner.post(base + '/pilot-activation', json={'mode': 'observe'}).status_code == 403
    csrf = admin.headers.pop('x-csrf-token')
    assert admin.post(base + '/pilot-activation', json={'mode': 'observe'}).status_code == 403
    admin.headers['x-csrf-token'] = csrf
    response = admin.post(base + '/pilot-activation', json={'mode': 'observe', 'minutes': 1})
    assert response.status_code == 200
    assert response.json()['mode'] == 'observe'
    assert response.json()['automatic_actions'] is False
    assert owner.get(base + '/pilot-activation').headers['cache-control'] == 'no-store'
    assert manager.get_account(str(account.id)) is None  # grant never registers/connects
    socket.assert_not_called()


@pytest.mark.parametrize('action', ['collect', 'farm', 'scan', 'scout', 'recall', 'recall-all',
                                   'conquest-guard/enable', 'army-groups/leave',
                                   'army-groups/123/join', 'locate-bases'])
def test_game_actions_blocked_before_dispatch(pilot_api, principals, action):
    manager, account, _ = pilot_api
    manager.pilot.activate(str(account.id), 'synthetic-operator', 1)
    response = principals['alice'][0].post(f'/accounts/{account.id}/{action}', json={})
    assert response.status_code == 409
    assert 'unverified' in response.json()['detail']
    assert manager.get_account(str(account.id)) is None


def test_automatic_request_cannot_open_gate_and_members_cannot_mass_cancel(pilot_api, principals):
    manager, account, _ = pilot_api
    admin, _ = principals['operator']
    path = f'/accounts/{account.id}/pilot-activation'
    assert admin.post(path, json={'mode': 'automatic'}).status_code == 409
    assert manager.pilot.status(str(account.id))['mode'] == 'off'
    assert principals['alice'][0].post('/accounts/mass-deploy/cancel').status_code == 403
    body = {'account_ids': [str(account.id)], 'ag_id': '1', 'player_uid': '2',
            'army_ids': 'auto', 'group_type': 'auto', 'execute': True}
    response = admin.post('/accounts/mass-deploy', json=body)
    assert response.status_code == 409, response.text
    assert 'unverified' in response.text


@pytest.mark.parametrize('body', [{'mode': 'observe', 'minutes': 0}, {'mode': 'observe', 'minutes': 61},
                                 {'mode': 'observe', 'minutes': True}, {'mode': 'observe', 'force': True}])
def test_invalid_grants_rejected(pilot_api, principals, body):
    _, account, _ = pilot_api
    assert principals['operator'][0].post(f'/accounts/{account.id}/pilot-activation', json=body).status_code == 422


def test_policy_change_revokes_even_unconnected_grant(pilot_api, principals):
    manager, account, other = pilot_api
    admin, _ = principals['operator']
    manager.pilot.activate(str(account.id), 'operator', 1)
    manager.pilot.activate(str(other.id), 'operator', 1)
    assert admin.post(f'/accounts/{account.id}/status', json={'status': 'restricted'}).status_code == 200
    assert manager.pilot.status(str(account.id))['mode'] == 'off'
    assert admin.post(f'/accounts/{account.id}/pilot-activation', json={'mode': 'observe'}).status_code == 409
    assert principals['alice'][0].post(f'/accounts/{account.id}/pilot-pause').status_code == 200
    assert manager.pilot.status(str(other.id))['mode'] == 'observe'


def test_audit_failure_leaves_off_and_pause_still_contains(pilot_api, principals, fake_repo, monkeypatch):
    manager, account, _ = pilot_api
    manager.pilot.activate(str(account.id), 'operator', 1)
    monkeypatch.setattr(fake_repo, 'add_event', Mock(side_effect=RuntimeError('synthetic storage unavailable')))
    admin, _ = principals['operator']
    with pytest.raises(RuntimeError):
        admin.post(f'/accounts/{account.id}/pilot-activation', json={'mode': 'observe'})
    assert manager.pilot.status(str(account.id))['mode'] == 'off'
    manager.pilot.activate(str(account.id), 'operator', 1)
    with pytest.raises(RuntimeError):
        admin.post(f'/accounts/{account.id}/pilot-pause')
    assert manager.pilot.status(str(account.id))['mode'] == 'off'


def test_customer_observation_owner_connects_without_operator_grant(
    pilot_api, principals, scripted_sockets
):
    manager, account, _ = pilot_api
    manager.pilot = PilotActivation(customer_observation=True)
    owner, _ = principals['alice']
    sock = FakeWarpathSocket([build_login_reply_frame(uid=42)])
    scripted_sockets([sock])
    base = f'/accounts/{account.id}'

    response = owner.post(base + '/connect')
    assert response.status_code == 202, response.text
    session = manager.get_account(str(account.id))
    assert wait_until(lambda: session is not None and session.connection.connected)
    assert owner.get(base + '/pilot-activation').json()['reason'] == 'customer_mode'
    blocked = owner.post(base + '/collect')
    assert blocked.status_code == 409
    assert 'unverified' in blocked.json()['detail']
    assert all(observation_packet(decode_request(packet)) for packet in sock.sent)
    assert owner.post(base + '/disconnect').status_code == 200


def test_customer_observation_mode_is_durable_but_actions_stay_closed():
    policy = PilotActivation(customer_observation=True)
    policy.require_observation('customer-account')
    status = policy.status('customer-account')
    assert status['mode'] == 'observe'
    assert status['reason'] == 'customer_mode'
    assert status['restart_policy'] == 'auto'
    assert status['automatic_actions'] is False
    assert status['game_actions'] is False
    with pytest.raises(PilotBlocked, match='unverified'):
        policy.check_http('customer-account', 'collect')
    policy.check_http('customer-account', 'connect')
    policy.revoke('customer-account')
    policy.require_observation('customer-account')


def test_monotonic_expiry_restart_and_independent_accounts():
    clock = [1.0]
    wall = [100.0]
    policy = PilotActivation(clock=lambda: clock[0], wall_clock=lambda: wall[0])
    policy.activate('a', 'admin', 1)
    policy.activate('b', 'admin', 2)
    wall[0] = -10000  # clock corrections cannot extend a grant
    clock[0] = 61.0
    assert policy.status('a')['reason'] == 'expired'
    with pytest.raises(PilotBlocked):
        policy.require_observation('a')
    policy.require_observation('b')
    restarted = PilotActivation()
    assert restarted.instance_id != policy.instance_id
    assert restarted.status('b')['mode'] == 'off'


@pytest.mark.parametrize('value', ['true', 'yes', '1', 'typo'])
def test_autostart_rejected_before_any_io(monkeypatch, value):
    monkeypatch.setenv('AUTOSTART_ACTIVE_ACCOUNTS', value)
    build = Mock(side_effect=AssertionError('must not touch DB'))
    monkeypatch.setattr('app.main.build_engine', build)
    with pytest.raises(RuntimeError, match='AUTOSTART'):
        create_app(lifespan_context=None)
    build.assert_not_called()


def test_socket_allowlist_and_before_send_reservation_boundary(make_credentials):
    manager = AccountManager()
    conn = manager.add_account(make_credentials('a')).connection
    conn.sock = FakeWarpathSocket()
    conn.socket_connected = conn.authenticated = True
    callback = Mock()
    with pytest.raises(PilotBlocked):
        conn.send_message(conn.build_login_message(), before_send=callback)
    callback.assert_not_called()
    manager.pilot.activate('a', 'operator', 1)
    conn.send_login()
    conn.send_keepalive()
    conn.request_vehicle_list()
    conn.request_power_snapshot()
    conn.request_user_skin_data()
    conn.request_group_army_list()
    conn.request_player_profile(1)
    assert len(conn.sock.sent) == 7
    before = len(conn.sock.sent)
    with pytest.raises(PilotBlocked):
        conn.send_raw(b'synthetic')
    conn.production_building_ids = {101}
    tickets = conn.request_collect_all()
    assert tickets[0].status == 'rejected' and tickets[0].wait_reason == 'not_sent'
    assert tickets[0].seq is None
    assert len(conn.sock.sent) == before
    assert conn.automatic_actions_enabled() is False
    with pytest.raises(PilotBlocked):
        conn.send_season_transfer_out()


def test_mixed_unknown_and_nested_mutation_packets_denied(make_credentials):
    conn = AccountManager().add_account(make_credentials('a')).connection
    up = up_pb2.up_msg()
    up.ParseFromString(conn.build_login_message())
    assert observation_packet(up)
    up.map_mine_req.gather_map_mine_req.mine_id = 1
    up.map_mine_req.gather_map_mine_req.vehicle_id = 2
    assert not observation_packet(up)
    up = up_pb2.up_msg()
    up.map_mine_req.get_vehicle_list_req.SetInParent()
    up.map_mine_req.call_back_vehicle_req.vehicle_id = 2
    assert not observation_packet(up)
    up = up_pb2.up_msg()
    up.power_req.SetInParent()
    up.MergeFromString(b'\xf8\xff\x03\x01')  # unknown field 8191
    assert not observation_packet(up)


def test_revoke_waits_for_admitted_send_then_blocks_next(make_credentials):
    manager = AccountManager()
    conn = manager.add_account(make_credentials('a')).connection
    conn.sock = FakeWarpathSocket()
    conn.socket_connected = True
    manager.pilot.activate('a', 'operator', 1)
    entered, release, revoking = Event(), Event(), Event()
    def send(packet):
        entered.set()
        assert release.wait(2)
    conn.sock.sendall = send
    def revoke():
        revoking.set()
        manager.pilot.revoke('a')
    with ThreadPoolExecutor(max_workers=2) as pool:
        sending = pool.submit(conn.send_keepalive)
        assert entered.wait(2)
        stopping = pool.submit(revoke)
        assert revoking.wait(2)
        assert not stopping.done()
        release.set()
        sending.result(2)
        stopping.result(2)
    with pytest.raises(PilotBlocked):
        conn.send_keepalive()


def test_connect_drop_does_not_retry_or_reset_tracker(pilot_api, principals, scripted_sockets):
    manager, account, _ = pilot_api
    owner, _ = principals['alice']
    admin, _ = principals['operator']
    sock = FakeWarpathSocket([build_login_reply_frame(uid=42)])
    factory = scripted_sockets([sock])
    base = f'/accounts/{account.id}'
    assert admin.post(base + '/pilot-activation', json={'mode': 'observe'}).status_code == 200
    assert owner.post(base + '/connect').status_code == 202
    session = manager.get_account(str(account.id))
    assert wait_until(lambda: session.connection.connected and len(sock.sent) >= 4)
    observation = session.connection.reply_actions.observation_id
    assert admin.post(base + '/pilot-activation', json={'mode': 'observe'}).status_code == 409
    assert owner.post(base + '/reconnect').status_code == 409
    sock.idle_reads_before_close = 0  # synthetic peer EOF on the next receive
    assert wait_until(lambda: session.is_quiescent)
    assert session.connection.reply_actions.observation_id == observation
    assert session.status()['retry_count'] == 0
    assert manager.pilot.status(str(account.id))['mode'] == 'off'
    assert owner.post(base + '/connect').status_code == 409
    assert len(factory.created) == 1
    assert all(observation_packet(decode_request(packet)) for packet in sock.sent)


def test_pause_retains_uncertainty_and_activation_cannot_clear(pilot_api, principals, make_credentials):
    from tests.fakes import SyntheticPilotPolicy
    manager, account, _ = pilot_api
    session = manager.add_account(make_credentials(str(account.id)))
    conn = session.connection
    sock = FakeWarpathSocket()
    conn.sock = sock
    conn.socket_connected = conn.authenticated = True
    conn.production_building_ids = {101}
    # Seed a historically uncertain send with a synthetic engine-only policy.
    conn.pilot_policy = SyntheticPilotPolicy()
    ticket = conn.request_collect_all()[0]
    conn.reply_actions.wait([ticket], timeout=0)
    conn.pilot_policy = manager.pilot
    before = conn.reply_actions.observation_id
    owner, _ = principals['alice']
    admin, _ = principals['operator']
    base = f'/accounts/{account.id}'
    assert owner.post(base + '/pilot-pause').status_code == 200
    report = owner.get(base + '/command-status').json()
    assert report['observation_id'] == before
    assert report['active'][0]['status'] == 'uncertain'
    assert conn.reply_actions.collections[101] is ticket
    sent = len(sock.sent)
    assert admin.post(base + '/pilot-activation', json={'mode': 'observe'}).status_code == 409
    assert len(sock.sent) == sent
    assert ticket.status == 'pending'


def test_background_collection_and_guard_do_not_attempt_actions(make_credentials, scripted_sockets, monkeypatch):
    from types import SimpleNamespace
    from app.core.warpath import connection as module
    clock = [1.0]
    manager = AccountManager()
    conn = manager.add_account(make_credentials('a')).connection
    manager.pilot.activate('a', 'operator', 10)
    sock = FakeWarpathSocket([build_login_reply_frame(uid=42, production_building_ids=[101])])
    scripted_sockets([sock])
    collector = Mock(side_effect=AssertionError('automatic collection must not run'))
    conn.request_collect_all = collector
    iterations = []
    def settimeout(value):
        if value == 0.02:
            iterations.append(value)
            clock[0] += 300  # advance past the legacy 240-second interval
            if len(iterations) == 3:
                sock.idle_reads_before_close = 0
    sock.settimeout = settimeout
    monkeypatch.setattr(module, 'time', SimpleNamespace(**{**vars(module.time),
        'monotonic': lambda: clock[0], 'sleep': lambda _: None}))
    conn.run()
    assert len(iterations) == 3
    collector.assert_not_called()
    assert all(observation_packet(decode_request(packet)) for packet in sock.sent)
    conn.account_snapshot.update(uid=42, base_id=99, city_id=1, season_city_id=1)
    conn.conquest_guard_enabled, conn.conquest_guard_armed_uid = True, 42
    exit_command = Mock(side_effect=AssertionError('guard must not run'))
    conn.send_season_transfer_out = exit_command
    conn._maybe_exit_conquest_for_attack(defender=SimpleNamespace(owner_id=42, obj_id=99))
    assert conn.conquest_guard_last_attack is not None
    exit_command.assert_not_called()
    assert conn.conquest_guard_attempts == 0


def test_expiry_blocks_send_before_callback_and_keeps_pending(make_credentials):
    clock = [0.0]
    policy = PilotActivation(clock=lambda: clock[0])
    manager = AccountManager(pilot_policy=policy)
    conn = manager.add_account(make_credentials('a')).connection
    conn.sock = FakeWarpathSocket()
    conn.socket_connected = True
    policy.activate('a', 'operator', 1)
    ticket = conn.request_vehicle_list()
    clock[0] = 60
    callback = Mock()
    with pytest.raises(PilotBlocked):
        conn.send_message(conn.build_login_message(), before_send=callback)
    callback.assert_not_called()
    assert ticket.seq in conn.reply_actions.requests
    assert len(conn.sock.sent) == 1
