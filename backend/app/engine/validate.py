"""Geometric validation — the contract every layout must pass (Step 4.1).

Three core checks:
    1. No two rooms overlap (interior area > tolerance).
    2. The union of all rooms covers the entire boundary (no gaps).
    3. The adjacency graph implied by shared walls is connected, so
       every room is reachable from any room via shared walls.

Floor plans only render or export when these pass. The validator is the
gate. Failures surface a concrete ValidationError.

Shapely does the heavy lifting; we wrap it so callers stay in mm space
without thinking about precision quirks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import networkx as nx
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.models import FloorPlan, Room


# Tolerance: mm. 1 mm^2 is much finer than the 100 mm snap grid we care
# about — but allows shapely's floating-point noise to slip through.
TOL_MM2 = 1.0
TOL_LEN_MM = 1.0  # acceptable overlap on a single shared wall


@dataclass
class ValidationError(Exception):
    code: str
    message: str
    room_ids: tuple[str, ...] = ()

    def __str__(self) -> str:
        rids = f" rooms={list(self.room_ids)}" if self.room_ids else ""
        return f"[{self.code}] {self.message}{rids}"


def boundary_polygon(plan: FloorPlan) -> Polygon:
    return box(0, 0, plan.boundary.width_mm, plan.boundary.depth_mm)


def room_polygon(room: Room) -> Polygon:
    return Polygon(room.polygon)


def validate_floor_plan(plan: FloorPlan) -> None:
    """Raise ValidationError on any failure. Return None on success."""
    if not plan.rooms:
        raise ValidationError(code="no_rooms", message="floor plan has no rooms")

    boundary = boundary_polygon(plan)
    if boundary.area <= 0:
        raise ValidationError(code="bad_boundary", message="boundary has zero area")

    polys: list[Polygon] = []
    for r in plan.rooms:
        if len(r.polygon) < 3:
            raise ValidationError(
                code="bad_polygon",
                message=f"room {r.id} polygon has fewer than 3 vertices",
                room_ids=(r.id,),
            )
        p = room_polygon(r)
        if not p.is_valid or p.area <= 0:
            raise ValidationError(
                code="bad_polygon",
                message=f"room {r.id} polygon invalid or zero area",
                room_ids=(r.id,),
            )
        # Room must fit inside the boundary (with mm tolerance).
        if not boundary.buffer(TOL_LEN_MM).contains(p):
            raise ValidationError(
                code="out_of_bounds",
                message=f"room {r.id} extends outside the boundary",
                room_ids=(r.id,),
            )
        polys.append(p)

    _check_no_overlaps(plan.rooms, polys)
    _check_full_coverage(boundary, polys, plan.rooms)
    _check_connectivity(plan.rooms, polys)


def _check_no_overlaps(rooms: list[Room], polys: list[Polygon]) -> None:
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j])
            if inter.area > TOL_MM2:
                raise ValidationError(
                    code="overlap",
                    message=(
                        f"rooms {rooms[i].id} and {rooms[j].id} overlap by "
                        f"{inter.area:.1f} mm^2"
                    ),
                    room_ids=(rooms[i].id, rooms[j].id),
                )


def _check_full_coverage(boundary: Polygon, polys: list[Polygon], rooms: list[Room]) -> None:
    union = unary_union(polys)
    # symmetric_difference area should be zero (within tolerance).
    diff = boundary.symmetric_difference(union)
    if diff.area > TOL_MM2 * 10:
        # Identify uncovered area for the message.
        gap = boundary.difference(union)
        spill = union.difference(boundary)
        msg = []
        if gap.area > TOL_MM2:
            msg.append(f"gap area {gap.area:.0f} mm^2")
        if spill.area > TOL_MM2:
            msg.append(f"spill area {spill.area:.0f} mm^2")
        raise ValidationError(
            code="coverage",
            message=f"rooms do not tile the boundary: {', '.join(msg) or 'mismatch'}",
            room_ids=tuple(r.id for r in rooms),
        )


def _shared_edge_length(a: Polygon, b: Polygon) -> float:
    """Length of the 1-D intersection between two polygon boundaries."""
    inter = a.boundary.intersection(b.boundary)
    if inter.is_empty:
        return 0.0
    # length attribute is robust across Point/LineString/MultiLineString/GeometryCollection
    return float(getattr(inter, "length", 0.0))


def _check_connectivity(rooms: list[Room], polys: list[Polygon]) -> None:
    """Every room must share a wall (length > tolerance) with the rest."""
    g = nx.Graph()
    g.add_nodes_from(r.id for r in rooms)
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            if _shared_edge_length(polys[i], polys[j]) > TOL_LEN_MM:
                g.add_edge(rooms[i].id, rooms[j].id)
    if not nx.is_connected(g):
        components = list(nx.connected_components(g))
        # Report the smallest disconnected component to keep the message tight.
        worst = min(components, key=len)
        raise ValidationError(
            code="disconnected",
            message=f"rooms not connected via shared walls (isolated: {sorted(worst)})",
            room_ids=tuple(sorted(worst)),
        )


def shared_wall_length(a: Room, b: Room) -> float:
    """Public helper for tests + cost function."""
    return _shared_edge_length(room_polygon(a), room_polygon(b))


def collect_validation_errors(plan: FloorPlan) -> list[ValidationError]:
    """Run all checks and accumulate errors instead of raising on the first one.

    Useful for the debug renderer to highlight every issue at once.
    """
    errors: list[ValidationError] = []
    try:
        validate_floor_plan(plan)
    except ValidationError as e:
        errors.append(e)
    return errors


def adjacency_graph(rooms: Iterable[Room]) -> nx.Graph:
    rooms = list(rooms)
    polys = [room_polygon(r) for r in rooms]
    g = nx.Graph()
    g.add_nodes_from(r.id for r in rooms)
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            length = _shared_edge_length(polys[i], polys[j])
            if length > TOL_LEN_MM:
                g.add_edge(rooms[i].id, rooms[j].id, length_mm=length)
    return g
