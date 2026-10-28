"""Per-account reconnect policy: exponential backoff for a transient drop,
immediate isolation (no auto-retry) for a rejected login, and proof that one
account's reconnect activity never touches another account.
"""

from app.core.account_session import AccountSession, ReconnectPolicy, SessionState
from tests.conftest import wait_until
from tests.fakes import (
    FakeWarpathSocket,
    build_err_info_frame,
    build_login_reply_frame,
)


FAST_POLICY = ReconnectPolicy(
    max_retries=3,
    base_delay_seconds=0.01,
    max_delay_seconds=0.05,
    jitter_seconds=0.01,
)


def test_delay_for_attempt_backs_off_and_caps():
    policy = ReconnectPolicy(base_delay_seconds=1.0, multiplier=2.0, max_delay_seconds=5.0, jitter_seconds=0.0)
    assert policy.delay_for_attempt(1) == 1.0
    assert policy.delay_for_attempt(2) == 2.0
    assert policy.delay_for_attempt(3) == 4.0
    assert policy.delay_for_attempt(4) == 5.0  # capped
    assert policy.delay_for_attempt(10) == 5.0  # still capped


def test_transient_drop_after_auth_is_retried_and_reconnects(make_credentials, scripted_sockets):
    creds = make_credentials('account-a')
    factory = scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)], idle_reads_before_close=1),
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),  # reconnect attempt succeeds and stays up
    ])

    session = AccountSession(creds, reconnect_policy=FAST_POLICY)
    session.start()

    # First connects...
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    # ...then drops and is retried automatically...
    assert wait_until(lambda: len(factory.created) == 2, timeout=3.0)
    # ...and reconnects on the second (scripted) socket.
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    assert session.connection.sock is factory.created[1]

    session.stop()


def test_rejected_login_is_isolated_not_retried(make_credentials, scripted_sockets):
    creds = make_credentials('account-a')
    factory = scripted_sockets([
        FakeWarpathSocket([build_err_info_frame(code=401, info='token invalid')]),
    ])

    # Default policy: max_auth_failures=0 -> never auto-retry an outright
    # login rejection, per the anti-abuse "isolate, don't hammer" guidance.
    session = AccountSession(creds)
    session.start()

    assert wait_until(lambda: session.state == SessionState.RESTRICTED)
    assert 'token invalid' in (session.last_error or '')
    # No second connection attempt was made.
    assert len(factory.created) == 1

    session.stop()


def test_giving_up_after_max_retries_marks_failed(make_credentials, scripted_sockets):
    creds = make_credentials('account-a')
    policy = ReconnectPolicy(max_retries=1, base_delay_seconds=0.01, max_delay_seconds=0.02, jitter_seconds=0.0)
    factory = scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)], idle_reads_before_close=1),
        FakeWarpathSocket([build_login_reply_frame(uid=1)], idle_reads_before_close=1),
    ])

    session = AccountSession(creds, reconnect_policy=policy)
    session.start()

    assert wait_until(lambda: session.state == SessionState.FAILED, timeout=5.0)
    assert len(factory.created) == 2  # one initial + one retry, then gave up

    session.stop()


def test_explicit_stop_then_start_reconnects_for_real(make_credentials, scripted_sockets):
    """Regression test: WarpathConnection.disconnect() sets
    connection.stop_requested and nothing in connection.py ever clears it.
    Before AccountSession.start() was fixed to reset it, calling stop()
    and then start() again (or .reconnect(), which is exactly stop()+
    start()) left every subsequent run() hitting connection.py's own
    `if self.stop_requested: return` guard and silently no-op'ing — the
    session looked like it started (start() returned True, state went to
    CONNECTING) but never actually authenticated. Found while validating
    the full account lifecycle's reconnect step end-to-end via the API."""
    creds = make_credentials('account-a')
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
    ])

    session = AccountSession(creds)
    assert session.start() is True
    assert wait_until(lambda: session.state == SessionState.CONNECTED)

    session.stop()
    assert session.state == SessionState.STOPPED

    assert session.start() is True
    assert wait_until(lambda: session.state == SessionState.CONNECTED), (
        'session never reached CONNECTED again after stop()+start() — '
        'connection.stop_requested was left True from the first stop()'
    )
    assert session.connection.authenticated is True

    session.stop()


def test_reconnect_after_disconnect_actually_reauthenticates(make_credentials, scripted_sockets):
    """Same bug, exercised via AccountSession.reconnect() (stop()+start()
    in one call) rather than the two calls separately."""
    creds = make_credentials('account-a')
    scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),
    ])

    session = AccountSession(creds)
    session.start()
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    session.stop()

    assert session.reconnect() is True
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    assert session.connection.authenticated is True

    session.stop()


def test_one_accounts_reconnect_never_touches_another_account(make_credentials, scripted_sockets):
    creds_a = make_credentials('account-a')
    creds_b = make_credentials('account-b')
    # Sockets are handed out strictly in connect() call order across BOTH
    # sessions, so the script order here matters: A connects first (and
    # will drop+reconnect), then B connects and stays up throughout.
    factory = scripted_sockets([
        FakeWarpathSocket([build_login_reply_frame(uid=1)], idle_reads_before_close=1),  # A initial (drops)
        FakeWarpathSocket([build_login_reply_frame(uid=2)]),                              # B (stays up)
        FakeWarpathSocket([build_login_reply_frame(uid=1)]),                              # A reconnect (stays up)
    ])

    session_a = AccountSession(creds_a, reconnect_policy=FAST_POLICY)
    session_b = AccountSession(creds_b, reconnect_policy=FAST_POLICY)

    session_a.start()
    assert wait_until(lambda: session_a.state == SessionState.CONNECTED)

    session_b.start()
    assert wait_until(lambda: session_b.state == SessionState.CONNECTED)
    assert session_b.connection.sock is factory.created[1]

    # A drops and reconnects on its own schedule; B is never touched by it.
    assert wait_until(lambda: len(factory.created) == 3, timeout=3.0)
    assert wait_until(lambda: session_a.state == SessionState.CONNECTED)
    assert session_a.connection.sock is factory.created[2]

    assert session_b.state == SessionState.CONNECTED
    assert session_b.connection.sock is factory.created[1]
    assert session_b._retry_count == 0

    session_a.stop()
    session_b.stop()
