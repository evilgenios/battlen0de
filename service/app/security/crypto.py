"""Application-level authenticated encryption for secrets at rest.

Primary production configuration:
- WARPATH_ENCRYPTION_KEYS: comma-separated Fernet keys, newest first.
- WARPATH_ENCRYPTION_KEY: legacy single-key fallback.

Encryption always uses the first configured key. Decryption accepts any key
in the keyring, enabling safe rotation without forcing account relinks.
"""

from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

ENCRYPTION_KEY_ENV_VAR = 'WARPATH_ENCRYPTION_KEY'
ENCRYPTION_KEYS_ENV_VAR = 'WARPATH_ENCRYPTION_KEYS'


class EncryptionKeyError(RuntimeError):
    """Encryption key configuration is missing or malformed."""


class DecryptionError(RuntimeError):
    """Ciphertext could not be decrypted/authenticated."""


def generate_key() -> str:
    return Fernet.generate_key().decode('ascii')


def _single(key: str | bytes) -> Fernet:
    try:
        return Fernet(key.encode('ascii') if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise EncryptionKeyError('configured Fernet key is invalid') from exc


def _key_values(key: Optional[str] = None) -> list[str]:
    if key is not None:
        return [key]
    multi = os.environ.get(ENCRYPTION_KEYS_ENV_VAR, '').strip()
    if multi:
        values = [value.strip() for value in multi.split(',') if value.strip()]
        if values:
            return values
    legacy = os.environ.get(ENCRYPTION_KEY_ENV_VAR, '').strip()
    if legacy:
        return [legacy]
    raise EncryptionKeyError(
        f'{ENCRYPTION_KEYS_ENV_VAR} or {ENCRYPTION_KEY_ENV_VAR} must be set. '
        'Generate Fernet keys with app.security.crypto.generate_key().'
    )


def _multi(key: Optional[str] = None) -> MultiFernet:
    return MultiFernet([_single(value) for value in _key_values(key)])


def encrypt_secret(plaintext: str, *, key: Optional[str] = None) -> str:
    if plaintext is None:
        raise ValueError('cannot encrypt None')
    return _multi(key).encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt_secret(ciphertext: str, *, key: Optional[str] = None) -> str:
    if ciphertext is None:
        raise ValueError('cannot decrypt None')
    try:
        plaintext = _multi(key).decrypt(ciphertext.encode('ascii'))
    except InvalidToken as exc:
        raise DecryptionError(
            'ciphertext could not be authenticated; it may be corrupt or encrypted under a key not present in the configured keyring'
        ) from exc
    return plaintext.decode('utf-8')


def rotate_secret(ciphertext: str) -> str:
    """Re-encrypt a Fernet token under the first configured key.

    The current keyring must include whichever older key encrypted the token.
    """
    if ciphertext is None:
        raise ValueError('cannot rotate None')
    try:
        return _multi().rotate(ciphertext.encode('ascii')).decode('ascii')
    except InvalidToken as exc:
        raise DecryptionError('ciphertext could not be rotated with the configured keyring') from exc
