"""connect/disconnect/reconnect/status: exercises the real AccountManager/
AccountSession/WarpathConnection stack from Stage 1/2 through the API,
with only the TCP socket faked (same tests/fakes.py as Stage 1/2)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fakes import synthetic_account_manager as AccountManager
from app.core.dashboard_session import DashboardSessionStore
from app.main import create_app
from tests.conftest import wait_until
from tests.fake_repository import FakeEngine, InMemoryAccountRepository
from tests.fakes import FakeWarpathSocket, build_login_reply_frame
from tests.test_api_accounts import account_payload


def create_account(api_client) -> str:
    return api_client.post('/accounts', json=account_payload()).json()['id']


def test_connect_reaches_connected_and_status_reflects_it(api_client, scripted_sockets):
    account_id = create_account(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=42)])])

    response = api_client.post(f'/accounts/{account_id}/connect')
    assert response.status_code == 202

    def is_connected():
        status = api_client.get(f'/accounts/{account_id}/status').json()
        return status['live'] is not None and status['live']['state'] == 'connected'

    assert wait_until(is_connected)

    status = api_client.get(f'/accounts/{account_id}/status').json()
    assert status['live']['authenticated'] is True


def test_connect_twice_is_409(api_client, scripted_sockets):
    account_id = create_account(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])

    first = api_client.post(f'/accounts/{account_id}/connect')
    assert first.status_code == 202
    second = api_client.post(f'/accounts/{account_id}/connect')
    assert second.status_code == 409


def test_connect_unknown_account_is_404(api_client):
    import uuid

    response = api_client.post(f'/accounts/{uuid.uuid4()}/connect')
    assert response.status_code == 404


def test_disconnect_without_a_session_is_409(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/disconnect')
    assert response.status_code == 409


def test_connect_then_disconnect(api_client, scripted_sockets):
    account_id = create_account(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
    api_client.post(f'/accounts/{account_id}/connect')
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )

    response = api_client.post(f'/accounts/{account_id}/disconnect')
    assert response.status_code == 200
    status = api_client.get(f'/accounts/{account_id}/status').json()
    assert status['live']['state'] == 'stopped'


def test_status_before_any_connect_has_no_live_session(api_client):
    account_id = create_account(api_client)
    response = api_client.get(f'/accounts/{account_id}/status')
    assert response.status_code == 200
    body = response.json()
    assert body['live'] is None
    assert body['db_status'] == 'active'


def test_reconnect_without_prior_connect_is_409(api_client):
    account_id = create_account(api_client)
    response = api_client.post(f'/accounts/{account_id}/reconnect')
    assert response.status_code == 409


def test_incomplete_credentials_yield_422_on_connect(api_client, fake_repo, dev_user_email):
    user = fake_repo.get_or_create_user(dev_user_email)
    account = fake_repo.create_account(
        owner_user_id=user.id, label='Incomplete', app_uid='', app_token='', device_id='',
    )
    response = api_client.post(f'/accounts/{account.id}/connect')
    assert response.status_code == 422
    # The 422 detail lists missing FIELD NAMES only, never a secret value.
    assert 'app_token' in response.text
    assert 'SECRET' not in response.text


def test_connect_after_credentials_are_corrected_no_longer_replays_stale_422(
    api_client, fake_repo, dev_user_email, scripted_sockets
):
    """Regression test for a live incident: an account was first registered
    with incomplete device metadata, so /connect correctly 422'd. The
    database row was corrected afterward (exactly like a human finishing
    device-metadata setup) — but on the SAME long-running server process,
    AccountManager kept a cached AccountSession built from the ORIGINAL,
    now-stale WarpathCredentials snapshot. Since AccountSession never
    re-reads the database on its own, every subsequent /connect on that
    process replayed the exact same missing-metadata 422 forever, even
    though a fresh process (or a direct repository check) proved the
    database itself was fine. _ensure_registered() in api/sessions.py must
    detect the drift and swap in a fresh session, as long as the old one
    isn't currently connecting/connected/reconnecting.
    """
    user = fake_repo.get_or_create_user(dev_user_email)
    account = fake_repo.create_account(
        owner_user_id=user.id, label='Bootstrap', app_uid='500000123',
        app_token='token-bootstrap-SECRET', device_id='device-bootstrap-SECRET',
        device_metadata={},  # incomplete: no app_id/pack_name/channel_id/etc.
    )

    first = api_client.post(f'/accounts/{account.id}/connect')
    assert first.status_code == 422
    assert 'app_id' in first.text

    # The database row gets corrected — same account, same session slot.
    fake_repo.update_account(account.id, device_metadata={
        'app_id': 'a', 'pack_name': 'p', 'channel_id': 'c',
        'app_version': '1.0.0', 'package_version': '1.0.0', 'os_type': 'win',
    })

    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
    # Operator explicitly re-enables the corrected account after auth_failed.
    assert api_client.post(f'/accounts/{account.id}/status', json={'status': 'active'}).status_code == 200
    second = api_client.post(f'/accounts/{account.id}/connect')
    assert second.status_code == 202

    assert wait_until(
        lambda: api_client.get(f'/accounts/{account.id}/status').json()['live']['state'] == 'connected'
    )


def test_concurrent_refresh_of_a_stale_session_never_surfaces_a_500(fake_repo, dev_user_email, account_manager, monkeypatch):
    """Two concurrent /connect (or /connect + /reconnect) calls that both
    see the same stale, inactive session can both decide to swap it for a
    fresh one — since remove_account()+add_account() isn't one atomic
    operation, AccountManager.add_account() can raise ValueError for
    whichever request's add() loses that race (the other one already
    re-registered the account_id first). _refresh_if_stale() must self-heal
    instead of letting that propagate as an unhandled 500."""
    from app.api.sessions import _refresh_if_stale

    user = fake_repo.get_or_create_user(dev_user_email)
    account = fake_repo.create_account(
        owner_user_id=user.id, label='Bootstrap', app_uid='500000789',
        app_token='token-bootstrap-SECRET', device_id='device-bootstrap-SECRET',
        device_metadata={},  # incomplete, so it differs from the corrected row below
    )
    stale_credentials = fake_repo.get_credentials(account.id)
    stale_session = account_manager.add_account(stale_credentials)

    fake_repo.update_account(account.id, device_metadata={
        'app_id': 'a', 'pack_name': 'p', 'channel_id': 'c',
        'app_version': '1.0.0', 'package_version': '1.0.0', 'os_type': 'win',
    })

    # Simulate the exact race: by the time OUR add_account() call inside
    # _refresh_if_stale runs, a concurrent request already won and
    # re-registered this account_id — the real AccountManager.add_account
    # would raise ValueError here.
    real_add_account = account_manager.add_account
    winning_session_holder = {}

    def add_account_that_loses_the_race(credentials, **kwargs):
        if 'winner' not in winning_session_holder:
            winning_session_holder['winner'] = real_add_account(credentials, **kwargs)
            raise ValueError(f'account {credentials.account_id!r} is already registered')
        return real_add_account(credentials, **kwargs)

    monkeypatch.setattr(account_manager, 'add_account', add_account_that_loses_the_race)

    result = _refresh_if_stale(account_manager, fake_repo, account, stale_session)

    assert result is winning_session_holder['winner']


def test_reconnect_after_credentials_are_corrected_no_longer_replays_stale_422(
    api_client, fake_repo, dev_user_email, scripted_sockets
):
    """Same regression as the /connect version above, but for /reconnect —
    an earlier pass fixed the stale-session bug only in _ensure_registered()
    (used by /connect), while /reconnect read manager.get_account() directly
    and skipped the refresh entirely. A user who clicks Reconnect instead of
    Connect after fixing an account's metadata would still get stuck on the
    original stale validation failure forever."""
    user = fake_repo.get_or_create_user(dev_user_email)
    account = fake_repo.create_account(
        owner_user_id=user.id, label='Bootstrap', app_uid='500000456',
        app_token='token-bootstrap-SECRET', device_id='device-bootstrap-SECRET',
        device_metadata={},  # incomplete
    )

    first = api_client.post(f'/accounts/{account.id}/connect')
    assert first.status_code == 422

    fake_repo.update_account(account.id, device_metadata={
        'app_id': 'a', 'pack_name': 'p', 'channel_id': 'c',
        'app_version': '1.0.0', 'package_version': '1.0.0', 'os_type': 'win',
    })

    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
    # Operator explicitly re-enables the corrected account after auth_failed.
    assert api_client.post(f'/accounts/{account.id}/status', json={'status': 'active'}).status_code == 200
    second = api_client.post(f'/accounts/{account.id}/reconnect')
    assert second.status_code == 202

    assert wait_until(
        lambda: api_client.get(f'/accounts/{account.id}/status').json()['live']['state'] == 'connected'
    )


def test_connect_does_not_replace_an_already_active_session_on_credential_drift(
    api_client, fake_repo, dev_user_email, scripted_sockets
):
    """The stale-session refresh in _ensure_registered() must never disturb
    a session that is currently connecting/connected/reconnecting — only a
    non-active (e.g. FAILED) session is eligible to be swapped out."""
    account_id = create_account(api_client)
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])

    first = api_client.post(f'/accounts/{account_id}/connect')
    assert first.status_code == 202
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )

    # Change the DB row while the session is live and active.
    import uuid as uuid_module
    fake_repo.update_account(uuid_module.UUID(account_id), device_metadata={
        'app_id': 'changed', 'pack_name': 'p', 'channel_id': 'c',
        'app_version': '1.0.0', 'package_version': '1.0.0', 'os_type': 'win',
    })

    # A second /connect while already connected is still correctly a 409 —
    # the live session must not have been torn down and replaced underneath
    # the already-successful connection.
    second = api_client.post(f'/accounts/{account_id}/connect')
    assert second.status_code == 409
    status = api_client.get(f'/accounts/{account_id}/status').json()
    assert status['live']['state'] == 'connected'
    assert status['live']['authenticated'] is True


def test_reconnect_at_capacity_returns_503(dev_user_email, scripted_sockets):
    """Regression test for the API surface of the AccountManager.reconnect()
    capacity fix: /reconnect must map the same RuntimeError /connect already
    maps to 503, not fall through to a bare 500."""
    manager = AccountManager(max_concurrent_sessions=1)
    app = create_app(lifespan_context=None)
    app.state.repository = InMemoryAccountRepository()
    app.state.account_manager = manager
    app.state.engine = FakeEngine(healthy=True)
    app.state.dashboard_sessions = DashboardSessionStore()

    with TestClient(app) as client:
        account_a = create_account(client)
        account_b = client.post('/accounts', json=account_payload(label='Second', app_uid='uid-456')).json()['id']

        scripted_sockets([
            FakeWarpathSocket([build_login_reply_frame(uid=1)]),
            FakeWarpathSocket([build_login_reply_frame(uid=2)]),
        ])

        # account-a takes the only slot; account-b is registered (via
        # /connect's own capacity check, which already worked) but never
        # gets to start.
        assert client.post(f'/accounts/{account_a}/connect').status_code == 202
        assert wait_until(
            lambda: client.get(f'/accounts/{account_a}/status').json()['live']['state'] == 'connected'
        )
        assert client.post(f'/accounts/{account_b}/connect').status_code == 503

        # account-b has a registered-but-never-started session (AccountManager
        # only raises after registering it — see sessions.py's
        # _ensure_registered), so /reconnect is the path this stage's fix
        # targets: it must ALSO be rejected with 503, not silently succeed
        # or fall through to a bare 500.
        response = client.post(f'/accounts/{account_b}/reconnect')
        assert response.status_code == 503

        manager.stop_all()


def test_sessions_between_two_accounts_are_isolated(api_client, scripted_sockets):
    account_a = create_account(api_client)
    account_b = api_client.post('/accounts', json=account_payload(label='Second', app_uid='uid-456')).json()['id']

    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])

    api_client.post(f'/accounts/{account_a}/connect')
    api_client.post(f'/accounts/{account_b}/connect')

    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_a}/status').json()['live']['state'] == 'connected'
    )
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_b}/status').json()['live']['state'] == 'connected'
    )

    api_client.post(f'/accounts/{account_a}/disconnect')

    status_a = api_client.get(f'/accounts/{account_a}/status').json()
    status_b = api_client.get(f'/accounts/{account_b}/status').json()
    assert status_a['live']['state'] == 'stopped'
    assert status_b['live']['state'] == 'connected'  # untouched by A's disconnect

