#!/usr/bin/env python3
"""ONE-TIME migration: warpath_accounts.json (legacy bot's plaintext
account store) -> PostgreSQL (encrypted, per the Stage 3 schema).

Never prints app_token or device_id, in any mode, at any verbosity —
verified by tests/test_migrate_json_accounts.py, which captures this
script's stdout and asserts real secret values never appear in it.

Usage:
    python scripts/migrate_json_accounts.py \\
        --json-path ../../warpath-audit/ughhhh/warpath_accounts.json \\
        --owner-email you@example.com \\
        --env-file ../../warpath-audit/ughhhh/.env \\
        --dry-run

Drop --dry-run to actually write to the database (DATABASE_URL and
WARPATH_ENCRYPTION_KEY must be set). Add --force to update an existing
account's credentials in place instead of skipping it as a duplicate
(matched by linked_email or app_uid).

Why --owner-email is required: warpath_accounts.json has no concept of a
platform user, only a list of linked Warpath accounts. Every account
imported by one run of this script is attached to the one owner you name.

Why --env-file: warpath_accounts.json only ever stored app_uid/app_token/
device_id/linked_at — the legacy bot's platform/device metadata (app_id,
pack_name, channel_id, app_version, ...) lived in ONE shared .env, used for
every account that bot ever connected as. This script reads that same set
of WARPATH_* variables once and applies it as the device_metadata for every
account it imports, because that no-per-account-metadata origin is a real
limitation of the source data, not something this script can invent an
answer for. If a migrated account fails to connect after Stage 3 is live,
double-check that its device_metadata actually matches the client
session it was really linked from.

This script never modifies or deletes the original JSON file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # service/ on sys.path

from app.db.repository import SqlAlchemyAccountRepository  # noqa: E402
from app.db.session import build_engine, build_session_factory  # noqa: E402

_DEVICE_METADATA_FIELDS = (
    'app_id', 'pack_name', 'channel_id', 'device_model', 'os_type', 'os_version',
    'os_language', 'pack_language', 'timezone', 'app_version', 'package_version',
    'env_id', 'net_route_type', 'net_route_info', 'client_ip', 'game_id',
    'server_ip', 'server_port', 'login_timeout',
)


@dataclass
class ParsedRecord:
    linked_email: str
    app_uid: str
    app_token: str
    device_id: str
    linked_at: Optional[int]
    errors: List[str]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_json_accounts(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
    accounts = data.get('accounts')
    if not isinstance(accounts, dict):
        raise ValueError(f"{path}: expected top-level 'accounts' object, found {type(accounts).__name__}")
    return accounts


def validate_record(email: str, entry: Any) -> ParsedRecord:
    errors: List[str] = []
    if not isinstance(entry, dict):
        return ParsedRecord(linked_email=email, app_uid='', app_token='', device_id='', linked_at=None,
                             errors=['entry is not a JSON object'])

    app_uid = str(entry.get('app_uid') or '').strip()
    app_token = str(entry.get('app_token') or '').strip()
    device_id = str(entry.get('device_id') or '').strip()
    linked_at = entry.get('linked_at')

    if '@' not in email:
        errors.append('key is not a valid-looking email address')
    if not app_uid:
        errors.append('missing app_uid')
    if not app_token:
        errors.append('missing app_token')
    if not device_id:
        errors.append('missing device_id')
    if linked_at is not None and not isinstance(linked_at, (int, float)):
        errors.append('linked_at is not a number')

    return ParsedRecord(
        linked_email=email, app_uid=app_uid, app_token=app_token, device_id=device_id,
        linked_at=int(linked_at) if isinstance(linked_at, (int, float)) else None,
        errors=errors,
    )


def load_device_metadata(env_file: Optional[Path]) -> Dict[str, Any]:
    if env_file is None or not env_file.exists():
        return {}
    from dotenv import dotenv_values

    from app.core.warpath.credentials import WarpathCredentials

    raw_env = {k: v for k, v in dotenv_values(str(env_file)).items() if v is not None}
    # Reuse from_env's parsing/defaulting so int fields (timezone, server_port,
    # ...) are coerced the same way the rest of this codebase coerces them —
    # app_uid/app_token/device_id from this call are discarded; only the
    # shared platform/device metadata fields are used.
    parsed = WarpathCredentials.from_env('migration-metadata-only', env=raw_env)
    return {field: getattr(parsed, field) for field in _DEVICE_METADATA_FIELDS}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json-path', type=Path, default=Path('warpath_accounts.json'))
    parser.add_argument('--owner-email', required=True, help='Platform user every imported account is attached to')
    parser.add_argument('--env-file', type=Path, default=None,
                         help='Legacy .env to source shared device_metadata from (see module docstring)')
    parser.add_argument('--dry-run', action='store_true', help='Validate and report only; write nothing')
    parser.add_argument('--force', action='store_true',
                         help='Update an existing account (matched by linked_email or app_uid) instead of skipping it')
    args = parser.parse_args(argv)

    if not args.json_path.exists():
        print(f'ERROR: {args.json_path} does not exist.')
        return 2

    try:
        raw_accounts = load_json_accounts(args.json_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'ERROR: could not read {args.json_path}: {exc}')
        return 2

    records = [validate_record(email, entry) for email, entry in raw_accounts.items()]
    valid_records = [r for r in records if r.is_valid]
    invalid_records = [r for r in records if not r.is_valid]

    print(f'Found: {len(records)} accounts')
    print(f'Valid: {len(valid_records)}')
    for record in invalid_records:
        # Email is not a secret; app_uid/app_token/device_id are never
        # printed regardless of validity.
        print(f'  - INVALID  {record.linked_email}: {"; ".join(record.errors)}')

    if args.dry_run:
        print(f'Would import: {len(valid_records)}')
        print('Skipped: 0 (dry run — duplicate checks require a database connection)')
        print('\nDry run — no database changes were made.')
        return 0

    device_metadata = load_device_metadata(args.env_file)
    if args.env_file is not None and not device_metadata:
        print(f'WARNING: {args.env_file} was not found or had no WARPATH_* values; '
              'imported accounts will use library defaults for device_metadata.')

    engine = build_engine()
    session_factory = build_session_factory(engine)
    repo = SqlAlchemyAccountRepository(session_factory)

    owner = repo.get_or_create_user(args.owner_email)

    imported = 0
    skipped = 0
    existing = {a.linked_email: a for a in repo.list_accounts() if a.linked_email}
    existing_by_uid = {a.app_uid: a for a in repo.list_accounts()}

    for record in valid_records:
        match = existing.get(record.linked_email) or existing_by_uid.get(record.app_uid)
        if match is not None and not args.force:
            print(f'  - SKIP  {record.linked_email}: already present as account {match.id} (use --force to update)')
            skipped += 1
            continue

        if match is not None and args.force:
            repo.update_account(
                match.id,
                app_uid=record.app_uid,
                app_token=record.app_token,
                device_id=record.device_id,
                device_metadata=device_metadata,
            )
            print(f'  - UPDATED  {record.linked_email}: account {match.id}')
        else:
            account = repo.create_account(
                owner_user_id=owner.id,
                label=record.linked_email,
                linked_email=record.linked_email,
                app_uid=record.app_uid,
                app_token=record.app_token,
                device_id=record.device_id,
                profile_uid=int(record.app_uid) if record.app_uid.isdigit() else None,
                device_metadata=device_metadata,
            )
            repo.add_event(
                account_id=account.id, actor='system:migrate_json_accounts',
                event_type='account_created', detail={'source': 'warpath_accounts.json'},
            )
            print(f'  - IMPORTED  {record.linked_email}: account {account.id}')
        imported += 1

    engine.dispose()

    print(f'Would import: {imported}')
    print(f'Skipped: {skipped}')
    print(f'\n{args.json_path} was not modified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
