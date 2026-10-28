"""Request/response schemas for the accounts API.

AccountResponse deliberately has no app_token/device_id field — Pydantic
only serializes fields that are declared, so there is no way for a secret
to leak through this schema even if a caller accidentally handed it a
richer object. AccountCreateRequest accepts secrets (there is no other way
to register a credential) but they are marked write-only in the docstrings
and are never echoed back in any response.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceMetadata(BaseModel):
    """Everything WarpathCredentials needs besides identity/secrets/owner.
    Mirrors app.core.warpath.credentials.WarpathCredentials field-for-field
    (minus account_id/label/app_uid/app_token/device_id/profile_uid/platform,
    which are either separate request fields or server-assigned)."""

    app_id: str = ''
    pack_name: str = ''
    channel_id: str = ''
    device_model: str = ''
    os_type: str = ''
    os_version: str = ''
    os_language: str = 'ENG'
    pack_language: str = 'ENG'
    timezone: int = 0
    app_version: str = ''
    package_version: str = ''
    env_id: str = ''
    net_route_type: int = 0
    net_route_info: str = ''
    client_ip: str = ''
    game_id: str = '10048'
    server_ip: str = '34.8.3.236'
    server_port: int = Field(default=10000, ge=1, le=65535)
    login_timeout: int = Field(default=30, ge=5)


class AccountCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    linked_email: Optional[str] = None
    app_uid: str = Field(min_length=1, max_length=64)
    app_token: str = Field(min_length=1, description='Write-only — never returned by any endpoint.')
    device_id: str = Field(min_length=1, description='Write-only — never returned by any endpoint.')
    profile_uid: Optional[int] = None
    platform: int = 22
    device_metadata: DeviceMetadata = Field(default_factory=DeviceMetadata)
    status: str = 'active'


class AccountResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    label: str
    linked_email: Optional[str]
    app_uid: str
    profile_uid: Optional[int]
    platform: int
    device_metadata: dict
    linked_at: Optional[datetime]
    last_connected_at: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class AccountEventResponse(BaseModel):
    id: int
    account_id: Optional[uuid.UUID]
    actor: str
    event_type: str
    detail: dict
    created_at: datetime


class AccountEventWithLabelResponse(BaseModel):
    event: AccountEventResponse
    account_label: Optional[str]
