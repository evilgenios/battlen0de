"""POST /accounts/link/request and /verify: the Lilith email/code linking
flow. Lilith itself is mocked at the module level (app.core.warpath.lilith)
— no real HTTP calls, no real verification emails, no real Warpath
credentials anywhere in this file. See app/api/link.py's module docstring
for the vehicle/bootstrap design these tests exercise.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.core.warpath.lilith import LilithLoginError, LinkSession
# Bound at import time, before any test's autouse mock_lilith fixture
# monkeypatches app.core.warpath.lilith.send_login_code — this stays the
# genuine, un-mocked function for the one regression test that needs it.
from app.core.warpath.lilith import send_login_code as real_send_login_code

FAKE_UID = '70000999'
FAKE_TOKEN = 'TOKEN-FROM-LILITH-NEVER-LOGGED'  # pragma: allowlist secret
GOOD_CODE = '123456'
BAD_CODE = '000000'


def fake_send_login_code(vehicle, email, link_session=None):
    return link_session or LinkSession.new()


def fake_verify_login_code(vehicle, email, code, link_session):
    if code != GOOD_CODE:
        raise LilithLoginError('verification failed: incorrect code')
    return FAKE_UID, FAKE_TOKEN


@pytest.fixture(autouse=True)
def mock_lilith(monkeypatch):
    monkeypatch.setattr('app.api.link.lilith.send_login_code', fake_send_login_code)
    monkeypatch.setattr('app.api.link.lilith.verify_login_code', fake_verify_login_code)


@pytest.fixture(autouse=True)
def no_ambient_vehicle_env(monkeypatch):
    """Defensively ensure ambient environment state can never supply a
    vehicle by accident — vehicle presence must come only from what each
    test explicitly sets up (an existing account, or an explicit env
    override), never from whatever happens to be in this process's real
    environment."""
    monkeypatch.delenv('WARPATH_APP_UID', raising=False)
    monkeypatch.delenv('WARPATH_APP_TOKEN', raising=False)


@pytest.fixture
def existing_vehicle_account(fake_repo, dev_user_email, monkeypatch):
    """Operator-configured synthetic credentials; stored customer is unrelated."""
    monkeypatch.setenv('WARPATH_APP_UID', '500000123')
    monkeypatch.setenv('WARPATH_APP_TOKEN', 'operator-bootstrap-SECRET')
    user = fake_repo.get_or_create_user(dev_user_email)
    return fake_repo.create_account(
        owner_user_id=user.id,
        label='Bootstrap Account',
        app_uid='500000123',
        app_token='token-bootstrap-vehicle-SECRET',
        device_id='device-bootstrap-vehicle-SECRET',
        device_metadata={'os_type': 'win', 'app_id': 'a', 'pack_name': 'p', 'channel_id': 'c',
                          'app_version': '1.0.0', 'package_version': '1.0.0'},
    )


# ---------------------------------------------------------------------------
# 1/2: request endpoint
# ---------------------------------------------------------------------------

def test_link_request_succeeds_and_creates_a_challenge(api_client, existing_vehicle_account, link_challenge_store):
    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})

    assert response.status_code == 202
    body = response.json()
    assert body['email'] == 'newplayer@example.com'
    assert 'challenge_id' in body and body['challenge_id']
    assert body['expires_in_seconds'] > 0

    pending = link_challenge_store.get(body['challenge_id'], api_client.app.state.repository.get_or_create_user('dev-user@example.test').id)
    assert pending is not None
    assert pending.email == 'newplayer@example.com'


def test_link_request_lowercases_and_trims_email(api_client, existing_vehicle_account):
    response = api_client.post('/accounts/link/request', json={'email': '  NewPlayer@Example.COM  '})
    assert response.status_code == 202
    assert response.json()['email'] == 'newplayer@example.com'


def test_link_request_rejects_malformed_email(api_client, existing_vehicle_account):
    response = api_client.post('/accounts/link/request', json={'email': 'not-an-email'})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# First-account bootstrap gap
# ---------------------------------------------------------------------------

def test_link_request_without_any_vehicle_returns_503_with_bootstrap_guidance(api_client, dev_user_email):
    # No existing account, no env-configured session: exactly the fresh-
    # deployment bootstrap gap described in api/link.py's module docstring.
    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert response.status_code == 503
    assert 'operator must configure' in response.text


def test_link_request_uses_env_configured_vehicle_when_no_account_exists(api_client, dev_user_email, monkeypatch):
    monkeypatch.setenv('WARPATH_APP_UID', '500000456')
    monkeypatch.setenv('WARPATH_APP_TOKEN', 'token-env-vehicle-SECRET')

    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# Regression: a malformed vehicle must never reach the Lilith client as an
# unhandled crash. Found live against the real dev deployment: a leftover
# test/dev account with a non-numeric app_uid ('dev-bootstrap-uid') was
# picked as the vehicle, and int(vehicle.app_uid) inside the REAL
# lilith.send_login_code raised an uncaught ValueError -> HTTP 500 -> no
# request ever reached Lilith, so no verification email was ever sent.
# _is_valid_vehicle() in api/link.py now catches this before the Lilith
# client is ever called.
# ---------------------------------------------------------------------------

@pytest.fixture
def malformed_vehicle_account(fake_repo, dev_user_email, monkeypatch):
    """Reproduces the exact shape of the leftover dev/test data that caused
    the live incident: a vehicle-shaped account whose app_uid could never be
    a real Lilith id (Lilith's are always numeric)."""
    monkeypatch.setenv('WARPATH_APP_UID', 'invalid-uid')
    monkeypatch.setenv('WARPATH_APP_TOKEN', 'operator-bootstrap-SECRET')
    user = fake_repo.get_or_create_user(dev_user_email)
    return fake_repo.create_account(
        owner_user_id=user.id,
        label='Malformed Vehicle',
        app_uid='dev-bootstrap-uid',
        app_token='token-malformed-vehicle-SECRET',
        device_id='device-malformed-vehicle-SECRET',
        device_metadata={'os_type': 'win', 'app_id': 'a', 'pack_name': 'p', 'channel_id': 'c',
                          'app_version': '1.0.0', 'package_version': '1.0.0'},
    )


def test_link_request_with_malformed_vehicle_app_uid_returns_503_not_500(api_client, malformed_vehicle_account):
    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})

    assert response.status_code == 503
    assert response.status_code != 500
    assert 'Vehicle session is invalid' in response.text
    # The malformed value and the vehicle's own secret must never leak into
    # the error response.
    assert 'dev-bootstrap-uid' not in response.text
    assert 'token-malformed-vehicle-SECRET' not in response.text


def test_link_request_missing_vehicle_and_invalid_vehicle_get_distinct_messages(api_client, dev_user_email):
    # "No vehicle exists at all" (needs a fresh bootstrap) and "a vehicle
    # exists but is malformed" (needs its credentials fixed/removed) are
    # different situations the operator would fix differently, so they must
    # never collapse into the same message.
    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})

    assert response.status_code == 503
    assert 'operator must configure' in response.text
    assert 'Vehicle session is invalid' not in response.text


def test_link_request_with_valid_numeric_vehicle_reaches_the_real_lilith_client(
    api_client, existing_vehicle_account, monkeypatch
):
    """Uses the REAL app.core.warpath.lilith.send_login_code (bypassing this
    file's module-level fake for just this test) to prove a well-formed,
    numeric vehicle passes _is_valid_vehicle and reaches
    int(vehicle.app_uid) without crashing. Only the HTTP transport
    (_requests_module) is stubbed — no real network call is made, per the
    instruction not to contact the real Lilith API in this change."""
    from app.core.warpath import lilith as real_lilith

    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {'result': {'code': 0}, 'data': {}}

    class _FakeRequestsModule:
        @staticmethod
        def post(url, **kwargs):
            captured['url'] = url
            captured['app_uid'] = kwargs.get('json', {}).get('app_uid')
            return _FakeResponse()

    monkeypatch.setattr('app.api.link.lilith.send_login_code', real_send_login_code)
    monkeypatch.setattr(real_lilith, '_requests_module', lambda: _FakeRequestsModule())

    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})

    assert response.status_code == 202
    assert captured['url'].endswith('/api/park/sdk/account/send_auth_code')
    assert isinstance(captured['app_uid'], int)  # int(vehicle.app_uid) succeeded, no crash


def test_invalid_vehicle_error_never_exposes_credentials(api_client, malformed_vehicle_account):
    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert response.status_code == 503
    assert 'app_token' not in response.text
    assert 'app_uid' not in response.text
    assert 'token-malformed-vehicle-SECRET' not in response.text


# ---------------------------------------------------------------------------
# 6: failed Lilith request (send_login_code)
# ---------------------------------------------------------------------------

def test_link_request_maps_lilith_failure_to_503(api_client, existing_vehicle_account, monkeypatch):
    def raising_send(vehicle, email, link_session=None):
        raise LilithLoginError('Lilith returned an invalid response')

    monkeypatch.setattr('app.api.link.lilith.send_login_code', raising_send)

    response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Rapid/duplicate request submission (rate limiting)
# ---------------------------------------------------------------------------

def test_link_request_twice_quickly_is_rate_limited(api_client, existing_vehicle_account):
    first = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert first.status_code == 202

    second = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert second.status_code == 429


def test_link_request_reuses_the_same_challenge_id_on_resend(api_client, existing_vehicle_account, link_challenge_store):
    link_challenge_store.resend_cooldown_seconds = 0  # allow an immediate resend for this test
    first = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    second = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})

    assert second.status_code == 202
    assert first.json()['challenge_id'] == second.json()['challenge_id']


# ---------------------------------------------------------------------------
# 3/8: successful verification creates the account
# ---------------------------------------------------------------------------

def test_link_verify_succeeds_and_creates_account(api_client, existing_vehicle_account, fake_repo):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})

    assert response.status_code == 201
    body = response.json()
    assert body['linked_email'] == 'newplayer@example.com'
    assert body['app_uid'] == FAKE_UID
    assert body['label'] == 'newplayer@example.com'

    accounts = fake_repo.list_accounts()
    assert any(a.linked_email == 'newplayer@example.com' for a in accounts)


def test_link_verify_uses_custom_label_when_given(api_client, existing_vehicle_account):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    response = api_client.post(
        '/accounts/link/verify',
        json={'challenge_id': challenge_id, 'code': GOOD_CODE, 'label': 'My Alt'},
    )
    assert response.json()['label'] == 'My Alt'


def test_link_verify_pulls_device_metadata_from_env_template(api_client, existing_vehicle_account, monkeypatch):
    monkeypatch.setenv('WARPATH_APP_ID', 'template-app-id')
    monkeypatch.setenv('WARPATH_PACK_NAME', 'template-pack')

    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']
    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})

    metadata = response.json()['device_metadata']
    assert metadata['app_id'] == 'template-app-id'
    assert metadata['pack_name'] == 'template-pack'


# ---------------------------------------------------------------------------
# 4: invalid code
# ---------------------------------------------------------------------------

def test_link_verify_with_wrong_code_is_422_and_does_not_create_an_account(api_client, existing_vehicle_account, fake_repo):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': BAD_CODE})

    assert response.status_code == 422
    assert not any(a.linked_email == 'newplayer@example.com' for a in fake_repo.list_accounts())


def test_link_verify_rejects_non_six_digit_code(api_client, existing_vehicle_account):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': '12'})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 5: expired code / expired challenge
# ---------------------------------------------------------------------------

def test_link_verify_after_challenge_expired_returns_410(api_client, existing_vehicle_account, link_challenge_store):
    link_challenge_store.ttl_seconds = 0
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    import time
    time.sleep(0.01)

    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert response.status_code == 410


def test_link_verify_with_unknown_challenge_id_returns_410(api_client, existing_vehicle_account):
    response = api_client.post(
        '/accounts/link/verify', json={'challenge_id': uuid.uuid4().hex, 'code': GOOD_CODE},
    )
    assert response.status_code == 410


# ---------------------------------------------------------------------------
# 7: failed Lilith verification (network-level, not a wrong code)
# ---------------------------------------------------------------------------

def test_link_verify_maps_lilith_network_failure_to_503(api_client, existing_vehicle_account, monkeypatch):
    from requests.exceptions import ConnectionError as RequestsConnectionError

    def raising_verify(vehicle, email, code, link_session):
        raise RequestsConnectionError('connection refused')

    monkeypatch.setattr('app.api.link.lilith.verify_login_code', raising_verify)

    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']
    response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Rate limiting: too many wrong attempts invalidates the challenge
# ---------------------------------------------------------------------------

def test_too_many_wrong_attempts_invalidates_the_challenge(api_client, existing_vehicle_account, link_challenge_store):
    link_challenge_store.max_attempts = 2
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    for _ in range(2):
        response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': BAD_CODE})
        assert response.status_code == 422

    final = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert final.status_code == 429

    # The challenge is gone even to a correct code afterwards.
    again = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert again.status_code in (410, 429)


# ---------------------------------------------------------------------------
# One-time use: a code cannot verify the same challenge twice
# ---------------------------------------------------------------------------

def test_verify_is_one_time_use(api_client, existing_vehicle_account):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']

    first = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert first.status_code == 201

    second = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
    assert second.status_code == 410


# ---------------------------------------------------------------------------
# 9/10: secrets never appear in responses; codes never persisted/logged
# ---------------------------------------------------------------------------

def test_no_secrets_in_any_link_response(api_client, existing_vehicle_account):
    request_response = api_client.post('/accounts/link/request', json={'email': 'newplayer@example.com'})
    assert FAKE_TOKEN not in request_response.text

    challenge_id = request_response.json()['challenge_id']
    verify_response = api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})

    assert verify_response.status_code == 201
    assert FAKE_TOKEN not in verify_response.text
    assert 'app_token' not in verify_response.json()
    assert 'device_id' not in verify_response.json()
    # The vehicle account's OWN secret must never leak through either.
    assert 'token-bootstrap-vehicle-SECRET' not in verify_response.text


def test_verification_code_is_never_persisted_in_any_event_or_account_record(api_client, existing_vehicle_account, fake_repo):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']
    api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})

    for event in fake_repo._events:  # noqa: SLF001 - direct inspection for this guarantee only
        assert GOOD_CODE not in str(event.detail)
    for account in fake_repo._accounts.values():  # noqa: SLF001
        assert GOOD_CODE not in str(account.device_metadata)


def test_failed_verification_event_does_not_contain_the_code(api_client, existing_vehicle_account, fake_repo):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']
    api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': BAD_CODE})

    failed_events = [e for e in fake_repo._events if e.event_type == 'account_link_failed']  # noqa: SLF001
    assert failed_events
    assert BAD_CODE not in str(failed_events[0].detail)


def test_link_request_and_verify_write_no_secrets_into_events(api_client, existing_vehicle_account, fake_repo):
    challenge_id = api_client.post(
        '/accounts/link/request', json={'email': 'newplayer@example.com'}
    ).json()['challenge_id']
    api_client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})

    for event in fake_repo._events:  # noqa: SLF001
        assert FAKE_TOKEN not in str(event.detail)


# ---------------------------------------------------------------------------
# Real Postgres: proves the Lilith-issued token is genuinely encrypted at
# rest, not just absent from API responses. Gated the same way as
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
def test_credentials_from_lilith_link_are_encrypted_at_rest(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from tests.fakes import synthetic_account_manager as AccountManager
    from app.db.identity_store import PostgresIdentityStore
    from app.core.link_challenge_store import LinkChallengeStore
    from app.db.models import Base, WarpathAccount
    from app.db.repository import SqlAlchemyAccountRepository
    from app.db.session import build_engine, build_session_factory
    from app.deps import DEV_USER_EMAIL_ENV_VAR
    from app.main import create_app
    from app.security.crypto import generate_key
    from tests.fake_repository import FakeEngine

    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())
    monkeypatch.setenv(DEV_USER_EMAIL_ENV_VAR, 'link-encryption-test@example.com')
    monkeypatch.delenv('WARPATH_APP_UID', raising=False)
    monkeypatch.delenv('WARPATH_APP_TOKEN', raising=False)
    monkeypatch.setattr('app.api.link.lilith.send_login_code', fake_send_login_code)
    monkeypatch.setattr('app.api.link.lilith.verify_login_code', fake_verify_login_code)

    engine = build_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    repo = SqlAlchemyAccountRepository(build_session_factory(engine))

    # Bootstrap vehicle: a manually-created account, exactly like a real
    # first-account bootstrap via POST /accounts.
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('AUTH_MODE', 'local')
    monkeypatch.setenv('WARPATH_APP_UID', '500000789')
    monkeypatch.setenv('WARPATH_APP_TOKEN', 'synthetic-operator-token')
    owner = repo.get_or_create_user('link-encryption-test@example.com')
    repo.create_account(
        owner_user_id=owner.id, label='Bootstrap', app_uid='500000789',
        app_token='token-bootstrap-SECRET', device_id='device-bootstrap-SECRET',
    )

    app = create_app(lifespan_context=None)
    app.state.repository = repo
    app.state.account_manager = AccountManager(max_concurrent_sessions=5)
    app.state.link_challenges = LinkChallengeStore()
    app.state.engine = FakeEngine(healthy=True)
    app.state.dashboard_sessions = PostgresIdentityStore(build_session_factory(engine))
    for key, value in {'APP_ID': 'test', 'PACK_NAME': 'test', 'CHANNEL_ID': 'test', 'APP_VERSION': '1',
                       'PACKAGE_VERSION': '1', 'OS_TYPE': 'win'}.items():
        monkeypatch.setenv('WARPATH_' + key, value)

    try:
        with TestClient(app) as client:
            challenge_id = client.post(
                '/accounts/link/request', json={'email': 'newplayer@example.com'}
            ).json()['challenge_id']
            response = client.post('/accounts/link/verify', json={'challenge_id': challenge_id, 'code': GOOD_CODE})
            assert response.status_code == 201
            account_id = response.json()['id']

        with repo._session_factory() as session:  # noqa: SLF001 - verification only
            row = session.execute(
                select(WarpathAccount).where(WarpathAccount.id == uuid.UUID(account_id))
            ).scalar_one()
            assert FAKE_TOKEN not in row.app_token_encrypted
            assert row.app_token_encrypted  # actually encrypted, not blank
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
