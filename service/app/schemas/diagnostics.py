from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DebugCaptureRequest(BaseModel):
    seconds: int = Field(default=10, ge=1, le=60)


class DebugCaptureResponse(BaseModel):
    started: bool
    log_path: Optional[str] = None


class DebugCaptureStopResponse(BaseModel):
    message_count: int
    log_path: Optional[str] = None


class RawSnapshotResponse(BaseModel):
    snapshot: Dict[str, Any]
