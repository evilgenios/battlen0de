#!/usr/bin/env python3
"""Provision a dashboard password user with an explicit member/admin role.

No signup API. Example (operator action, writes to the configured database):
    python scripts/bootstrap_dashboard_admins.py --email alice@example.com --role admin

Passwords are prompted twice, hashed immediately, never accepted in argv.
Existing users are updated. Production authentication is always enforced,
including before provisioning. Changing a password/role does NOT revoke
existing in-memory sessions; restart the single worker when revocation is
required until durable revocation is implemented in a later phase.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # service/ on sys.path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--email', required=True, help='Dashboard login email')
    parser.add_argument('--role', required=True, choices=['member', 'admin'], help='Explicit privilege level')
    args = parser.parse_args()

    from app.db.repository import SqlAlchemyAccountRepository
    from app.db.session import build_engine, build_session_factory
    from app.security.passwords import hash_password

    password = getpass.getpass(f'New password for {args.email}: ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        print('Passwords did not match; nothing was changed.', file=sys.stderr)
        sys.exit(1)
    if len(password) < 12:
        print('Use a password of at least 12 characters.', file=sys.stderr)
        sys.exit(1)

    engine = build_engine()
    try:
        repo = SqlAlchemyAccountRepository(build_session_factory(engine))
        password_hash = hash_password(password)
        user = repo.set_user_password(args.email, password_hash=password_hash, role=args.role)
        print(f'Dashboard login ready: {user.email} (role={user.role}).')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
