from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MassDeployRequest(BaseModel):
    account_ids: List[str] = Field(min_length=1)
    ag_id: str
    player_uid: str
    army_ids: str = 'auto'
    group_type: str = 'auto'
    execute: bool = False


class MassDeployAccountResult(BaseModel):
    account_id: str
    label: str
    teleport: str
    ag: str
    error: Optional[str] = None


class MassDeployResponse(BaseModel):
    execute: bool
    ag_id: str
    player_uid: str
    army_ids: str
    group_type: str
    results: List[MassDeployAccountResult]
    complete_count: int
    total_count: int
