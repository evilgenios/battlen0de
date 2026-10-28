"""Typed seller-supplied information; no operational-account or credential fields."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ListingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=5, max_length=100)
    description: str = Field(min_length=30, max_length=5000)
    commander_name: str = Field(min_length=2, max_length=60)
    commander_id: str = Field(min_length=2, max_length=40, pattern=r'^[a-zA-Z0-9-]+$')
    server: int = Field(ge=1, le=10000)
    strength: int = Field(ge=0, le=100_000_000_000)
    commander_level: int = Field(ge=1, le=200)
    collector_level: int = Field(ge=0, le=200)
    airspace: int = Field(ge=0, le=100000)
    vip: int = Field(ge=0, le=100)
    composition: Literal['ground', 'air', 'balanced']
    research: int = Field(ge=0, le=100)
    price_cents: int = Field(ge=100, le=100_000_000)
    currency: Literal['USD'] = 'USD'
    evidence: str = Field(default='', max_length=5000)

    @field_validator('commander_id')
    @classmethod
    def canonical_commander_id(cls, value: str) -> str:
        return value.lower()


class ListingEdit(ListingInput):
    version: int = Field(ge=1)


class VersionInput(BaseModel):
    version: int = Field(ge=1)


class DecisionInput(VersionInput):
    decision: Literal['approve', 'reject', 'remove']
    note: str = Field(min_length=5, max_length=2000)
    stats_reviewed: bool = False
    control_demonstrated: bool = False


class MessageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=3000)


class ReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=10, max_length=2000)


class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str = Field(min_length=2, max_length=60)


class PermissionsInput(BaseModel):
    seller_enabled: bool
    staff_role: Literal['user', 'moderator', 'marketplace_admin', 'owner'] = 'user'
    restricted: bool = False
