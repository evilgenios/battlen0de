"""encrypt_secret()/decrypt_secret(): roundtrip, key isolation, and proof
this is authenticated encryption (tampering is detected, not silently
decrypted into garbage)."""

import base64

import pytest

from app.security.crypto import (
    DecryptionError,
    EncryptionKeyError,
    decrypt_secret,
    encrypt_secret,
    generate_key,
)


def test_roundtrip():
    key = generate_key()
    ciphertext = encrypt_secret('super-secret-token', key=key)
    assert decrypt_secret(ciphertext, key=key) == 'super-secret-token'


def test_ciphertext_does_not_contain_plaintext():
    key = generate_key()
    ciphertext = encrypt_secret('super-secret-token', key=key)
    assert 'super-secret-token' not in ciphertext


def test_encryption_is_randomized():
    """Authenticated-encryption schemes (Fernet included) use a fresh IV per
    call, so the same plaintext never produces the same ciphertext twice —
    this is what stops an attacker from spotting two accounts that share a
    token just by comparing ciphertext bytes."""
    key = generate_key()
    a = encrypt_secret('same-value', key=key)
    b = encrypt_secret('same-value', key=key)
    assert a != b
    assert decrypt_secret(a, key=key) == decrypt_secret(b, key=key) == 'same-value'


def test_decrypting_with_the_wrong_key_fails_closed():
    key_a = generate_key()
    key_b = generate_key()
    ciphertext = encrypt_secret('secret', key=key_a)
    with pytest.raises(DecryptionError):
        decrypt_secret(ciphertext, key=key_b)


def test_tampered_ciphertext_is_rejected_not_silently_decrypted():
    """The core authenticated-encryption property: flipping a byte in the
    ciphertext must be DETECTED (raise), never produce different-but-valid-
    looking plaintext."""
    key = generate_key()
    ciphertext = encrypt_secret('secret-value', key=key)
    raw = bytearray(base64.urlsafe_b64decode(ciphertext))
    raw[-5] ^= 0xFF  # flip bits well inside the HMAC-covered region
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode('ascii')
    with pytest.raises(DecryptionError):
        decrypt_secret(tampered, key=key)


def test_truncated_ciphertext_is_rejected():
    key = generate_key()
    ciphertext = encrypt_secret('secret-value', key=key)
    with pytest.raises(DecryptionError):
        decrypt_secret(ciphertext[:-4], key=key)


def test_missing_key_raises_encryption_key_error(monkeypatch):
    monkeypatch.delenv('WARPATH_ENCRYPTION_KEY', raising=False)
    with pytest.raises(EncryptionKeyError):
        encrypt_secret('value')
    with pytest.raises(EncryptionKeyError):
        decrypt_secret('doesnt-matter')


def test_malformed_key_raises_encryption_key_error():
    with pytest.raises(EncryptionKeyError):
        encrypt_secret('value', key='not-a-valid-fernet-key')


def test_key_read_from_environment_variable(monkeypatch):
    key = generate_key()
    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', key)
    ciphertext = encrypt_secret('value-from-env-key')
    assert decrypt_secret(ciphertext) == 'value-from-env-key'


def test_keyring_decrypts_old_ciphertext_and_encrypts_with_primary(monkeypatch):
    old_key = generate_key()
    new_key = generate_key()
    old_ciphertext = encrypt_secret('rotation-value', key=old_key)

    monkeypatch.setenv('WARPATH_ENCRYPTION_KEYS', f'{new_key},{old_key}')
    monkeypatch.delenv('WARPATH_ENCRYPTION_KEY', raising=False)

    assert decrypt_secret(old_ciphertext) == 'rotation-value'
    new_ciphertext = encrypt_secret('new-value')
    assert decrypt_secret(new_ciphertext, key=new_key) == 'new-value'
    with pytest.raises(DecryptionError):
        decrypt_secret(new_ciphertext, key=old_key)


def test_missing_keyring_and_legacy_key_fails_closed(monkeypatch):
    monkeypatch.delenv('WARPATH_ENCRYPTION_KEYS', raising=False)
    monkeypatch.delenv('WARPATH_ENCRYPTION_KEY', raising=False)
    with pytest.raises(EncryptionKeyError):
        encrypt_secret('value')
