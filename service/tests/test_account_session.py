"""AccountSession lifecycle and concurrent-session isolation.

The socket is faked (tests/fakes.py); AccountSession, WarpathConnection, and
the real protocol/decoding path are all real and exercised as written.
"""

from app.core.account_session import AccountSession, ReconnectPolicy, SessionState
from tests.conftest import wait_until
from tests.fakes import FakeWarpathSocket, build_login_reply_frame


def test_session_starts_idle(make_credentials):
    session = AccountSession(make_credentials('account-a'))
    assert session.state == SessionState.IDLE
    assert not session.is_active


def test_session_reaches_connected_on_successful_login(make_credentials, scripted_sockets):
    creds = make_credentials('account-a')
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=111)])])

    session = AccountSession(creds)
    assert session.start() is True
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    assert session.connection.authenticated is True
    assert session.connection.account_snapshot['uid'] == 111
    assert session.last_connected_at is not None

    session.stop()
    assert session.state == SessionState.STOPPED


def test_start_is_a_noop_while_already_running(make_credentials, scripted_sockets):
    creds = make_credentials('account-a')
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=111)])])

    session = AccountSession(creds)
    assert session.start() is True
    assert session.start() is False  # already running
    session.stop()


def test_start_fails_fast_on_incomplete_credentials(make_credentials):
    creds = make_credentials('account-a', app_token='')
    session = AccountSession(creds)

    assert session.start() is False
    assert session.state == SessionState.FAILED
    assert 'app_token' in session.last_error


def test_each_session_owns_its_own_connection_instance(make_credentials):
    session_a = AccountSession(make_credentials('account-a'))
    session_b = AccountSession(make_credentials('account-b'))

    assert session_a.connection is not session_b.connection
    assert session_a.credentials is not session_b.credentials
    assert session_a.credentials.account_id != session_b.credentials.account_id


def test_two_sessions_connect_concurrently_with_independent_sockets(make_credentials, scripted_sockets):
    creds_a = make_credentials('account-a')
    creds_b = make_credentials('account-b')
    factory = scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),
    ])

    session_a = AccountSession(creds_a)
    session_b = AccountSession(creds_b)

    assert session_a.start() is True
    assert session_b.start() is True

    assert wait_until(lambda: session_a.state == SessionState.CONNECTED)
    assert wait_until(lambda: session_b.state == SessionState.CONNECTED)

    # Two distinct sockets were opened — one per account, never shared.
    assert len(factory.created) == 2
    assert factory.created[0] is not factory.created[1]
    assert session_a.connection.sock is factory.created[0]
    assert session_b.connection.sock is factory.created[1]

    session_a.stop()
    session_b.stop()


def test_stopping_one_session_does_not_affect_another(make_credentials, scripted_sockets):
    creds_a = make_credentials('account-a')
    creds_b = make_credentials('account-b')
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=2)], idle_reads_before_close=None),
    ])

    session_a = AccountSession(creds_a)
    session_b = AccountSession(creds_b, reconnect_policy=ReconnectPolicy(max_retries=0))

    session_a.start()
    session_b.start()
    assert wait_until(lambda: session_a.state == SessionState.CONNECTED)
    assert wait_until(lambda: session_b.state == SessionState.CONNECTED)

    session_a.stop()

    assert session_a.state == SessionState.STOPPED
    # B was never touched by A's stop() call.
    assert session_b.state == SessionState.CONNECTED
    assert session_b.connection.authenticated is True

    session_b.stop()


def test_status_reports_this_sessions_own_state_only(make_credentials):
    session_a = AccountSession(make_credentials('account-a', label='Alpha'))
    status = session_a.status()
    assert status['account_id'] == 'account-a'
    assert status['label'] == 'Alpha'
    assert status['state'] == SessionState.IDLE.value
