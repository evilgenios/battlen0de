from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminSummaryResponse(BaseModel):
    users_total: int
    users_active: int
    users_disabled: int
    accounts_total: int
    accounts_connected: int
    active_web_sessions: int
    alliance_users: int
    individual_users: int


class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: Optional[str]
    status: str
    plan: Literal['individual', 'alliance']
    max_accounts: int
    max_sessions: int
    max_active_accounts: int
    mfa_enabled: bool
    player_scout_access: bool
    account_count: int
    active_sessions: int
    created_at: datetime
    updated_at: datetime


class AdminAccountResponse(BaseModel):
    id: str
    owner_user_id: str
    owner_email: str
    label: str
    app_uid: str
    linked_email: Optional[str]
    status: str
    live_state: Optional[str]
    authenticated: bool
    last_connected_at: Optional[datetime]


class AdminAuditResponse(BaseModel):
    id: int
    actor_user_id: Optional[str]
    actor_email: Optional[str]
    action: str
    target_type: str
    target_id: Optional[str]
    outcome: str
    peer_ip: Optional[str]
    user_agent: Optional[str]
    detail: dict[str, Any]
    created_at: datetime


class AdminAccountEventResponse(BaseModel):
    id: int
    account_id: Optional[str]
    account_label: Optional[str]
    owner_email: Optional[str]
    actor: str
    event_type: str
    detail: dict[str, Any]
    created_at: datetime


class AdminUserPolicyPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['active', 'disabled']
    max_accounts: int = Field(ge=1, le=100)
    max_sessions: int = Field(ge=1, le=20)
    max_active_accounts: int = Field(ge=1, le=20)
    player_scout_access: Optional[bool] = None


class AdminAccountStatusPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['active', 'disabled', 'needs_reauth', 'restricted']


class MfaCodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(pattern=r'^\d{6}$')


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaStatusResponse(BaseModel):
    enabled: bool
    setup_pending: bool
