#!/usr/bin/env python3
"""Manual concurrency proof: connect two REAL Warpath accounts at the same
time through one AccountManager, using two independent AccountSessions.

This is a temporary stage-1/2 development entry point — not part of the
eventual service. It exists to prove, against the real Warpath game server,
that two AccountSession/WarpathConnection pairs can be authenticated and
running at once with zero shared credential/connection state, which is the
whole point of this refactor.

No credentials are hardcoded anywhere in this file. Configure two accounts
via environment variables (or a `.env` file loaded from this directory) and
run:

    cd service
    ..\\.venv\\Scripts\\python.exe scripts\\dev_two_accounts.py       (Windows)
    ../.venv/bin/python scripts/dev_two_accounts.py                    (macOS/Linux)

Environment variables — same field names as the legacy bot's .env, just
duplicated under two prefixes so both accounts can live in one process's
environment. See scripts/.env.two_accounts.example for the full list.

  WARPATH_A_APP_UID / WARPATH_A_APP_TOKEN / WARPATH_A_DEVICE_ID / ...
  WARPATH_B_APP_UID / WARPATH_B_APP_TOKEN / WARPATH_B_DEVICE_ID / ...

Getting real values for those: use the legacy bot's own extract_warpath_env.py
against a Wireshark capture of each account's login (see the legacy bot's
README), or /link+/verify a second account through the legacy Discord bot
and read its app_uid/app_token/device_id out of warpath_accounts.json for
that one entry. Either way, DO NOT commit the resulting values anywhere —
keep them only in a local, gitignored .env.

Safety note: this script does not do anything to hide the fact that two
accounts are connecting from this machine/IP — see the "Multi-account
connection safety" docstring in app/core/account_manager.py. That is
intentional. If Warpath flags or rejects one of the two accounts, this
script will show it moving to RESTRICTED instead of hammering the login
endpoint — that is the correct, expected behavior, not a bug to work around.
"""

import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # service/ on sys.path

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.two_accounts'))
except ImportError:
    pass

from app.core.account_manager import AccountManager  # noqa: E402
from app.core.warpath.credentials import WarpathCredentials  # noqa: E402

ACCOUNT_A_ID = 'dev-account-a'
ACCOUNT_B_ID = 'dev-account-b'


def _print_status_table(manager: AccountManager) -> None:
    for status in manager.list_accounts():
        print(
            f"  [{status['account_id']:14s}] state={status['state']:12s} "
            f"authenticated={status['authenticated']!s:5s} "
            f"retries={status['retry_count']} auth_failures={status['auth_failure_count']} "
            f"last_error={status['last_error']}"
        )


def main() -> int:
    creds_a = WarpathCredentials.from_env(ACCOUNT_A_ID, prefix='WARPATH_A_', label='Account A')
    creds_b = WarpathCredentials.from_env(ACCOUNT_B_ID, prefix='WARPATH_B_', label='Account B')

    incomplete = False
    for creds in (creds_a, creds_b):
        errors = creds.validation_errors()
        if errors:
            incomplete = True
            print(f'[{creds.account_id}] configuration incomplete:')
            for error in errors:
                print(f'  - {error}')
    if incomplete:
        print()
        print('Fill in the missing WARPATH_A_*/WARPATH_B_* environment variables '
              '(see scripts/.env.two_accounts.example) and re-run.')
        return 2

    def on_event(event):
        print(f'[{time.strftime("%H:%M:%S", time.localtime(event.at))}] '
              f'{event.account_id}: {event.kind} — {event.detail}')

    manager = AccountManager(
        max_concurrent_sessions=int(os.environ.get('MAX_CONCURRENT_SESSIONS', '5')),
        on_event=on_event,
    )
    manager.add_account(creds_a)
    manager.add_account(creds_b)

    print(f'Starting {ACCOUNT_A_ID} and {ACCOUNT_B_ID} concurrently...')
    manager.start(ACCOUNT_A_ID)
    manager.start(ACCOUNT_B_ID)

    stop_requested = {'flag': False}

    def handle_sigint(signum, frame):
        stop_requested['flag'] = True

    signal.signal(signal.SIGINT, handle_sigint)
    print('Press Ctrl+C to stop both accounts and exit.\n')

    try:
        while not stop_requested['flag']:
            time.sleep(5)
            _print_status_table(manager)
    finally:
        print('\nStopping both accounts...')
        manager.stop_all()
        _print_status_table(manager)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
