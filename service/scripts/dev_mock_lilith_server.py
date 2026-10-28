#!/usr/bin/env python3
"""Manual verification tool: runs the REAL FastAPI app (real Postgres, real
AccountManager, real encryption) with ONLY app.core.warpath.lilith's two
outbound HTTP calls replaced by fakes — so the full Email -> Code -> Verify
-> Account Created flow can be driven end-to-end against a browser/curl
without sending a real verification email or touching Lilith's/Warpath's
real servers.

This is a temporary, stage-5 manual-verification tool, not part of the
product — analogous to scripts/dev_two_accounts.py from Stage 1/2. It is
never imported by app/ code and has no effect unless run directly.

Fake behavior (mirrors tests/test_api_link.py's fakes exactly):
  * send_login_code(...)  -> always "succeeds" (no email is ever sent).
  * verify_login_code(...) -> succeeds for any code EXCEPT the sentinel
    WRONG_CODE below (used to test the invalid-code path), returning a
    synthetic, obviously-fake (app_uid, app_token) pair.

Usage:
    cd service
    ../.venv/Scripts/python.exe scripts/dev_mock_lilith_server.py

Requires the same environment as running the app for real: DATABASE_URL,
WARPATH_ENCRYPTION_KEY, DEV_USER_EMAIL (service/.env already has these from
earlier stages). Does NOT require any WARPATH_APP_UID/WARPATH_APP_TOKEN —
if none exist yet (fresh database), this script prints the exact bootstrap
gap this stage's report documents, then bootstraps one automatically with
clearly-fake credentials so the rest of the flow can be exercised.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # service/ on sys.path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import app.core.warpath.lilith as lilith  # noqa: E402
from app.core.warpath.lilith import LilithLoginError, LinkSession  # noqa: E402

WRONG_CODE = '000000'
FAKE_UID = '900000001'
FAKE_TOKEN = 'DEV-MOCK-LILITH-TOKEN-NOT-REAL'  # noqa: S105 - obviously-fake dev-only sentinel


def _fake_send_login_code(vehicle, email, link_session=None):
    print(f'[mock-lilith] send_login_code: pretending to email a code to {email} (no real email sent)')
    return link_session or LinkSession.new()


def _fake_verify_login_code(vehicle, email, code, link_session):
    print(f'[mock-lilith] verify_login_code: checking a code for {email} (never printing the code itself)')
    if code == WRONG_CODE:
        raise LilithLoginError('verification failed: incorrect code (mock)')
    return FAKE_UID, FAKE_TOKEN


lilith.send_login_code = _fake_send_login_code
lilith.verify_login_code = _fake_verify_login_code


def _ensure_bootstrap_vehicle() -> None:
    """If there is no account at all yet, create one with obviously-fake
    credentials via the same repository the API uses — reproducing exactly
    the manual-POST-/accounts bootstrap path this stage's report describes,
    so /accounts/link/request has a vehicle to use."""
    from app.db.session import build_engine, build_session_factory
    from app.db.repository import SqlAlchemyAccountRepository
    from app.deps import DEV_USER_EMAIL_ENV_VAR

    dev_email = os.environ.get(DEV_USER_EMAIL_ENV_VAR, '').strip()
    if not dev_email:
        print(f'WARNING: {DEV_USER_EMAIL_ENV_VAR} is not set; the API will 503 on every request.')
        return

    engine = build_engine()
    repo = SqlAlchemyAccountRepository(build_session_factory(engine))
    existing = repo.list_accounts()
    if existing:
        print(f'[bootstrap] {len(existing)} account(s) already exist — using one of them as the link vehicle.')
        engine.dispose()
        return

    print('[bootstrap] No accounts exist yet — this is the exact first-account bootstrap gap '
          'described in the Stage 5 report: POST /accounts/link/request would 503 right now.')
    print('[bootstrap] Creating one bootstrap account with obviously-fake credentials via POST '
          '/accounts\'s own code path, so the email/code flow has a vehicle to authorize it...')
    owner = repo.get_or_create_user(dev_email)
    account = repo.create_account(
        owner_user_id=owner.id,
        label='Dev Bootstrap Vehicle (fake)',
        app_uid='dev-bootstrap-uid',
        app_token='dev-bootstrap-token-NOT-REAL',
        device_id='dev-bootstrap-device-NOT-REAL',
        device_metadata={
            'os_type': 'win', 'app_id': 'dev-app-id', 'pack_name': 'dev-pack',
            'channel_id': 'dev-channel', 'app_version': '1.0.0', 'package_version': '1.0.0',
        },
    )
    print(f'[bootstrap] Created account {account.id} to serve as the vehicle.')
    engine.dispose()


if __name__ == '__main__':
    _ensure_bootstrap_vehicle()

    import uvicorn

    port = int(os.environ.get('PORT', '8010'))
    print(f'\nStarting the REAL app (mocked Lilith only) on http://127.0.0.1:{port}\n')
    uvicorn.run('app.main:app', host='127.0.0.1', port=port)
