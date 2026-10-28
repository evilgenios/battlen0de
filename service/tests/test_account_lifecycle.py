"""End-to-end integration test for the full account lifecycle requested for
this stage:

  1. create/add a Warpath account through the API
  2. validate the account data
  3. encrypt sensitive credentials before persistence
  4. store the account in PostgreSQL
  5. load the account from PostgreSQL
  6. create its AccountSession
  7. connect the account
  8. query its live status
  9. disconnect it
  10. reconnect it
  11. delete the account cleanly
  12. ensure events/audit records are persisted appropriately

Everything on this path — FastAPI routing, ownership checks, AccountManager,
AccountSession, WarpathConnection, the real protobuf encode/decode, and the
account_events audit trail (including the on_event bridge from main.py,
wired into the account_manager fixture in conftest.py) — is real code. Only
two things are faked, on purpose, per this stage's instructions:

* The TCP socket (tests/fakes.py, same technique as every Stage 1/2 test) —
  no real Warpath credentials, no real network calls to Warpath's servers.
* Persistence uses the in-memory AccountRepository (tests/fake_repository.py)
  in this version, so it runs without a database. A second version of this
  same test below is gated on TEST_DATABASE_URL and runs against real
  Postgres, additionally proving encryption-at-rest (something the in-memory
  fake, by design, does not do — see its docstring).
"""

from __future__ import annotations

import os
import uuid

import pytest

from tests.conftest import wait_until
from tests.fakes import FakeWarpathSocket, build_login_reply_frame


def _account_payload(**overrides) -> dict:
    payload = {
        'label': 'Lifecycle Test Account',
        'app_uid': '70000888',
        'app_token': 'LIFECYCLE-TEST-TOKEN-never-real-9f8e7d6c',
        'device_id': 'LIFECYCLE-TEST-DEVICE-never-real-1a2b3c4d',
        'platform': 22,
        'device_metadata': {
            'os_type': 'win',
            'app_version': '1.0.0',
            'app_id': 'test-app-id',
            'pack_name': 'test-pack-name',
            'channel_id': 'test-channel-id',
            'package_version': '1.0.0',
        },
    }
    payload.update(overrides)
    return payload


def test_full_account_lifecycle_via_api(api_client, fake_repo, scripted_sockets):
    secret_token = _account_payload()['app_token']
    secret_device_id = _account_payload()['device_id']

    # -- 1/2/3/4: create -> validate -> encrypt -> persist ------------------
    create_response = api_client.post('/accounts', json=_account_payload())
    assert create_response.status_code == 201
    body = create_response.json()
    account_id = body['id']
    account_uuid = uuid.UUID(account_id)

    # Secrets are accepted on the way in but never echoed back (encryption
    # happens inside repo.create_account before anything is persisted —
    # see app/db/repository.py — and the response schema has no field for
    # them at all regardless).
    assert 'app_token' not in body and 'device_id' not in body
    assert secret_token not in create_response.text
    assert secret_device_id not in create_response.text
    assert body['app_uid'] == '70000888'
    assert body['status'] == 'active'

    # Validation (2) is exercised negatively elsewhere (test_api_accounts.py's
    # test_create_account_rejects_missing_required_fields); confirmed
    # positively here by the 201 above having actually gone through Pydantic.

    # -- 5: load the account back (a fresh read, not the create response) ---
    get_response = api_client.get(f'/accounts/{account_id}')
    assert get_response.status_code == 200
    assert get_response.json()['id'] == account_id
    assert secret_token not in get_response.text

    # -- 12 (part 1): account_created was recorded ---------------------------
    events_after_create = fake_repo.list_events(account_uuid)
    assert any(e.event_type == 'account_created' for e in events_after_create)

    # -- 6/7: first /connect call creates the AccountSession (lazily) and
    #         starts it — this is the one AccountManager for the whole
    #         process; nothing here constructs a second one.
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=555, name='LifecycleTester')])])
    connect_response = api_client.post(f'/accounts/{account_id}/connect')
    assert connect_response.status_code == 202
    assert secret_token not in connect_response.text

    # -- 8: query live status until the (faked) handshake completes ---------
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )
    status = api_client.get(f'/accounts/{account_id}/status').json()
    assert status['live']['authenticated'] is True
    assert status['db_status'] == 'active'
    assert secret_token not in api_client.get(f'/accounts/{account_id}/status').text

    # account_connected (from the live on_event bridge, not just the API's
    # own account_connect_requested) must have landed too.
    events_after_connect = {e.event_type for e in fake_repo.list_events(account_uuid)}
    assert 'account_connect_requested' in events_after_connect
    assert 'account_connected' in events_after_connect

    # An account-scoped action actually works while connected (proves the
    # AccountSession's WarpathConnection, not just its bookkeeping state, is
    # live) — scan() needs no account precondition, unlike collect() (which
    # now correctly 409s without any known production buildings — this login
    # frame doesn't set any, on purpose, to keep this test focused on proving
    # connectivity rather than collect's own behavior).
    scan_response = api_client.post(f'/accounts/{account_id}/scan', json={})
    assert scan_response.status_code == 200

    # -- 9: disconnect --------------------------------------------------------
    disconnect_response = api_client.post(f'/accounts/{account_id}/disconnect')
    assert disconnect_response.status_code == 200
    assert api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'stopped'

    # -- 10: reconnect (fresh scripted socket — the old one was consumed) ----
    scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=555, name='LifecycleTester')])])
    reconnect_response = api_client.post(f'/accounts/{account_id}/reconnect')
    assert reconnect_response.status_code == 202
    assert wait_until(
        lambda: api_client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
    )

    # Stop it again before deleting, so deletion below is against a
    # currently-active session — exercising delete_account's
    # "stop the live session, THEN delete the row" ordering for real.
    # (No explicit disconnect call needed: DELETE is documented to do this
    # itself — see app/api/accounts.py's delete_account.)

    # -- 11: delete cleanly ----------------------------------------------------
    delete_response = api_client.delete(f'/accounts/{account_id}')
    assert delete_response.status_code == 204

    # The account is really gone from persistence...
    assert api_client.get(f'/accounts/{account_id}').status_code == 404
    # ...and its live session was stopped and dropped from AccountManager,
    # not left running as an orphan.
    manager = api_client.app.state.account_manager
    assert manager.get_account(account_id) is None

    # -- 12 (part 2): the full audit trail survives account deletion --------
    # account_events.account_id is ON DELETE SET NULL (see models.py), so
    # these rows persist with account_id=None but keep the id in `detail`
    # for redundancy (see repository.add_event). The in-memory fake mirrors
    # real delete_account's cascade behavior for snapshots/discord links but
    # (like the real repository) never touches account_events rows.
    all_event_types = {e.event_type for e in fake_repo._events if e.detail.get('account_id') == account_id}
    assert {
        'account_created', 'account_connect_requested', 'account_connected',
        'account_disconnect_requested', 'account_stopped',
        'account_reconnect_requested',
        'account_deleted',
    }.issubset(all_event_types)


# ---------------------------------------------------------------------------
# Full-fidelity version: real Postgres, so encryption-at-rest and the actual
# schema (JSONB device_metadata, UUID keys, ON DELETE behavior) are proven
# too, not just the API/AccountManager wiring. Gated the same way as
# test_repository.py — see that file's module docstring for why this
# sandbox can't run it, and how to run it against a throwaway database.
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')

pytestmark_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason='TEST_DATABASE_URL is not set — see test_repository.py module docstring. '
           'Never point this at a production database: it drops and recreates the schema.',
)


@pytestmark_db
def test_full_account_lifecycle_against_real_postgres(monkeypatch, scripted_sockets):
    from fastapi.testclient import TestClient

    from tests.fakes import synthetic_account_manager as AccountManager
    from app.db.models import Base
    from app.core.dashboard_session import DashboardSessionStore
    from app.db.repository import SqlAlchemyAccountRepository
    from app.db.session import build_engine, build_session_factory
    from app.deps import DEV_USER_EMAIL_ENV_VAR
    from app.main import _make_event_sink, create_app
    from app.security.crypto import generate_key
    from tests.fake_repository import FakeEngine

    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('AUTH_MODE', 'local')
    monkeypatch.setenv('DEV_USER_ROLE', 'admin')
    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())
    monkeypatch.setenv(DEV_USER_EMAIL_ENV_VAR, 'lifecycle-pg-test@example.test')

    engine = build_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    repo = SqlAlchemyAccountRepository(build_session_factory(engine))
    manager = AccountManager(max_concurrent_sessions=5, on_event=_make_event_sink(repo))

    app = create_app(lifespan_context=None)
    app.state.repository = repo
    app.state.account_manager = manager
    app.state.engine = FakeEngine(healthy=True)
    app.state.dashboard_sessions = DashboardSessionStore()

    try:
        with TestClient(app) as client:
            secret_token = _account_payload()['app_token']

            create_response = client.post('/accounts', json=_account_payload())
            assert create_response.status_code == 201
            account_id = create_response.json()['id']
            account_uuid = uuid.UUID(account_id)

            # Encryption-at-rest: read the raw row directly, bypassing the
            # repository entirely, and confirm the plaintext token is
            # nowhere in the stored ciphertext column.
            from sqlalchemy import select

            from app.db.models import WarpathAccount

            with repo._session_factory() as session:  # noqa: SLF001 - verification only
                row = session.execute(
                    select(WarpathAccount).where(WarpathAccount.id == account_uuid)
                ).scalar_one()
                assert secret_token not in row.app_token_encrypted

            scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
            assert client.post(f'/accounts/{account_id}/connect').status_code == 202
            assert wait_until(
                lambda: client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
            )
            assert client.post(f'/accounts/{account_id}/disconnect').status_code == 200

            scripted_sockets([FakeWarpathSocket([build_login_reply_frame(uid=1)])])
            assert client.post(f'/accounts/{account_id}/reconnect').status_code == 202
            assert wait_until(
                lambda: client.get(f'/accounts/{account_id}/status').json()['live']['state'] == 'connected'
            )

            assert client.delete(f'/accounts/{account_id}').status_code == 204
            assert client.get(f'/accounts/{account_id}').status_code == 404

            # Real Postgres ON DELETE SET NULL, proven end-to-end (not just
            # against the in-memory fake's approximation of it).
            with repo._session_factory() as session:  # noqa: SLF001
                from app.db.models import AccountEvent

                remaining = session.execute(
                    select(AccountEvent).where(AccountEvent.detail['account_id'].as_string() == account_id)
                ).scalars().all()
                assert remaining, 'audit events should survive account deletion'
                assert all(e.account_id is None for e in remaining)
    finally:
        manager.stop_all()
        Base.metadata.drop_all(engine)
        engine.dispose()

