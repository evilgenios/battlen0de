"""Rotate encrypted BattleN0de secrets to the primary Fernet key.

Usage from service/ after configuring:
  WARPATH_ENCRYPTION_KEYS=new_key,old_key python scripts/rotate_encrypted_secrets.py
  WARPATH_ENCRYPTION_KEYS=new_key,old_key python scripts/rotate_encrypted_secrets.py --apply

Dry-run validates every ciphertext without writing. --apply re-encrypts
Warpath app tokens, device IDs and administrator MFA secrets under the first
key in WARPATH_ENCRYPTION_KEYS. No plaintext secret is printed.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.models import User, WarpathAccount
from app.db.session import build_engine, build_session_factory
from app.security.crypto import decrypt_secret, rotate_secret


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write rotated ciphertext after validating all rows')
    args = parser.parse_args()

    engine = build_engine()
    factory = build_session_factory(engine)

    account_rows = []
    admin_rows = []
    with factory() as db:
        account_rows = list(db.scalars(select(WarpathAccount)).all())
        admin_rows = list(db.scalars(select(User).where(User.mfa_secret_encrypted.is_not(None))).all())

        # Preflight all ciphertexts before any mutation.
        for row in account_rows:
            decrypt_secret(row.app_token_encrypted)
            decrypt_secret(row.device_id_encrypted)
        for row in admin_rows:
            decrypt_secret(row.mfa_secret_encrypted)

    print(f'validated account secrets: {len(account_rows)} accounts')
    print(f'validated admin MFA secrets: {len(admin_rows)} admins')

    if not args.apply:
        print('dry run only; use --apply after verifying the configured keyring and database backup')
        return

    with factory.begin() as db:
        for row in db.scalars(select(WarpathAccount)).all():
            row.app_token_encrypted = rotate_secret(row.app_token_encrypted)
            row.device_id_encrypted = rotate_secret(row.device_id_encrypted)
        for row in db.scalars(select(User).where(User.mfa_secret_encrypted.is_not(None))).all():
            row.mfa_secret_encrypted = rotate_secret(row.mfa_secret_encrypted)

    print('rotation applied successfully; keep the previous key in the keyring until this transaction is verified')
    engine.dispose()


if __name__ == '__main__':
    main()
