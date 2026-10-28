"""Read-mostly intelligence endpoints: vehicles, armies, Army Groups,
profile, skins, map objects, locate bases, refresh, heartbeat. All exercised
against the real AccountManager/AccountSession/WarpathConnection stack with
only the TCP socket faked (scripted_sockets), same as every other action
test — never a real Warpath connection."""

from __future__ import annotations

from dataclasses import replace

from tests.conftest import wait_until
from tests.fakes import (
    FakeWarpathSocket,
    build_army_list_reply_frame,
    build_group_army_list_reply_frame,
    build_login_reply_frame,
    build_vehicle_list_reply_frame,
)
from tests.test_api_actions import connect_and_wait
from tests.test_api_sessions import create_account

AG_LAND = 10001


def _first_army_matches(api_client, account_id, **expected) -> bool:
    armies = api_client.get(f'/accounts/{account_id}/armies').json()
    return bool(armies) and all(armies[0].get(key) == value for key, value in expected.items())


def test_vehicles_empty_before_any_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/vehicles')
    assert response.status_code == 200
    assert response.json() == []


def test_summary_reports_zeros_before_any_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/summary')
    assert response.status_code == 200
    assert response.json()['vehicle_count'] == 0


def test_armies_and_army_groups_are_empty_lists_when_connected_with_no_data(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    assert api_client.get(f'/accounts/{account_id}/armies').json() == []
    assert api_client.get(f'/accounts/{account_id}/army-groups').json() == []


def test_army_group_join_without_a_known_ag_is_404(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.post(f'/accounts/{account_id}/army-groups/999/join', json={})
    assert response.status_code == 404


def test_army_group_actions_require_connection(api_client):
    account_id = create_account(api_client)
    assert api_client.post(f'/accounts/{account_id}/army-groups/refresh').status_code == 409
    assert api_client.post(f'/accounts/{account_id}/army-groups/leave', json={'army_id': 1}).status_code == 409
    assert api_client.post(f'/accounts/{account_id}/heartbeat').status_code == 409
    assert api_client.post(f'/accounts/{account_id}/refresh').status_code == 409


def test_heartbeat_succeeds_when_connected(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.post(f'/accounts/{account_id}/heartbeat')
    assert response.status_code == 200


def test_profile_not_cached_yet_is_404(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.get(f'/accounts/{account_id}/profile/12345')
    assert response.status_code == 404


def test_locate_base_not_cached_yet_is_404(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.get(f'/accounts/{account_id}/locate-bases/12345')
    assert response.status_code == 404


def test_player_scout_requires_explicit_member_access(api_client, fake_repo, monkeypatch):
    # Create the owned base under the fixture's normal local-admin identity,
    # then exercise the same identity as a member. This isolates the feature
    # entitlement check from account-provisioning policy.
    account_id = create_account(api_client)
    user = next(iter(fake_repo._users.values()))
    monkeypatch.setenv('DEV_USER_ROLE', 'member')

    # Exact player intelligence is denied before connection state is even
    # considered, so a customer cannot probe the privileged routes.
    assert api_client.get(f'/accounts/{account_id}/profile/12345').status_code == 403
    assert api_client.get(f'/accounts/{account_id}/locate-bases/12345').status_code == 403
    assert api_client.post(
        f'/accounts/{account_id}/locate-bases',
        json={'player_uid': 12345},
    ).status_code == 403

    # Ordinary nearby-map refresh remains a normal account feature.
    assert api_client.post(
        f'/accounts/{account_id}/locate-bases',
        json={'player_uid': None},
    ).status_code == 409

    fake_repo._users[user.id] = replace(user, player_scout_access=True)

    # Once explicitly entitled, the same member reaches the underlying
    # scout/cache behavior instead of the access-control boundary.
    assert api_client.get(f'/accounts/{account_id}/profile/12345').status_code == 404
    assert api_client.get(f'/accounts/{account_id}/locate-bases/12345').status_code == 404


def test_skins_default_to_empty_categories(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    response = api_client.get(f'/accounts/{account_id}/skins')
    assert response.status_code == 200
    assert response.json() == {'categories': {}}


def test_intel_routes_never_expose_secrets(api_client, scripted_sockets):
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id)
    for path in ('vehicles', 'armies', 'army-groups', 'map-objects', 'summary', 'skins'):
        response = api_client.get(f'/accounts/{account_id}/{path}')
        assert 'SECRET' not in response.text


def test_army_group_join_confirms_real_membership_change(api_client, scripted_sockets):
    """Regression: a live test against the real account showed the join
    request succeeding server-side (the AG's army_count went up) while the
    dashboard's Join/Leave button never updated, because nothing re-checked
    real membership. This confirms the backend now reads back
    connection.armies[id]['group_unique_id'] instead of just reporting
    "requested"."""
    import threading
    import time

    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)

    socket.push_frame(build_group_army_list_reply_frame([{'unique_id': 555, 'group_type': AG_LAND}]))
    socket.push_frame(build_army_list_reply_frame([{'army_id': 1, 'equipment_id': 100, 'group_unique_id': 0}]))
    api_client.post(f'/accounts/{account_id}/army-groups/refresh')
    assert wait_until(lambda: _first_army_matches(api_client, account_id, equipment_id=100))

    def push_confirmation():
        time.sleep(0.2)
        socket.push_frame(build_army_list_reply_frame([{'army_id': 1, 'equipment_id': 100, 'group_unique_id': 555}]))

    threading.Thread(target=push_confirmation, daemon=True).start()
    response = api_client.post(f'/accounts/{account_id}/army-groups/555/join', json={'army_ids': '1', 'group_type': 'auto'})

    assert response.status_code == 200
    assert response.json() == {'ag_id': 555, 'joined_army_ids': [1], 'unconfirmed_army_ids': []}
    assert api_client.get(f'/accounts/{account_id}/armies').json()[0]['group_unique_id'] == 555


def test_army_group_leave_confirms_real_membership_change(api_client, scripted_sockets):
    import threading
    import time

    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_army_list_reply_frame([{'army_id': 1, 'equipment_id': 100, 'group_unique_id': 555}]))
    api_client.post(f'/accounts/{account_id}/army-groups/refresh')
    assert wait_until(lambda: _first_army_matches(api_client, account_id, group_unique_id=555))

    def push_confirmation():
        time.sleep(0.2)
        socket.push_frame(build_army_list_reply_frame([{'army_id': 1, 'equipment_id': 100, 'group_unique_id': 0}]))

    threading.Thread(target=push_confirmation, daemon=True).start()
    response = api_client.post(f'/accounts/{account_id}/army-groups/leave', json={'army_id': 1})

    assert response.status_code == 200
    assert response.json() == {'army_id': 1, 'left': True}


def test_active_actions_reflects_real_gathering_vehicle_end_to_end(api_client, scripted_sockets):
    """Full wire path: a real get_vehicle_list_reply frame -> farm_vehicles
    -> /active-actions, proving the endpoint surfaces genuine server-sent
    position/timing data rather than anything invented."""
    account_id = create_account(api_client)
    socket = connect_and_wait(api_client, scripted_sockets, account_id)
    socket.push_frame(build_vehicle_list_reply_frame([
        {'id': 9, 'state': 3, 'mine_id': 555, 'x': 47830, 'y': 50954, 'start_time': 1000, 'end_time': 2000, 'max_gather_num': 2020000},
        {'id': 1, 'state': 1},  # idle — must not appear
    ]))
    api_client.post(f'/accounts/{account_id}/recall-all')  # populates farm_vehicles via a real reply wait

    response = api_client.get(f'/accounts/{account_id}/active-actions')
    assert response.status_code == 200
    [activity] = response.json()
    assert activity['activity_type'] == 'vehicle_gathering'
    assert activity['vehicle_id'] == 9
    assert activity['mine_id'] == 555
    assert activity['start_time'] == 1000
    assert activity['end_time'] == 2000
    assert activity['quantity'] == 2020000


def test_active_actions_accepts_a_real_non_numeric_task_id_end_to_end(api_client, scripted_sockets):
    """Regression: task_id is a string on the real wire (e.g. 'f1') — a
    live-browser check against a real account caught this endpoint
    returning a 500 (Pydantic rejecting it as int) that the frontend
    silently rendered as an empty "no activity" list. This is the exact
    validation step the unit tests in test_active_actions.py skip by
    calling build_active_actions() directly, so it needed its own
    end-to-end test through the real login-reply wire path."""
    account_id = create_account(api_client)
    connect_and_wait(api_client, scripted_sockets, account_id, officer_tasks=[
        {'task_id': 'f1', 'status': 2, 'start_time': 1000, 'end_time': 2000},
    ])

    response = api_client.get(f'/accounts/{account_id}/active-actions')
    assert response.status_code == 200
    [activity] = response.json()
    assert activity['activity_type'] == 'officer_task'
    assert activity['task_id'] == 'f1'
    assert activity['start_time'] == 1000
    assert activity['end_time'] == 2000


def test_production_endpoint_returns_the_complete_picture(api_client, scripted_sockets):
    """Unlike Active Actions' production entries (which only report cells
    whose end_time hasn't passed... no — Active Actions actually includes
    both in_progress and finished, same as this endpoint; the real
    difference active_actions.py's _production_activities draws is
    irrelevant here since both status values are real either way), this
    endpoint is the one-stop, unfiltered view across every known line."""
    import time

    account_id = create_account(api_client)
    now = int(time.time())
    connect_and_wait(api_client, scripted_sockets, account_id, production_lines=[
        {'bld_id': 108, 'line_id': 1, 'item_type_id': 'steel', 'quantity': 100, 'start_time': now - 200, 'end_time': now + 999999999},
        {'bld_id': 108, 'line_id': 2, 'item_type_id': 'oil', 'quantity': 50, 'start_time': now - 200, 'end_time': now - 100},
    ])

    response = api_client.get(f'/accounts/{account_id}/production')
    assert response.status_code == 200
    cells = response.json()
    assert len(cells) == 2
    in_progress = next(c for c in cells if c['line_id'] == 1)
    finished = next(c for c in cells if c['line_id'] == 2)
    assert in_progress['status'] == 'in_progress'
    assert in_progress['item_type_id'] == 'steel'
    assert finished['status'] == 'finished'
    assert finished['item_type_id'] == 'oil'


def test_production_is_empty_list_before_any_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/production')
    assert response.status_code == 200
    assert response.json() == []


def test_active_actions_is_empty_list_before_any_connection(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/active-actions')
    assert response.status_code == 200
    assert response.json() == []


def test_army_group_ownership_is_enforced(api_client, fake_repo, monkeypatch):
    monkeypatch.setenv('DEV_USER_ROLE', 'member')
    other_user = fake_repo.get_or_create_user('someone-else@example.com')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='999', app_token='t', device_id='d',
    )
    response = api_client.get(f'/accounts/{other_account.id}/vehicles')
    assert response.status_code == 403
