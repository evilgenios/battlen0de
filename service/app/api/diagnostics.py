"""Admin-only diagnostics: bounded protocol-debug capture (existing safe
read-only requests only — never arbitrary packet construction) and a
redacted account snapshot. Both gated by require_admin (see deps.py) on
top of the normal require_dashboard_auth router-level gate.

Deliberately NOT exposed: the legacy bot's `/raw` let an operator run
arbitrary console commands against the connection. This module exposes
only a read of the already-collected, redacted account_snapshot — never a
way to construct or send a new protocol packet.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.account_manager import AccountManager
from app.core.warpath.connection import WarpathConnection
from app.db.repository import AccountRecord
from app.deps import get_account_manager, get_owned_account, require_admin
from app.schemas.diagnostics import (
    DebugCaptureRequest,
    DebugCaptureResponse,
    DebugCaptureStopResponse,
    RawSnapshotResponse,
)

router = APIRouter(prefix='/accounts', tags=['diagnostics'], dependencies=[Depends(require_admin)])


def _connected_session(manager: AccountManager, account_id: uuid.UUID):
    session = manager.get_account(str(account_id))
    if session is None or not session.connection.connected:
        raise HTTPException(status_code=409, detail='account is not connected')
    return session


@router.post('/{account_id}/debug-capture/start', response_model=DebugCaptureResponse)
def start_debug_capture(
    account_id: uuid.UUID,
    body: DebugCaptureRequest,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> DebugCaptureResponse:
    session = _connected_session(manager, account_id)
    try:
        path = session.connection.start_protocol_debug(body.seconds, console=False)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.connection.request_debug_snapshots()
    return DebugCaptureResponse(started=True, log_path=path)


@router.post('/{account_id}/debug-capture/stop', response_model=DebugCaptureStopResponse)
def stop_debug_capture(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> DebugCaptureStopResponse:
    session = manager.get_account(str(account_id))
    if session is None:
        raise HTTPException(status_code=409, detail='account is not connected')
    path, count = session.connection.stop_protocol_debug()
    return DebugCaptureStopResponse(message_count=count, log_path=path)


@router.get('/{account_id}/debug-capture/download')
def download_debug_capture(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
):
    from fastapi.responses import FileResponse

    session = manager.get_account(str(account_id))
    path = session.connection.debug_log_path if session else None
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail='no capture log available for this account')
    if os.path.getsize(path) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='capture log exceeds 8 MiB; inspect it on the server instead')
    return FileResponse(path, media_type='application/jsonl', filename=os.path.basename(path))


@router.get('/{account_id}/raw-snapshot', response_model=RawSnapshotResponse)
def raw_snapshot(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    manager: AccountManager = Depends(get_account_manager),
) -> RawSnapshotResponse:
    session = manager.get_account(str(account_id))
    if session is None:
        return RawSnapshotResponse(snapshot={})
    snap = dict(session.connection.account_snapshot)
    # Truncate large fields, same as the legacy bot's /raw.
    if 'inventory' in snap and isinstance(snap['inventory'], dict):
        snap['inventory'] = f'<{len(snap["inventory"])} items>'
    # Defense in depth: this dict has never contained app_token/device_id in
    # practice, but redact anything token/session/password-shaped anyway,
    # reusing the exact same redaction WarpathConnection applies to its own
    # protocol debug log.
    snap = WarpathConnection._redact_protocol_secrets(snap)
    return RawSnapshotResponse(snapshot=snap)
