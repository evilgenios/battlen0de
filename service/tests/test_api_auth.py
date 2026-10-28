"""Session authentication with synthetic password users and no database."""

from __future__ import annotations

import pytest

from app.security.passwords import hash_password
from tests.test_api_sessions import create_account


@pytest.fixture(autouse=True)
def cookies_over_plain_http(api_client, monkeypatch):
    """TestClient talks to http://testserver, not https:// — a real browser
    (and httpx's cookie jar) correctly refuses to send a Secure cookie back
    over plain http, so the session would never round-trip in tests without
    this. Production keeps the default (Secure=true) — see api/auth.py's
    _cookie_secure()."""
    monkeypatch.setenv('DASHBOARD_COOKIE_SECURE', 'false')
    monkeypatch.setenv('AUTH_MODE', 'session')


def make_admin(fake_repo, email='admin@example.com', password='correct horse battery staple'):
    fake_repo.set_user_password(email, password_hash=hash_password(password), role='admin')
    return email, password


def login(api_client, email, password):
    return api_client.post('/auth/login', json={'email': email, 'password': password})


def test_anonymous_denied_before_any_password_user_exists(api_client):
    assert api_client.get('/accounts').status_code == 401
    assert api_client.get('/health').json()['auth_required'] is True


def test_unauthenticated_request_is_rejected_once_a_dashboard_user_exists(api_client, fake_repo):
    make_admin(fake_repo)
    response = api_client.get('/accounts')
    assert response.status_code == 401


def test_invalid_credentials_rejected(api_client, fake_repo):
    email, _password = make_admin(fake_repo)
    response = login(api_client, email, 'wrong password entirely')
    assert response.status_code == 401
    assert 'wrong password entirely' not in response.text


def test_unknown_email_still_pays_the_full_hash_cost(api_client, fake_repo, monkeypatch):
    """Regression test: login() must call verify_password() even for an
    email that doesn't exist, against a dummy hash — otherwise an unknown
    email short-circuits before ever hashing, and a real email with a wrong
    password always pays the full scrypt cost, making the two cases
    distinguishable by response time (email enumeration via timing)."""
    make_admin(fake_repo)  # at least one real dashboard user exists

    import app.api.auth as auth_module
    calls = []
    original = auth_module.verify_password

    def spy(password, stored_hash):
        calls.append(stored_hash)
        return original(password, stored_hash)

    monkeypatch.setattr(auth_module, 'verify_password', spy)

    login(api_client, 'definitely-not-a-real-admin@example.com', 'whatever')

    assert len(calls) == 1
    assert calls[0] == auth_module._DUMMY_PASSWORD_HASH


def test_unknown_email_rejected_with_the_same_generic_message(api_client, fake_repo):
    make_admin(fake_repo)
    response = login(api_client, 'nobody@example.com', 'whatever')
    assert response.status_code == 401
    assert response.json()['detail'] == 'invalid email or password'


def test_valid_credentials_accepted_and_set_cookies(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    response = login(api_client, email, password)
    assert response.status_code == 200
    body = response.json()
    assert body['email'] == email
    assert body['role'] == 'admin'
    assert 'dashboard_session' in response.cookies
    assert 'dashboard_csrf' in response.cookies
    # The password must never be echoed back anywhere in the response.
    assert password not in response.text


def test_session_persists_across_requests_after_login(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    # api_client is a single TestClient instance — cookies persist on it
    # like a real browser session, so a plain GET now succeeds.
    response = api_client.get('/accounts')
    assert response.status_code == 200


def test_me_reports_the_logged_in_user(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    response = api_client.get('/auth/me')
    assert response.status_code == 200
    body = response.json()
    assert body['email'] == email
    assert body['role'] == 'admin'
    assert body['active_sessions'] == 1
    assert body['plan'] == 'alliance'
    assert body['max_accounts'] == 5
    assert body['max_active_accounts'] == 2


def test_me_active_sessions_reflects_multiple_logins(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    # A second login (e.g. another tab/device) creates a second session —
    # the count is process-wide, not per-cookie.
    api_client.app.state.dashboard_sessions.create(user_id=api_client.app.state.dashboard_sessions.get(
        api_client.cookies.get('dashboard_session')
    ).user_id, email=email, role='admin')
    response = api_client.get('/auth/me')
    assert response.json()['active_sessions'] == 2


def test_me_without_a_session_is_401(api_client, fake_repo):
    make_admin(fake_repo)
    response = api_client.get('/auth/me')
    assert response.status_code == 401


def test_logout_invalidates_the_session(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    assert api_client.get('/accounts').status_code == 200

    logout_response = api_client.post('/auth/logout', headers={'x-csrf-token': api_client.cookies.get('dashboard_csrf')})
    assert logout_response.status_code == 204

    assert api_client.get('/accounts').status_code == 401


def test_auth_does_not_depend_on_password_user_enumeration(api_client, fake_repo, monkeypatch):
    def forbidden():
        raise AssertionError('Authentication must not enumerate password users')
    monkeypatch.setattr(fake_repo, 'list_dashboard_users', forbidden)
    for _ in range(3):
        assert api_client.get('/accounts').status_code == 401
    assert api_client.get('/health').json()['auth_required'] is True


def test_authorized_dashboard_admin_can_access_another_owners_account(api_client, fake_repo):
    """All three dashboard admins manage every platform account (explicit
    role check in get_owned_account) — this is not a bypass of ownership,
    it's the documented 3-admin model."""
    other_user = fake_repo.get_or_create_user('someone-else@example.com')
    other_account = fake_repo.create_account(
        owner_user_id=other_user.id, label='Not Mine', app_uid='999', app_token='t', device_id='d',
    )
    email, password = make_admin(fake_repo)
    login(api_client, email, password)

    response = api_client.get(f'/accounts/{other_account.id}')
    assert response.status_code == 200


def test_mutating_request_without_csrf_header_is_rejected(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    # No x-csrf-token header attached.
    response = api_client.post('/accounts/mass-deploy/cancel')
    assert response.status_code == 403


def test_mutating_request_with_correct_csrf_header_succeeds(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    csrf_token = api_client.cookies.get('dashboard_csrf')
    response = api_client.post('/accounts/mass-deploy/cancel', headers={'x-csrf-token': csrf_token})
    assert response.status_code == 200


def test_get_requests_never_require_csrf(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    login(api_client, email, password)
    response = api_client.get('/accounts')
    assert response.status_code == 200


def test_admin_with_mfa_enabled_requires_valid_totp(api_client, fake_repo):
    email, password = make_admin(fake_repo)
    user = fake_repo.get_user_by_email(email)
    api_client.app.state.admin_store._mfa[user.id] = True

    missing = api_client.post('/auth/login', json={'email': email, 'password': password})
    assert missing.status_code == 401
    assert missing.json()['detail'] == 'mfa required'

    wrong = api_client.post('/auth/login', json={'email': email, 'password': password, 'mfa_code': '000000'})
    assert wrong.status_code == 401

    valid = api_client.post('/auth/login', json={'email': email, 'password': password, 'mfa_code': '123456'})
    assert valid.status_code == 200
    assert 'dashboard_session' in valid.cookies
