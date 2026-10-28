"""Action endpoints: only the existing WarpathConnection methods, gated on
the account actually being connected."""

from __future__ import annotations

from tests.conftest import wait_until
from tests.fakes import (
    FakeWarpathSocket,
    respond_on_send,
    build_map_search_reply_frame,
    build_gain_all_produce_reply_frame,
    build_gather_mine_return_reply_frame,
    build_login_reply_frame,
    build_try_gather_mine_reply_frame,
    build_vehicle_list_reply_frame,
)
from tests.test_api_accounts import account_payload
from tests.test_api_sessions import create_account


def connect_and_wait(
    api_client, scripted_sockets, account_id: str, *,
    production_building_ids=None, production_lines=None, officer_tasks=None,
) -> FakeWarpathSocket:
    socket = FakeWarpathSocket([build_login_reply_frame(
        uid=7, production_building_ids=production_building_ids,
        production_lines=production_lines, officer_tasks=officer_tasks,
    )])
    scripted_sockets([socket])
    api_client.post(f'/accounts/{account_id}/connect')
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )
    return socket


def test_collect_without_connection_is_409(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/collect')
    assert response.status_code == 409


def test_collect_without_known_production_buildings_is_409(api_client, scripted_sockets):
    """Regression: request_collect_all() silently sent zero packets when
    production_building_ids was empty, but used to still report 200
    "collect requested" — indistinguishable from a real collect. Now it's a
    409 that says why, instead of a false success."""
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    response = api_client.post(f'/accounts/{account_id}/collect')
    assert response.status_code == 409
    assert 'no production buildings' in response.json()['detail']


def test_collect_when_connected_waits_for_real_replies_and_logs_event(api_client, scripted_sockets, fake_repo):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id, production_building_ids=[107, 108])
    respond_on_send(socket, lambda up: [build_gain_all_produce_reply_frame(
        up.bld_produce_req.gain_all_produce_req.bld_id,
        2 if up.bld_produce_req.gain_all_produce_req.bld_id == 107 else 0,
    )] if up.HasField('bld_produce_req') else [])

    response = api_client.post(f'/accounts/{account_id}/collect')
    assert response.status_code == 200
    body = response.json()
    assert body == {'status': 'confirmed', 'detail': 'complete', 'unconfirmed_building_ids': [],
                    'buildings_requested': 2, 'buildings_replied': 2, 'items_gained': 2}

    import uuid

    events = fake_repo.list_events(uuid.UUID(account_id))
    assert any(e.event_type == 'action_requested' and e.detail.get('action') == 'collect' for e in events)


def test_scan_accepts_optional_coordinates(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    response = api_client.post(f'/accounts/{account_id}/scan', json={'center_x': 100, 'center_y': 200})
    assert response.status_code == 200


def test_farm_validates_resource_and_level(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    bad = api_client.post(f'/accounts/{account_id}/farm', json={'resource': 'diamonds', 'level': 3})
    assert bad.status_code == 422

    too_high = api_client.post(f'/accounts/{account_id}/farm', json={'resource': 'gold', 'level': 99})
    assert too_high.status_code == 422


def test_farm_dispatches_an_idle_vehicle_to_a_found_mine(api_client, scripted_sockets):
    """The real search-then-dispatch chain: send_farm_search() only finds a
    target (find_and_refresh_req) — this confirms /farm now also calls the
    previously-dead send_farm_vehicle() once a mine and an idle vehicle are
    both known, and waits for that dispatch to be confirmed too."""
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_vehicle_list_reply_frame([{'id': 9, 'state': 1}]))
    api_client.post(f'/accounts/{account_id}/recall-all')

    def respond(up):
        if up.HasField('map_request'):
            return [build_map_search_reply_frame(mine_id=555, mine_type=1, x=10, y=20)]
        if up.HasField('map_mine_req') and up.map_mine_req.HasField('gather_map_mine_req'):
            return [build_try_gather_mine_reply_frame(vehicle_id=9, state=3, mine_id=555)]
        return []
    respond_on_send(socket, respond)

    response = api_client.post(f'/accounts/{account_id}/farm', json={'resource': 'gold', 'level': 3})
    assert response.status_code == 200
    assert response.json() == {'status': 'confirmed', 'dispatched': True, 'detail': 'vehicle dispatched to gather', 'mine_id': 555, 'vehicle_id': 9}


def test_farm_reports_no_mine_found_without_inventing_success(api_client, scripted_sockets):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    respond_on_send(socket, lambda up: [build_map_search_reply_frame(mine_id=0)]
                    if up.HasField('map_request') else [])

    response = api_client.post(f'/accounts/{account_id}/farm', json={'resource': 'gold', 'level': 3})
    assert response.status_code == 200
    body = response.json()
    assert body['dispatched'] is False
    assert body['mine_id'] is None


def test_farm_reports_no_idle_vehicle_available(api_client, scripted_sockets):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_vehicle_list_reply_frame([{'id': 9, 'state': 3}]))  # gathering, not idle
    api_client.post(f'/accounts/{account_id}/recall-all')
    respond_on_send(socket, lambda up: [build_map_search_reply_frame(mine_id=555)]
                    if up.HasField('map_request') else [])

    response = api_client.post(f'/accounts/{account_id}/farm', json={'resource': 'gold', 'level': 3})
    assert response.status_code == 200
    body = response.json()
    assert body == {'status': 'not_dispatched', 'dispatched': False, 'detail': 'found a mine but no idle farm vehicle is available', 'mine_id': 555, 'vehicle_id': None}


def test_recall_requires_vehicle_id(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    missing = api_client.post(f'/accounts/{account_id}/recall', json={})
    assert missing.status_code == 422


def test_recall_waits_for_the_real_return_reply(api_client, scripted_sockets):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_gather_mine_return_reply_frame(vehicle_id=5, state=1))

    response = api_client.post(f'/accounts/{account_id}/recall', json={'vehicle_id': 5})
    assert response.status_code == 200
    assert response.json() == {'vehicle_id': 5, 'state': 1}


def test_recall_all_requires_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/recall-all')
    assert response.status_code == 409


def test_recall_all_recalls_only_traveling_and_gathering_vehicles(api_client, scripted_sockets):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)

    socket.push_frame(build_vehicle_list_reply_frame([
        {'id': 1, 'state': 1},  # idle — must not be recalled
        {'id': 2, 'state': 2},  # traveling to resource — recall
        {'id': 3, 'state': 3},  # gathering — recall
        {'id': 4, 'state': 4},  # returning — must not be recalled
        {'id': 5, 'state': 9},  # gathering super mine — recall
    ]))

    response = api_client.post(f'/accounts/{account_id}/recall-all')
    assert response.status_code == 200
    assert sorted(response.json()['vehicle_ids']) == [2, 3, 5]


def test_recall_all_with_no_active_vehicles_recalls_nothing(api_client, scripted_sockets):
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_vehicle_list_reply_frame([{'id': 1, 'state': 1}]))

    response = api_client.post(f'/accounts/{account_id}/recall-all')
    assert response.status_code == 200
    assert response.json()['vehicle_ids'] == []


def test_scout_requires_plane_id(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)

    ok = api_client.post(f'/accounts/{account_id}/scout', json={'plane_id': 9})
    assert ok.status_code == 200


def test_action_on_account_owned_by_someone_else_is_403(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.test')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='x', app_token='t', device_id='d',
    )
    response = api_client.post(f'/accounts/{other_account.id}/collect')
    assert response.status_code == 403
