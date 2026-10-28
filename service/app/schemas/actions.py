"""Action request bodies. One schema per EXISTING WarpathConnection method
(app/core/warpath/connection.py) — collect and scan take no protocol
parameters beyond what's already optional on the connection; farm/recall/
scout mirror send_farm_search/send_recall_vehicle/send_continuous_scout's
existing signatures exactly. Nothing here invents new protocol behavior."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    # Both optional, same as WarpathConnection.send_map_view_request(): when
    # omitted, the connection falls back to the cached base position.
    center_x: Optional[int] = None
    center_y: Optional[int] = None


class FarmRequest(BaseModel):
    resource: Literal['gold', 'metal', 'oil']
    level: int = Field(ge=1, le=10)


class RecallRequest(BaseModel):
    vehicle_id: int


class ScoutRequest(BaseModel):
    plane_id: int


class ActionResponse(BaseModel):
    detail: str


class RecallAllResponse(BaseModel):
    vehicle_ids: list[int]


class CollectResponse(BaseModel):
    """Counts only correlated replies; items_gained counts reward entries,
    not resource units. Zero means empty only when status is confirmed."""

    status: Literal["confirmed", "partial", "uncertain", "rejected"]
    detail: str
    unconfirmed_building_ids: list[int]
    buildings_requested: int
    buildings_replied: int
    items_gained: int


class FarmResponse(BaseModel):
    """dispatched is true only for confirmed travel/gathering. An uncertain
    dispatch may have executed upstream; its truck remains reserved."""

    status: Literal["confirmed", "uncertain", "rejected", "not_dispatched"]
    dispatched: bool
    detail: str
    mine_id: Optional[int] = None
    vehicle_id: Optional[int] = None


class RecallResponse(BaseModel):
    vehicle_id: int
    state: int



class CommandObservation(BaseModel):
    operation_id: str
    kind: Literal['collect', 'gather', 'search', 'vehicles']
    status: Literal['awaiting_reply', 'uncertain', 'confirmed', 'rejected']
    reason: Literal['waiting_for_reply', 'timeout', 'cancelled', 'disconnected',
                    'send_uncertain', 'confirmed_reply', 'explicit_rejection',
                    'not_sent', 'awaiting_idle_observation', 'idle_observed']
    reservation: Literal['truck', 'building', 'search', 'none']
    created_at: float
    age_seconds: float
    building_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    mine_id: Optional[int] = None


class CommandStatusResponse(BaseModel):
    # This is not an assertion that older actions completed safely.
    history_scope: Literal['current_connection_only'] = 'current_connection_only'
    history_complete: Literal[False] = False
    upstream_evidence: Literal['unverified'] = 'unverified'
    observation_id: Optional[str] = None
    tracking_started_at: Optional[float] = None
    connected: bool = False
    active: list[CommandObservation] = Field(default_factory=list)
    recent: list[CommandObservation] = Field(default_factory=list)
    recent_dropped: int = 0
    tracked_requests: int = 0
    tracking_limit: int = 1024
