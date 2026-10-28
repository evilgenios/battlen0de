"""Dashboard login password hashing.

Uses `hashlib.scrypt` (stdlib, no new dependency) — a memory-hard KDF
suitable for password hashing, the same reasoning this project already
applies to app/security/crypto.py's choice of Fernet over hand-rolled AES:
a well-vetted standard-library primitive built for exactly this job, rather
than adding a new third-party dependency (passlib/bcrypt) for a
three-account login system.

Stored format: `scrypt$n$r$p$<salt-b64>$<hash-b64>` — the KDF parameters
are embedded so they can be tuned later without invalidating existing
hashes (verify_password reads them back out instead of assuming constants).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_N = 2**14  # CPU/memory cost
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    if not password:
        raise ValueError('password must not be empty')
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return '$'.join([
        'scrypt', str(_N), str(_R), str(_P),
        base64.b64encode(salt).decode('ascii'),
        base64.b64encode(derived).decode('ascii'),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n_str, r_str, p_str, salt_b64, hash_b64 = stored_hash.split('$')
        if scheme != 'scrypt':
            return False
        n, r, p = int(n_str), int(r_str), int(p_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    derived = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=n, r=r, p=p, dklen=len(expected))
    return hmac.compare_digest(derived, expected)
