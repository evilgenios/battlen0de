"""Schemas for the live-session endpoints. Deliberately mirrors
AccountSession.status() (app/core/account_session.py) rather than inventing
a parallel shape — 'live' is None when this process has no registered
AccountSession for the account yet (e.g. it was created but never
connected since this worker last started)."""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel

from app.schemas.accounts import AccountResponse


class LiveSessionStatus(BaseModel):
    account_id: str
    label: str
    state: str
    authenticated: bool
    connection_state: str
    last_error: Optional[str]
    last_connected_at: Optional[float]
    started_at: Optional[float]
    retry_count: int
    auth_failure_count: int


class SessionStatusResponse(BaseModel):
    account_id: uuid.UUID
    db_status: str
    live: Optional[LiveSessionStatus]


class AccountOverviewResponse(BaseModel):
    account: AccountResponse
    status: SessionStatusResponse
