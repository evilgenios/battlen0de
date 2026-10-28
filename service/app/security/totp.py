"""Small RFC 6238 TOTP helper used for administrator MFA.

No TOTP secret is stored in plaintext: callers encrypt it before persistence.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote


def generate_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode('ascii').rstrip('=')


def _decode(secret: str) -> bytes:
    padded = secret + '=' * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded.upper(), casefold=True)


def code_at(secret: str, at: int | None = None, *, step: int = 30, digits: int = 6) -> str:
    moment = int(time.time() if at is None else at)
    counter = moment // step
    digest = hmac.new(_decode(secret), struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)


def verify(secret: str, candidate: str | None, *, window: int = 1, at: int | None = None) -> bool:
    if not candidate or len(candidate) != 6 or not candidate.isdigit():
        return False
    moment = int(time.time() if at is None else at)
    return any(hmac.compare_digest(code_at(secret, moment + delta * 30), candidate) for delta in range(-window, window + 1))


def provisioning_uri(secret: str, email: str, *, issuer: str = 'BattleN0de') -> str:
    label = quote(f'{issuer}:{email}')
    return f'otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30'
