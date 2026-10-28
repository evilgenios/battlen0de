from __future__ import annotations

from tests.test_api_accounts import account_payload


def test_global_events_are_owner_scoped_and_include_account_label(api_client, fake_repo):
    mine = api_client.post('/accounts', json=account_payload(label='Main')).json()
    mine_id = __import__('uuid').UUID(mine['id'])
    fake_repo.add_event(
        account_id=mine_id,
        actor='system',
        event_type='owned_event',
        detail={'ok': True},
    )

    other_user = fake_repo.get_or_create_user('events-other@example.test')
    other = fake_repo.create_account(
        owner_user_id=other_user.id,
        label='Other',
        app_uid='events-other',
        app_token='t',
        device_id='d',
    )
    fake_repo.add_event(
        account_id=other.id,
        actor='system',
        event_type='other_event',
        detail={},
    )

    response = api_client.get('/events?limit=20')
    assert response.status_code == 200
    rows = response.json()
    assert any(row['event']['event_type'] == 'owned_event' and row['account_label'] == 'Main' for row in rows)
    assert all(row['event']['event_type'] != 'other_event' for row in rows)


def test_global_events_is_empty_for_user_without_accounts(api_client):
    response = api_client.get('/events')
    assert response.status_code == 200
    assert response.json() == []
