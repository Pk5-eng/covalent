"""Shared floor-plan data model (Section 4 of the spec).

Internal units are millimetres. The frontend mirrors these shapes in
`frontend/src/lib/model.ts`. Keep both in sync.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

Units = Literal["metric", "imperial"]
Zone = Literal["public", "private", "service", "circulation", "exterior"]


class Boundary(BaseModel):
    width_mm: PositiveInt
    depth_mm: PositiveInt
    units_display: Units = "metric"


class RoomRequest(BaseModel):
    """A single room slot the user asked for in the palette."""

    type: str
    count: PositiveInt = 1


class Point(BaseModel):
    x: float
    y: float


class Room(BaseModel):
    id: str
    type: str
    label: str
    zone: Zone
    polygon: list[tuple[float, float]] = Field(default_factory=list)
    area_mm2: float = 0
    needs_window: bool = False
    needs_egress: bool = False
    needs_exterior_wall: bool = False


class Wall(BaseModel):
    id: str
    a: tuple[float, float]
    b: tuple[float, float]
    thickness_mm: PositiveInt = 115
    type: Literal["interior", "exterior"] = "interior"


class Opening(BaseModel):
    id: str
    kind: Literal["door", "window"]
    wall_id: str
    position: float  # 0..1 along the wall
    width_mm: PositiveInt
    swing: Optional[str] = None  # doors only: in_left/in_right/out_left/out_right
    is_egress: bool = False


class PlanMeta(BaseModel):
    scale: str = "1:100"
    north_deg: float = 0
    title: str = "Covalent floor plan"


class FloorPlan(BaseModel):
    boundary: Boundary
    rooms: list[Room]
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    meta: PlanMeta = Field(default_factory=PlanMeta)


# ---------- Architect agent I/O (Section 5) ----------


class ProgramGlobal(BaseModel):
    circulation_target_pct: NonNegativeInt = 12
    group_wet_rooms: bool = True
    primary_entry_side: Literal["north", "south", "east", "west"] = "south"


class ProgramRoom(BaseModel):
    id: str
    type: str
    label: str
    zone: Zone
    target_area_m2: float
    min_width_m: float
    priority: int = 1
    needs_exterior_wall: bool = False
    needs_window: bool = False
    needs_egress: bool = False
    adjacent_to: list[str] = Field(default_factory=list)
    not_adjacent_to: list[str] = Field(default_factory=list)


class ProgramCirculation(BaseModel):
    entry_room_id: str
    notes: str = ""


class Program(BaseModel):
    units: Literal["mm"] = "mm"
    global_: ProgramGlobal = Field(default_factory=ProgramGlobal, alias="global")
    rooms: list[ProgramRoom]
    circulation: ProgramCirculation

    model_config = {"populate_by_name": True}


# ---------- Request/response envelopes ----------


class GenerateRequest(BaseModel):
    boundary: Boundary
    rooms: list[RoomRequest]
    seed: Optional[int] = None


class GenerateResponse(BaseModel):
    plan: FloorPlan
    program: Optional[Program] = None


class ResizeRequest(BaseModel):
    plan: FloorPlan
    room_id: str
    new_target_area_m2: float
