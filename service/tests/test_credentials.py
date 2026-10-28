"""Credential isolation and validation.

No real credentials appear anywhere in this file — every value below is an
obviously-fake test placeholder (see tests/conftest.py:fake_credentials).
"""

from app.core.warpath.credentials import WarpathCredentials, redact_secrets


def test_from_env_reads_prefixed_variables():
    env = {
        'WARPATH_A_APP_UID': 'uid-a',
        'WARPATH_A_APP_TOKEN': 'token-a-SECRET',
        'WARPATH_A_DEVICE_ID': 'device-a-SECRET',
        'WARPATH_A_PLATFORM': '22',
        'WARPATH_A_APP_ID': 'app-id-a',
        'WARPATH_A_PACK_NAME': 'pack-a',
        'WARPATH_A_CHANNEL_ID': 'channel-a',
        'WARPATH_A_APP_VERSION': '1.0.0',
        'WARPATH_A_PACKAGE_VERSION': '1.0.0',
    }
    creds = WarpathCredentials.from_env('account-a', prefix='WARPATH_A_', env=env)

    assert creds.account_id == 'account-a'
    assert creds.app_uid == 'uid-a'
    assert creds.app_token == 'token-a-SECRET'
    assert creds.device_id == 'device-a-SECRET'
    assert creds.platform == 22
    # PC platform defaults device_model/os_type to 'win' when not supplied.
    assert creds.os_type == 'win'


def test_from_env_two_prefixes_do_not_cross_contaminate():
    env = {
        'WARPATH_A_APP_UID': 'uid-a',
        'WARPATH_A_APP_TOKEN': 'token-a-SECRET',
        'WARPATH_A_DEVICE_ID': 'device-a-SECRET',
        'WARPATH_B_APP_UID': 'uid-b',
        'WARPATH_B_APP_TOKEN': 'token-b-SECRET',
        'WARPATH_B_DEVICE_ID': 'device-b-SECRET',
    }
    creds_a = WarpathCredentials.from_env('account-a', prefix='WARPATH_A_', env=env)
    creds_b = WarpathCredentials.from_env('account-b', prefix='WARPATH_B_', env=env)

    assert creds_a.app_uid == 'uid-a'
    assert creds_b.app_uid == 'uid-b'
    assert creds_a.app_token != creds_b.app_token
    assert creds_a.device_id != creds_b.device_id
    assert creds_a.account_id != creds_b.account_id


def test_credentials_are_immutable_value_objects(make_credentials):
    creds = make_credentials('account-a')
    updated = creds.with_updates(app_token='token-a-ROTATED')

    # Original instance is untouched by with_updates(); this is what makes
    # it safe to hand the same WarpathCredentials to a WarpathConnection
    # without either side mutating shared state out from under the other.
    assert creds.app_token != updated.app_token
    assert creds.account_id == updated.account_id


def test_validation_errors_catch_missing_required_fields():
    incomplete = WarpathCredentials(
        account_id='account-a',
        app_uid='',
        app_token='',
        device_id='',
    )
    errors = incomplete.validation_errors()
    assert any('app_uid' in e for e in errors)
    assert any('app_token' in e for e in errors)
    assert any('device_id' in e for e in errors)


def test_validation_errors_empty_for_complete_credentials(make_credentials):
    creds = make_credentials('account-a')
    assert creds.validation_errors() == []


def test_redact_secrets_scrubs_only_that_accounts_values(make_credentials):
    creds_a = make_credentials('account-a')
    creds_b = make_credentials('account-b')

    message = f'server said: token={creds_a.app_token} device={creds_a.device_id}'
    redacted = redact_secrets(message, creds_a)

    assert creds_a.app_token not in redacted
    assert creds_a.device_id not in redacted
    assert '<redacted>' in redacted

    # redact_secrets(text, creds_b) must NOT redact account A's secrets —
    # each account's redaction is scoped to the credentials it's given.
    not_redacted = redact_secrets(message, creds_b)
    assert creds_a.app_token in not_redacted
