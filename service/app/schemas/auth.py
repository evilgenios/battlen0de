from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str = Field(max_length=320)
    password: str = Field(max_length=256)
    mfa_code: Optional[str] = Field(default=None, pattern=r'^\d{6}$')


class DashboardUserInfo(BaseModel):
    email: str
    role: str
    csrf_token: str


class MeResponse(BaseModel):
    user_id: str
    session_key: str
    email: str
    role: str
    active_sessions: int
    plan: Literal['individual', 'alliance']
    max_accounts: int
    max_sessions: int
    max_active_accounts: int
    mfa_enabled: bool = False
    player_scout_access: bool = False


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: EmailStr
    kind: Literal['invite', 'recovery']


class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=256)


class UserPolicyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: Literal['active', 'disabled']
    max_accounts: int = Field(ge=1, le=100)
    max_sessions: int = Field(ge=1, le=20)
    max_active_accounts: int = Field(ge=1, le=20)
    player_scout_access: Optional[bool] = None
