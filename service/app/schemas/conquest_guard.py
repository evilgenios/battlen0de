from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class ConquestGuardStatus(BaseModel):
    enabled: bool
    armed_uid: int
    connected_uid: Optional[int] = None
    in_progress: bool
    attempts: int
    last_attack: Optional[Dict[str, Any]] = None
    last_result: Optional[Dict[str, Any]] = None
