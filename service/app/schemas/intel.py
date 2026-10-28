from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AccountSummary(BaseModel):
    """Section 3's "Account" card: base level/state/coordinates, counts —
    everything derived from the connection's own already-collected data,
    never a new protocol call."""

    name: Optional[str] = None
    uid: Optional[int] = None
    account_level: Optional[int] = None
    mainbase_level: Optional[int] = None
    base_state: str = 'Unknown'
    base_x: Optional[int] = None
    base_y: Optional[int] = None
    current_map_id: int = 0
    vehicle_count: int = 0
    scout_plane_count: int = 0
    map_object_count: int = 0
    army_count: int = 0


class VehicleInfo(BaseModel):
    id: int
    state: int
    state_label: str
    mine_id: int
    map_vehicle_id: int
    type_id: int
    map_id: int
    is_locked: bool
    # Confirmed present on the real get_vehicle_list_reply via a live
    # protocol capture on 2026-09-15 — 0 (not None) when the server didn't
    # send them, matching every other zero-default field on this model.
    x: int = 0
    y: int = 0
    start_time: int = 0
    end_time: int = 0
    max_gather_num: int = 0
    target_x: int = 0
    target_y: int = 0


class ArmyInfo(BaseModel):
    army_id: int
    equipment_id: int
    reserves: int
    master_obj_id: int
    group_unique_id: int


class ArmyGroupInfo(BaseModel):
    unique_id: int
    group_type: int
    map_id: int
    city_id: int
    creator_uid: int
    creator_name: str
    announcement: str
    state: int
    army_count: int
    max_num: int


class JoinArmyGroupRequest(BaseModel):
    army_ids: str = 'auto'
    group_type: str = 'auto'


class LeaveArmyGroupRequest(BaseModel):
    army_id: int


class JoinArmyGroupResponse(BaseModel):
    """Real post-join state, read back from the same army snapshot the
    Armies panel uses (connection.armies[id]['group_unique_id']) — confirmed
    via a live test that a join actually changes this AG's army_count, so
    this is real confirmation, not just "request sent"."""

    ag_id: int
    joined_army_ids: List[int]
    unconfirmed_army_ids: List[int]


class LeaveArmyGroupResponse(BaseModel):
    army_id: int
    left: bool


class ProfileInfo(BaseModel):
    uid: int
    name: str
    guild_id: int
    guild_name: str
    power: int
    skin_point: int
    commander_skin: int
    title_skin: int


class MapObjectInfo(BaseModel):
    unique_id: int
    owner_id: int
    x: int
    y: int
    object_type: int
    map_id: int
    is_mainbase: bool


class LocateBasesRequest(BaseModel):
    player_uid: Optional[int] = None


class MainbasePosition(BaseModel):
    player_id: int
    x: int
    y: int


class RefreshResponse(BaseModel):
    requested: List[str]
    failures: List[str]


class SkinsResponse(BaseModel):
    categories: Dict[str, List[Dict[str, Any]]]


class ProductionLineInfo(BaseModel):
    """One produce_cell from playerdata_reply.building_produce — the
    complete, unfiltered picture (unlike ActiveActionInfo's production
    entries, which only include cells with a real end_time)."""

    building_id: int
    line_id: int
    item_type_id: Optional[str] = None
    quantity: Optional[int] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    status: str


class ActiveActionInfo(BaseModel):
    """One normalized, real, currently-in-progress activity for this
    account — see app/core/warpath/active_actions.py's module docstring for
    exactly which protocol fields back each activity_type and why. Every
    field here is either a value read straight off a server reply, or a
    status derived by comparing two real server timestamps to the current
    time — never a client-invented countdown. Fields not meaningful for a
    given activity_type are left None rather than defaulted to 0, so the
    frontend can tell "not applicable" apart from "the server sent zero"."""

    activity_type: str
    status: str
    vehicle_id: Optional[int] = None
    mine_id: Optional[int] = None
    building_id: Optional[int] = None
    line_id: Optional[int] = None
    map_id: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    target_x: Optional[int] = None
    target_y: Optional[int] = None
    item_type_id: Optional[str] = None
    quantity: Optional[int] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    task_id: Optional[str] = None
    task_status: Optional[int] = None
    detail: Optional[str] = None
