"""Finishing passes after annealing (Step 4.5 of the spec).

Order:
    1. Snap room rectangle edges to the 100 mm grid (cluster-aligned).
    2. Build walls: offset room rectangles to wall thickness, merge
       shared interior walls, label exterior segments.
    3. Place doors on shared walls between graph-adjacent rooms.
    4. Place windows on exterior walls of rooms that need daylight.
    5. Run validate.py.
    6. Return a `FloorPlan`.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.engine.fixtures import place_fixtures_in_plan
from app.engine.slicing import Rect
from app.engine.validate import validate_floor_plan
from app.models import Boundary, FloorPlan, Opening, PlanMeta, Room, Wall
from app.rules.defaults import (
    CATALOG_BY_TYPE,
    CORRIDOR_MIN_WIDTH_MM,
    DOOR_WIDTHS_MM,
    EXTERIOR_WALL_MM,
    GRID_MM,
    INTERIOR_WALL_MM,
    are_open_pair,
)

# Wall-axis tolerance (mm) when treating two edges as collinear.
COLLINEAR_TOL = 1.0


# ----------------------------------------------------------------------
# Snapping (cluster-aligned so adjacent rects stay flush)
# ----------------------------------------------------------------------


def snap_rects_to_grid(
    rects: dict[str, Rect],
    boundary_w: float,
    boundary_h: float,
    grid: float = GRID_MM,
) -> dict[str, Rect]:
    """Snap shared edge coordinates to the grid simultaneously.

    Per-rect snapping breaks the tiling. Cluster-aligned snapping rounds
    each unique x-line and y-line in the layout once, so every rect that
    shared that line stays flush.
    """
    if grid <= 0:
        return rects

    xs: dict[float, float] = {}
    ys: dict[float, float] = {}

    def _snap(v: float) -> float:
        return round(v / grid) * grid

    for r in rects.values():
        for v in (r.x, r.x + r.w):
            xs.setdefault(round(v, 3), _snap(v))
        for v in (r.y, r.y + r.h):
            ys.setdefault(round(v, 3), _snap(v))

    # Force outer edges to land exactly on the boundary.
    xs[0.0] = 0.0
    xs[round(boundary_w, 3)] = boundary_w
    ys[0.0] = 0.0
    ys[round(boundary_h, 3)] = boundary_h

    out: dict[str, Rect] = {}
    for rid, r in rects.items():
        nx0 = xs[round(r.x, 3)]
        ny0 = ys[round(r.y, 3)]
        nx1 = xs[round(r.x + r.w, 3)]
        ny1 = ys[round(r.y + r.h, 3)]
        out[rid] = Rect(nx0, ny0, max(grid, nx1 - nx0), max(grid, ny1 - ny0))
    return out


# ----------------------------------------------------------------------
# Walls + openings
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _Edge:
    """One side of a room rectangle, used to find shared walls."""

    room_id: str
    axis: str  # "h" (horizontal: const y) or "v" (vertical: const x)
    const: float
    lo: float
    hi: float

    def length(self) -> float:
        return self.hi - self.lo


def _rect_edges(rid: str, r: Rect) -> list[_Edge]:
    return [
        _Edge(rid, "h", r.y, r.x, r.x + r.w),               # top
        _Edge(rid, "h", r.y + r.h, r.x, r.x + r.w),         # bottom
        _Edge(rid, "v", r.x, r.y, r.y + r.h),               # left
        _Edge(rid, "v", r.x + r.w, r.y, r.y + r.h),         # right
    ]


def _is_on_boundary(edge: _Edge, boundary_w: float, boundary_h: float) -> bool:
    if edge.axis == "h":
        return abs(edge.const) < COLLINEAR_TOL or abs(edge.const - boundary_h) < COLLINEAR_TOL
    return abs(edge.const) < COLLINEAR_TOL or abs(edge.const - boundary_w) < COLLINEAR_TOL


def _overlap(e1: _Edge, e2: _Edge) -> tuple[float, float] | None:
    lo = max(e1.lo, e2.lo)
    hi = min(e1.hi, e2.hi)
    if hi - lo > COLLINEAR_TOL:
        return lo, hi
    return None


def build_walls_and_openings(
    rects: dict[str, Rect],
    program_by_id: dict[str, dict],
    boundary_w: float,
    boundary_h: float,
    adjacency_graph_edges: Iterable[tuple[str, str]],
) -> tuple[list[Wall], list[Opening]]:
    """Build wall + opening lists from snapped rectangles.

    For Step 4.5 we keep the wall model simple:
      - one Wall per exterior segment (whole boundary side per room),
      - one Wall per shared interior segment between two rooms,
      - each wall stored at its centerline coordinate, with `type` and
        `thickness_mm` set per Section 7 defaults.
    """
    walls: list[Wall] = []
    openings: list[Opening] = []
    wall_id_counter = 0
    opening_id_counter = 0

    # Group all edges by (axis, const) so we can find shared interior walls.
    edges_by_line: dict[tuple[str, float], list[_Edge]] = defaultdict(list)
    for rid, r in rects.items():
        for e in _rect_edges(rid, r):
            edges_by_line[(e.axis, round(e.const, 3))].append(e)

    seen_pairs: set[tuple[str, str, float, float, str]] = set()

    for (axis, const), edges in edges_by_line.items():
        if abs(const) < COLLINEAR_TOL or (
            axis == "h" and abs(const - boundary_h) < COLLINEAR_TOL
        ) or (axis == "v" and abs(const - boundary_w) < COLLINEAR_TOL):
            # Exterior side: emit one wall per room edge that lies on it.
            for e in edges:
                if axis == "h":
                    a = (e.lo, e.const)
                    b = (e.hi, e.const)
                else:
                    a = (e.const, e.lo)
                    b = (e.const, e.hi)
                wall_id_counter += 1
                walls.append(
                    Wall(
                        id=f"w{wall_id_counter}",
                        a=a,
                        b=b,
                        thickness_mm=EXTERIOR_WALL_MM,
                        type="exterior",
                    )
                )
            continue

        # Interior line: find overlapping pairs.
        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                e1, e2 = edges[i], edges[j]
                if e1.room_id == e2.room_id:
                    continue
                ov = _overlap(e1, e2)
                if ov is None:
                    continue
                lo, hi = ov
                key = (e1.room_id, e2.room_id, lo, hi, axis)
                if key in seen_pairs:
                    continue
                seen_pairs.add((e1.room_id, e2.room_id, lo, hi, axis))
                seen_pairs.add((e2.room_id, e1.room_id, lo, hi, axis))

                # Open-pair rule: kitchen/dining/living/family/foyer/gallery
                # flow as one space — no wall, no door, just continuous floor.
                # Privacy-critical rooms (bedrooms, bathrooms, study, etc.)
                # still get walled normally.
                type_a = program_by_id.get(e1.room_id, {}).get("type", "")
                type_b = program_by_id.get(e2.room_id, {}).get("type", "")
                if are_open_pair(type_a, type_b):
                    continue

                if axis == "h":
                    a = (lo, const)
                    b = (hi, const)
                else:
                    a = (const, lo)
                    b = (const, hi)
                wall_id_counter += 1
                wall = Wall(
                    id=f"w{wall_id_counter}",
                    a=a,
                    b=b,
                    thickness_mm=INTERIOR_WALL_MM,
                    type="interior",
                )
                walls.append(wall)

                # Door, if these rooms are graph-adjacent and the wall is
                # long enough to host one.
                if _wants_door(e1.room_id, e2.room_id, adjacency_graph_edges):
                    door = _make_door(
                        wall.id,
                        wall_length=hi - lo,
                        room_a=program_by_id.get(e1.room_id, {}),
                        room_b=program_by_id.get(e2.room_id, {}),
                        opening_id=f"d{opening_id_counter + 1}",
                    )
                    if door:
                        opening_id_counter += 1
                        openings.append(door)

    # Ensure every walled room can be entered: if a room has no door, find
    # the best shared wall (preferring circulation > public > service) and
    # place one. Private-private walls (bedroom-bedroom) are last resort.
    openings = _ensure_room_reachability(
        rects, program_by_id, walls, openings, opening_id_counter
    )
    opening_id_counter = max((int(o.id[1:]) for o in openings if o.id.startswith("d")), default=0)

    # Windows on exterior walls for rooms needing daylight.
    windows = _place_windows(rects, program_by_id, walls, boundary_w, boundary_h, opening_id_counter)
    openings.extend(windows)

    return walls, openings


def _ensure_room_reachability(
    rects: dict[str, Rect],
    program_by_id: dict[str, dict],
    walls: list[Wall],
    openings: list[Opening],
    base_door_id: int,
) -> list[Opening]:
    """Make sure every walled room can be entered (has at least one door or
    is open-pair connected to another room).
    """
    # Track which rooms each door connects.
    walls_by_id = {w.id: w for w in walls}
    door_rooms: dict[str, set[str]] = {rid: set() for rid in rects}
    for op in openings:
        if op.kind != "door":
            continue
        wall = walls_by_id.get(op.wall_id)
        if wall is None:
            continue
        # Which two rooms does this wall separate? Find by edge match.
        for rid, rect in rects.items():
            if _wall_lies_on_room_edge(wall, rect):
                door_rooms[rid].add(op.id)

    # Open-pair connectivity: any two rooms that share an edge but no wall
    # between them are effectively connected.
    open_neighbors: dict[str, set[str]] = {rid: set() for rid in rects}
    rids = list(rects.keys())
    for i in range(len(rids)):
        for j in range(i + 1, len(rids)):
            a, b = rids[i], rids[j]
            shared_len = _shared_edge_length_rects(rects[a], rects[b])
            if shared_len <= 0:
                continue
            # Are they open-pair AND have no wall between them?
            ta = program_by_id.get(a, {}).get("type", "")
            tb = program_by_id.get(b, {}).get("type", "")
            if are_open_pair(ta, tb):
                open_neighbors[a].add(b)
                open_neighbors[b].add(a)

    # For each room with no door AND no open neighbor, place a door.
    next_id = base_door_id + 1
    for rid in rids:
        if door_rooms[rid]:
            continue
        if open_neighbors[rid]:
            continue
        # Find best shared wall.
        best_wall = _pick_door_wall(rid, rects, program_by_id, walls)
        if best_wall is None:
            continue
        other_id = _other_room_on_wall(best_wall, rid, rects)
        other_type = program_by_id.get(other_id, {}).get("type", "") if other_id else ""
        my_type = program_by_id.get(rid, {}).get("type", "")
        bathroom_types = {"full_bath", "powder"}
        if my_type in bathroom_types or other_type in bathroom_types:
            width = DOOR_WIDTHS_MM["bathroom"]
        else:
            width = DOOR_WIDTHS_MM["internal"]
        wall_len = _length_xy(best_wall.a, best_wall.b)
        if wall_len < width + 200:
            continue
        openings.append(
            Opening(
                id=f"d{next_id}",
                kind="door",
                wall_id=best_wall.id,
                position=0.5,
                width_mm=width,
                swing="in_left",
            )
        )
        door_rooms[rid].add(f"d{next_id}")
        if other_id:
            door_rooms[other_id].add(f"d{next_id}")
        next_id += 1

    return openings


def _wall_lies_on_room_edge(wall: Wall, rect: Rect) -> bool:
    """True if `wall`'s segment coincides with one edge of `rect`."""
    (ax, ay), (bx, by) = wall.a, wall.b
    rx, ry, rw, rh = rect.x, rect.y, rect.w, rect.h
    if abs(ay - by) < COLLINEAR_TOL:  # horizontal wall
        if abs(ay - ry) > COLLINEAR_TOL and abs(ay - (ry + rh)) > COLLINEAR_TOL:
            return False
        lo, hi = min(ax, bx), max(ax, bx)
        return lo >= rx - COLLINEAR_TOL and hi <= rx + rw + COLLINEAR_TOL
    # vertical
    if abs(ax - rx) > COLLINEAR_TOL and abs(ax - (rx + rw)) > COLLINEAR_TOL:
        return False
    lo, hi = min(ay, by), max(ay, by)
    return lo >= ry - COLLINEAR_TOL and hi <= ry + rh + COLLINEAR_TOL


def _shared_edge_length_rects(a: Rect, b: Rect) -> float:
    """Length of shared edge between two axis-aligned rects."""
    # Vertical line shared?
    if abs((a.x + a.w) - b.x) < COLLINEAR_TOL or abs((b.x + b.w) - a.x) < COLLINEAR_TOL:
        lo = max(a.y, b.y)
        hi = min(a.y + a.h, b.y + b.h)
        return max(0.0, hi - lo)
    # Horizontal line shared?
    if abs((a.y + a.h) - b.y) < COLLINEAR_TOL or abs((b.y + b.h) - a.y) < COLLINEAR_TOL:
        lo = max(a.x, b.x)
        hi = min(a.x + a.w, b.x + b.w)
        return max(0.0, hi - lo)
    return 0.0


def _pick_door_wall(
    room_id: str,
    rects: dict[str, Rect],
    program_by_id: dict[str, dict],
    walls: list[Wall],
) -> Wall | None:
    """Pick the best interior wall to door from `room_id`.

    Preference: circulation > public > service > private. Among ties,
    longest wall wins.
    """
    if room_id not in rects:
        return None
    rect = rects[room_id]
    zone_score = {"circulation": 4, "public": 3, "service": 2, "private": 1, "exterior": 0}
    best = None
    best_score = (-1, -1.0)
    for w in walls:
        if w.type != "interior":
            continue
        if not _wall_lies_on_room_edge(w, rect):
            continue
        other = _other_room_on_wall(w, room_id, rects)
        if other is None:
            continue
        other_zone = program_by_id.get(other, {}).get("zone", "")
        zs = zone_score.get(other_zone, 0)
        length = _length_xy(w.a, w.b)
        score = (zs, length)
        if score > best_score:
            best = w
            best_score = score
    return best


def _other_room_on_wall(wall: Wall, room_id: str, rects: dict[str, Rect]) -> str | None:
    for rid, rect in rects.items():
        if rid == room_id:
            continue
        if _wall_lies_on_room_edge(wall, rect):
            return rid
    return None


def _length_xy(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def _wants_door(
    room_a: str,
    room_b: str,
    edges: Iterable[tuple[str, str]],
) -> bool:
    e = set(tuple(sorted(p)) for p in edges)
    return tuple(sorted((room_a, room_b))) in e


def _make_door(
    wall_id: str,
    wall_length: float,
    room_a: dict,
    room_b: dict,
    opening_id: str,
) -> Opening | None:
    """Pick a door width that fits the shared wall."""
    bathroom_types = {"full_bath", "powder"}
    a_type = room_a.get("type", "")
    b_type = room_b.get("type", "")
    if a_type in bathroom_types or b_type in bathroom_types:
        width = DOOR_WIDTHS_MM["bathroom"]
    else:
        width = DOOR_WIDTHS_MM["internal"]
    # Need wall length >= door width + 200 mm of jamb on each side.
    if wall_length < width + 400:
        return None
    return Opening(
        id=opening_id,
        kind="door",
        wall_id=wall_id,
        position=0.5,
        width_mm=width,
        swing="in_left",
    )


def _place_windows(
    rects: dict[str, Rect],
    program_by_id: dict[str, dict],
    walls: list[Wall],
    boundary_w: float,
    boundary_h: float,
    base_id: int,
) -> list[Opening]:
    """One window per exterior-wall room that asks for daylight."""
    windows: list[Opening] = []
    next_id = base_id + 1

    # Index exterior walls by room. An exterior wall passes through a room's
    # rectangle if it lies on the boundary AND the wall span lies within the
    # room's extent on that axis.
    exterior_walls = [w for w in walls if w.type == "exterior"]

    for rid, r in rects.items():
        spec = program_by_id.get(rid, {})
        needs = spec.get("needs_window") or spec.get("needs_exterior_wall")
        if not needs:
            continue

        candidates: list[Wall] = []
        for w in exterior_walls:
            (ax, ay), (bx, by) = w.a, w.b
            if abs(ay - by) < COLLINEAR_TOL:  # horizontal wall (top/bottom)
                if abs(ay - r.y) < COLLINEAR_TOL or abs(ay - (r.y + r.h)) < COLLINEAR_TOL:
                    if ax >= r.x - COLLINEAR_TOL and bx <= r.x + r.w + COLLINEAR_TOL:
                        candidates.append(w)
            else:
                if abs(ax - r.x) < COLLINEAR_TOL or abs(ax - (r.x + r.w)) < COLLINEAR_TOL:
                    if ay >= r.y - COLLINEAR_TOL and by <= r.y + r.h + COLLINEAR_TOL:
                        candidates.append(w)

        if not candidates:
            continue

        # Pick the longest candidate.
        w = max(candidates, key=lambda w: _wall_length(w))
        length = _wall_length(w)
        # Window width: glazing ratio (8-10% by floor area, but capped to wall).
        floor_area = r.w * r.h
        glazing_target = 0.10 * floor_area  # NBC default
        # Assume sill height + lintel; approximate window with width only.
        window_w = max(600, min(length - 600, glazing_target / 1500))
        if window_w < 600:
            continue
        windows.append(
            Opening(
                id=f"win{next_id}",
                kind="window",
                wall_id=w.id,
                position=0.5,
                width_mm=int(window_w),
                is_egress=bool(spec.get("needs_egress", False)),
            )
        )
        next_id += 1
    return windows


def _wall_length(w: Wall) -> float:
    (ax, ay), (bx, by) = w.a, w.b
    return ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5


# ----------------------------------------------------------------------
# Pipeline glue
# ----------------------------------------------------------------------


def finish_floor_plan(
    boundary: Boundary,
    rects: dict[str, Rect],
    program_rooms: list[dict],
    adjacency_pairs: Iterable[tuple[str, str]],
    *,
    grid_mm: float = GRID_MM,
) -> FloorPlan:
    """Run the finishing passes and return a validated FloorPlan."""
    # 1. Snap.
    snapped = snap_rects_to_grid(rects, boundary.width_mm, boundary.depth_mm, grid_mm)

    # 2. Rooms from rectangles.
    program_by_id = {r["id"]: r for r in program_rooms}
    rooms: list[Room] = []
    for spec in program_rooms:
        rect = snapped[spec["id"]]
        polygon = [
            (rect.x, rect.y),
            (rect.x + rect.w, rect.y),
            (rect.x + rect.w, rect.y + rect.h),
            (rect.x, rect.y + rect.h),
        ]
        catalog = CATALOG_BY_TYPE.get(spec["type"])
        rooms.append(
            Room(
                id=spec["id"],
                type=spec["type"],
                label=spec["label"],
                zone=spec["zone"],
                polygon=polygon,
                area_mm2=rect.area,
                needs_window=catalog.needs_window if catalog else spec.get("needs_window", False),
                needs_egress=catalog.needs_egress if catalog else spec.get("needs_egress", False),
                needs_exterior_wall=(
                    catalog.needs_exterior_wall if catalog else spec.get("needs_exterior_wall", False)
                ),
            )
        )

    # 3. Walls + openings.
    walls, openings = build_walls_and_openings(
        snapped,
        program_by_id,
        boundary.width_mm,
        boundary.depth_mm,
        adjacency_pairs,
    )

    fixtures = place_fixtures_in_plan(rooms)

    plan = FloorPlan(
        boundary=boundary,
        rooms=rooms,
        walls=walls,
        openings=openings,
        fixtures=fixtures,
        meta=PlanMeta(),
    )

    validate_floor_plan(plan)
    return plan


__all__ = [
    "build_walls_and_openings",
    "finish_floor_plan",
    "snap_rects_to_grid",
    "CORRIDOR_MIN_WIDTH_MM",
]
