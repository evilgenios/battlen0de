"""AccountManager add/remove/start/stop, concurrency cap, and broadcast."""

import pytest

from tests.fakes import synthetic_account_manager as AccountManager
from app.core.account_session import SessionState
from tests.conftest import wait_until
from tests.fakes import FakeWarpathSocket, build_login_reply_frame


def test_add_and_get_account(make_credentials):
    manager = AccountManager()
    session = manager.add_account(make_credentials('account-a'))
    assert manager.get_account('account-a') is session
    assert manager.get_account('missing') is None


def test_add_account_rejects_duplicate_id(make_credentials):
    manager = AccountManager()
    manager.add_account(make_credentials('account-a'))
    with pytest.raises(ValueError):
        manager.add_account(make_credentials('account-a'))


def test_remove_account_stops_it_first(make_credentials, scripted_sockets):
    manager = AccountManager()
    manager.add_account(make_credentials('account-a'))
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])

    manager.start('account-a')
    session = manager.get_account('account-a')
    assert wait_until(lambda: session.state == SessionState.CONNECTED)

    manager.remove_account('account-a')
    assert manager.get_account('account-a') is None
    assert session.state == SessionState.STOPPED


def test_start_unknown_account_raises_keyerror():
    manager = AccountManager()
    with pytest.raises(KeyError):
        manager.start('does-not-exist')


def test_list_accounts_and_list_active(make_credentials, scripted_sockets):
    manager = AccountManager()
    manager.add_account(make_credentials('account-a'))
    manager.add_account(make_credentials('account-b'))
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])

    manager.start('account-a')
    assert wait_until(
        lambda: manager.get_account('account-a').state == SessionState.CONNECTED
    )

    all_accounts = {row['account_id'] for row in manager.list_accounts()}
    active_accounts = {row['account_id'] for row in manager.list_active()}
    assert all_accounts == {'account-a', 'account-b'}
    assert active_accounts == {'account-a'}

    manager.stop('account-a')


def test_max_concurrent_sessions_is_enforced(make_credentials, scripted_sockets):
    manager = AccountManager(max_concurrent_sessions=1)
    manager.add_account(make_credentials('account-a'))
    manager.add_account(make_credentials('account-b'))
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])

    manager.start('account-a')
    assert wait_until(
        lambda: manager.get_account('account-a').state == SessionState.CONNECTED
    )

    with pytest.raises(RuntimeError, match='max_concurrent_sessions'):
        manager.start('account-b')

    manager.stop('account-a')


def test_max_concurrent_sessions_is_enforced_for_reconnect(make_credentials, scripted_sockets):
    """Regression test: AccountManager.reconnect() used to call
    session.reconnect() directly with no capacity check at all, so a
    stopped/failed account could be reconnected even while the manager was
    already at max_concurrent_sessions — the exact gap start() was supposed
    to close but didn't, for this second entry point."""
    manager = AccountManager(max_concurrent_sessions=1)
    manager.add_account(make_credentials('account-a'))
    manager.add_account(make_credentials('account-b'))
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])

    # account-a takes the one available slot...
    manager.start('account-a')
    assert wait_until(lambda: manager.get_account('account-a').state == SessionState.CONNECTED)

    # ...and account-b, which has never been started (so it's not "already
    # active" and reconnecting it is equivalent to a fresh connect), must be
    # rejected by reconnect() exactly like start() would reject it.
    with pytest.raises(RuntimeError, match='max_concurrent_sessions'):
        manager.reconnect('account-b')
    assert manager.get_account('account-b').state == SessionState.IDLE

    manager.stop('account-a')


def test_reconnecting_an_already_active_session_does_not_count_against_itself(make_credentials, scripted_sockets):
    """An account that already holds the (only) slot must still be able to
    reconnect itself — it's cycling its own slot, not requesting a new one.
    Confirms the capacity check excludes the session being reconnected."""
    manager = AccountManager(max_concurrent_sessions=1)
    manager.add_account(make_credentials('account-a'))
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),  # the reconnect
    ])

    manager.start('account-a')
    assert wait_until(lambda: manager.get_account('account-a').state == SessionState.CONNECTED)

    assert manager.reconnect('account-a') is True
    assert wait_until(lambda: manager.get_account('account-a').state == SessionState.CONNECTED)

    manager.stop('account-a')


def test_reconnect_unknown_account_raises_keyerror():
    manager = AccountManager()
    with pytest.raises(KeyError):
        manager.reconnect('does-not-exist')


def test_broadcast_isolates_a_failing_account_from_the_others(make_credentials, scripted_sockets):
    manager = AccountManager()
    manager.add_account(make_credentials('account-a'))
    manager.add_account(make_credentials('account-b'))
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])

    manager.start('account-a')
    manager.start('account-b')
    assert wait_until(
        lambda: manager.get_account('account-a').state == SessionState.CONNECTED
        and manager.get_account('account-b').state == SessionState.CONNECTED
    )

    def action(session):
        if session.account_id == 'account-a':
            raise RuntimeError('boom')
        return 'ok'

    results = manager.broadcast(action)

    assert isinstance(results['account-a'], RuntimeError)
    assert results['account-b'] == 'ok'

    manager.stop('account-a')
    manager.stop('account-b')


def test_broadcast_only_active_skips_stopped_sessions(make_credentials):
    manager = AccountManager()
    manager.add_account(make_credentials('account-a'))
    manager.add_account(make_credentials('account-b'))

    results = manager.broadcast(lambda session: 'called', only_active=True)
    assert results == {}

