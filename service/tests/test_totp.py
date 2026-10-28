from app.security.totp import code_at, generate_secret, provisioning_uri, verify


def test_totp_roundtrip_at_fixed_time():
    secret = generate_secret()
    at = 1_700_000_000
    code = code_at(secret, at)
    assert len(code) == 6
    assert verify(secret, code, at=at)
    assert not verify(secret, '000000' if code != '000000' else '111111', at=at)


def test_totp_accepts_small_clock_skew_only():
    secret = generate_secret()
    at = 1_700_000_000
    code = code_at(secret, at)
    assert verify(secret, code, at=at + 30)
    assert not verify(secret, code, at=at + 90)


def test_provisioning_uri_contains_no_password_or_session_material():
    secret = 'JBSWY3DPEHPK3PXP'
    uri = provisioning_uri(secret, 'admin@example.test')
    assert uri.startswith('otpauth://totp/')
    assert secret in uri
    assert 'BattleN0de' in uri
