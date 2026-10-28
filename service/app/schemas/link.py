"""Request/response schemas for the two-step Lilith email/code linking
flow. See app/api/link.py for the endpoints and app/core/link_challenge_store.py
for why the challenge never touches PostgreSQL."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LinkRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: Optional[UUID] = None
    email: EmailStr
    challenge_id: Optional[str] = None


class LinkRequestResponse(BaseModel):
    challenge_id: str
    email: str
    expires_in_seconds: int


class LinkVerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str
    code: str = Field(min_length=6, max_length=6, pattern=r'^[0-9]{6}$')
    # Defaults to the linked email if omitted — see api/link.py.
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
