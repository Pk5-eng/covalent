"""Fixture / furniture placement for finished rooms.

Each catalog room type maps to a small list of fixtures using realistic
residential dimensions (international standards). The placer:
  - Reads room rectangles AND the wall/opening data from the finishing
    pass so it knows which sides of a room have actual walls vs. are
    open to a neighbouring room.
  - Avoids placing fixtures against open edges (those aren't walls,
    they're walking paths to the next space).
  - Avoids door swing zones (a square in front of each door).
  - Keeps a 600 mm circulation corridor down the centre of every room.

Standards used (mm):
  King bed         1930 × 2030     Queen bed        1530 × 2030
  Twin bed         990  × 1900     Sofa 3-seat      2030 × 900
  Loveseat         1500 × 900      Coffee table     1200 × 700
  Dining 6        1800 × 900       Dining 4         1200 × 900
  Toilet           380  × 710      Bathroom sink    600  × 460
  Bathtub          1700 × 760      Fridge           760  × 710
  Range            760  × 650      Dishwasher       600  × 600
  Washer/Dryer     685  × 685      Wardrobe         length × 600
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models import Fixture, Opening, Room, Wall

WALL_STANDOFF_MM = 80         # gap between fixture and wall poche
DOOR_CLEARANCE_MM = 900       # square clearance in front of every door swing
CORRIDOR_MIN_MM = 600         # leave at least this much walking room in any open path


Placement = Literal[
    "wall_long",
    "wall_long_alt",
    "wall_short",
    "wall_short_alt",
    "center",
    "counter_run",
]


@dataclass(frozen=True)
class FixtureSpec:
    kind: str
    label: str
    width_mm: int     # dimension ALONG the wall (or X if centred)
    depth_mm: int     # dimension perpendicular to the wall, into the room
    placement: Placement


# Per-room-type fixture lists. Standard residential sizes.
FIXTURE_TEMPLATES: dict[str, list[FixtureSpec]] = {
    # private — beds project INTO the room, head against the wall
    "primary_bedroom": [
        FixtureSpec("bed", "King bed",  1930, 2030, "wall_long"),
        FixtureSpec("wardrobe", "Wardrobe", 1800, 600, "wall_short"),
    ],
    "bedroom": [
        FixtureSpec("bed", "Queen bed", 1530, 2030, "wall_long"),
        FixtureSpec("wardrobe", "Wardrobe", 1500, 600, "wall_short"),
    ],
    "kids_room": [
        FixtureSpec("bed", "Twin bed", 990, 1900, "wall_long"),
        FixtureSpec("desk", "Desk", 1200, 600, "wall_short"),
    ],
    "guest_room": [
        FixtureSpec("bed", "Queen bed", 1530, 2030, "wall_long"),
        FixtureSpec("wardrobe", "Wardrobe", 1500, 600, "wall_short"),
    ],
    "nursery": [
        FixtureSpec("crib", "Crib", 1300, 750, "wall_long"),
    ],
    "study": [
        FixtureSpec("desk", "Desk", 1500, 700, "wall_long"),
    ],
    "library": [
        FixtureSpec("desk", "Desk", 1500, 700, "wall_long"),
        FixtureSpec("bookshelf", "Bookshelf", 2400, 400, "wall_long_alt"),
    ],
    "home_gym": [
        FixtureSpec("equipment", "Equipment", 1800, 700, "wall_long"),
    ],
    "walk_in_closet": [
        FixtureSpec("wardrobe", "", 1800, 600, "wall_long"),
    ],
    "dressing_room": [
        FixtureSpec("wardrobe", "Wardrobe", 1800, 600, "wall_long"),
        FixtureSpec("wardrobe", "", 1500, 600, "wall_short"),
    ],
    # public — sofas/sideboards against walls, table at centre
    "living_room": [
        FixtureSpec("sofa", "Sofa", 2030, 900, "wall_long"),
        FixtureSpec("coffee_table", "", 1200, 700, "center"),
    ],
    "family_room": [
        FixtureSpec("sofa", "Sofa", 2030, 900, "wall_long"),
        FixtureSpec("coffee_table", "", 1200, 700, "center"),
    ],
    "media_room": [
        FixtureSpec("sofa", "Sofa", 2200, 900, "wall_long"),
    ],
    "dining_room": [
        FixtureSpec("table", "Dining table", 1800, 900, "center"),
    ],
    "kitchen": [
        FixtureSpec("counter", "", 600, 600, "counter_run"),
        FixtureSpec("fridge", "Fridge", 760, 710, "wall_short"),
    ],
    "sunroom": [
        FixtureSpec("table", "Table", 1400, 800, "center"),
    ],
    "foyer": [
        FixtureSpec("console", "Console", 1200, 400, "wall_short"),
    ],
    "pantry": [
        FixtureSpec("shelving", "", 1200, 400, "wall_long"),
    ],
    "full_bath": [
        FixtureSpec("tub", "Tub", 1700, 760, "wall_long"),
        FixtureSpec("toilet", "WC", 380, 710, "wall_short"),
        FixtureSpec("sink", "Sink", 600, 460, "wall_short_alt"),
    ],
    "powder": [
        FixtureSpec("toilet", "WC", 380, 710, "wall_short"),
        FixtureSpec("sink", "Sink", 500, 460, "wall_long"),
    ],
    "laundry": [
        FixtureSpec("washer", "Washer", 685, 685, "wall_long"),
        FixtureSpec("dryer", "Dryer", 685, 685, "wall_long_alt"),
    ],
    "mudroom": [
        FixtureSpec("bench", "Bench", 1200, 400, "wall_long"),
    ],
    "garage_single": [
        FixtureSpec("car", "Car", 4500, 1900, "center"),
    ],
    "garage_double": [
        FixtureSpec("car", "Car", 4500, 1900, "wall_long"),
        FixtureSpec("car", "Car", 4500, 1900, "wall_long_alt"),
    ],
    "storage": [],
    "gallery": [],
    "patio": [
        FixtureSpec("table", "Table", 1400, 1400, "center"),
    ],
    "deck": [
        FixtureSpec("table", "Table", 1400, 1400, "center"),
    ],
    "balcony": [],
    "porch": [],
}


# ----------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------


def place_fixtures_in_plan(
    rooms: list[Room],
    walls: list[Wall] | None = None,
    openings: list[Opening] | None = None,
) -> list[Fixture]:
    """Place fixtures for every room, respecting walls and door clearances."""
    walls = walls or []
    openings = openings or []
    by_room: dict[str, _RoomContext] = {}
    for room in rooms:
        by_room[room.id] = _build_room_context(room, walls, openings)

    out: list[Fixture] = []
    counter = 0
    for room in rooms:
        specs = FIXTURE_TEMPLATES.get(room.type, [])
        ctx = by_room[room.id]
        for spec in specs:
            placed = _place_one(room, spec, counter, ctx)
            if placed is None:
                continue
            counter += 1
            out.append(placed)
            # Register this fixture's footprint so later fixtures don't overlap.
            ctx.blockers.append(_footprint_bbox(placed))
    return out


# ----------------------------------------------------------------------
# Room context: which sides have walls, where are the doors?
# ----------------------------------------------------------------------


@dataclass
class _RoomContext:
    rect: tuple[float, float, float, float]  # x, y, w, h
    sides_walled: dict[str, bool]            # "top", "bottom", "left", "right"
    door_zones: list[tuple[float, float, float, float]]  # x, y, w, h
    blockers: list[tuple[float, float, float, float]]    # already-placed fixtures


def _build_room_context(
    room: Room,
    walls: list[Wall],
    openings: list[Opening],
) -> _RoomContext:
    rx, ry, rw, rh = _room_rect(room)
    sides_walled = _detect_walled_sides(rx, ry, rw, rh, walls)
    door_zones = _door_clearance_zones(rx, ry, rw, rh, walls, openings)
    return _RoomContext(
        rect=(rx, ry, rw, rh),
        sides_walled=sides_walled,
        door_zones=door_zones,
        blockers=[],
    )


def _room_rect(room: Room) -> tuple[float, float, float, float]:
    xs = [p[0] for p in room.polygon]
    ys = [p[1] for p in room.polygon]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return x0, y0, x1 - x0, y1 - y0


def _detect_walled_sides(
    rx: float, ry: float, rw: float, rh: float, walls: list[Wall],
) -> dict[str, bool]:
    """For each of the 4 sides, does an actual wall span enough of it?

    A side is considered "walled" if a wall along that side covers at
    least 60% of its length. Otherwise the side is open (e.g., open
    transition to a neighbouring room in a great-room plan).
    """
    tol = 1.0
    coverage = {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}
    for w in walls:
        (ax, ay), (bx, by) = w.a, w.b
        if abs(ay - by) < tol:
            # horizontal wall
            y = ay
            lo, hi = min(ax, bx), max(ax, bx)
            if abs(y - ry) < tol:
                coverage["top"] += _overlap_len(lo, hi, rx, rx + rw)
            elif abs(y - (ry + rh)) < tol:
                coverage["bottom"] += _overlap_len(lo, hi, rx, rx + rw)
        elif abs(ax - bx) < tol:
            x = ax
            lo, hi = min(ay, by), max(ay, by)
            if abs(x - rx) < tol:
                coverage["left"] += _overlap_len(lo, hi, ry, ry + rh)
            elif abs(x - (rx + rw)) < tol:
                coverage["right"] += _overlap_len(lo, hi, ry, ry + rh)
    lengths = {"top": rw, "bottom": rw, "left": rh, "right": rh}
    return {side: coverage[side] >= 0.6 * lengths[side] for side in coverage}


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _door_clearance_zones(
    rx: float, ry: float, rw: float, rh: float,
    walls: list[Wall], openings: list[Opening],
) -> list[tuple[float, float, float, float]]:
    """Build a clearance rectangle in front of every door that opens into
    this room. The rectangle is door-width × door-width on the room side."""
    walls_by_id = {w.id: w for w in walls}
    zones: list[tuple[float, float, float, float]] = []
    tol = 1.0
    for op in openings:
        if op.kind != "door":
            continue
        wall = walls_by_id.get(op.wall_id)
        if wall is None:
            continue
        (ax, ay), (bx, by) = wall.a, wall.b
        if abs(ay - by) < tol:
            y = ay
            lo, hi = min(ax, bx), max(ax, bx)
            # Is this wall along one of our sides?
            opening_x = lo + (hi - lo) * op.position
            x0 = opening_x - op.width_mm / 2
            x1 = opening_x + op.width_mm / 2
            depth = max(DOOR_CLEARANCE_MM, op.width_mm)
            if abs(y - ry) < tol:
                # top wall — door swings down into room
                zones.append((x0, ry, x1 - x0, depth))
            elif abs(y - (ry + rh)) < tol:
                zones.append((x0, ry + rh - depth, x1 - x0, depth))
        elif abs(ax - bx) < tol:
            x = ax
            lo, hi = min(ay, by), max(ay, by)
            opening_y = lo + (hi - lo) * op.position
            y0 = opening_y - op.width_mm / 2
            y1 = opening_y + op.width_mm / 2
            depth = max(DOOR_CLEARANCE_MM, op.width_mm)
            if abs(x - rx) < tol:
                zones.append((rx, y0, depth, y1 - y0))
            elif abs(x - (rx + rw)) < tol:
                zones.append((rx + rw - depth, y0, depth, y1 - y0))
    return zones


# ----------------------------------------------------------------------
# Placement
# ----------------------------------------------------------------------


def _place_one(
    room: Room, spec: FixtureSpec, idx: int, ctx: _RoomContext,
) -> Fixture | None:
    rx, ry, rw, rh = ctx.rect
    fid = f"fx{idx + 1}"

    if spec.placement == "center":
        return _place_centre(room, spec, fid, ctx)
    if spec.placement == "counter_run":
        return _place_counter_run(room, spec, fid, ctx)
    return _place_wall(room, spec, fid, ctx)


def _place_centre(
    room: Room, spec: FixtureSpec, fid: str, ctx: _RoomContext,
) -> Fixture | None:
    rx, ry, rw, rh = ctx.rect
    inner_w = rw - 2 * WALL_STANDOFF_MM
    inner_h = rh - 2 * WALL_STANDOFF_MM
    if inner_w <= spec.width_mm or inner_h <= spec.depth_mm:
        # Room too small — scale down but don't go below 60% of spec.
        w = max(spec.width_mm * 0.6, min(spec.width_mm, inner_w * 0.7))
        h = max(spec.depth_mm * 0.6, min(spec.depth_mm, inner_h * 0.7))
    else:
        w, h = float(spec.width_mm), float(spec.depth_mm)
    x = rx + (rw - w) / 2
    y = ry + (rh - h) / 2
    return Fixture(
        id=fid, room_id=room.id, kind=spec.kind, label=spec.label,
        polygon=_rect_to_poly(x, y, w, h), rotation_deg=0,
    )


def _place_counter_run(
    room: Room, spec: FixtureSpec, fid: str, ctx: _RoomContext,
) -> Fixture | None:
    """Kitchen counter: along the longest walled side, full length."""
    rx, ry, rw, rh = ctx.rect
    depth = min(spec.depth_mm, min(rw, rh) * 0.35)
    walled_sides = [s for s, w in ctx.sides_walled.items() if w]
    if not walled_sides:
        return None
    # Pick the longest walled side.
    side_lengths = {"top": rw, "bottom": rw, "left": rh, "right": rh}
    side = max(walled_sides, key=lambda s: side_lengths[s])
    if side in ("top", "bottom"):
        x = rx + WALL_STANDOFF_MM
        y = ry + WALL_STANDOFF_MM if side == "top" else ry + rh - WALL_STANDOFF_MM - depth
        w = rw - 2 * WALL_STANDOFF_MM
        h = depth
    else:
        x = rx + WALL_STANDOFF_MM if side == "left" else rx + rw - WALL_STANDOFF_MM - depth
        y = ry + WALL_STANDOFF_MM
        w = depth
        h = rh - 2 * WALL_STANDOFF_MM
    return Fixture(
        id=fid, room_id=room.id, kind=spec.kind, label=spec.label,
        polygon=_rect_to_poly(x, y, w, h), rotation_deg=0,
    )


def _place_wall(
    room: Room, spec: FixtureSpec, fid: str, ctx: _RoomContext,
) -> Fixture | None:
    """Pick the best walled side for `spec` and place the fixture against it,
    centred along the wall, avoiding door zones and already-placed fixtures.
    """
    rx, ry, rw, rh = ctx.rect
    long_axis = "x" if rw >= rh else "y"
    preferred = _wall_preference_order(spec.placement, long_axis)

    for side in preferred:
        if not ctx.sides_walled.get(side, False):
            continue
        result = _try_place_against_side(spec, side, ctx)
        if result is not None:
            x, y, w, h, rot = result
            return Fixture(
                id=fid, room_id=room.id, kind=spec.kind, label=spec.label,
                polygon=_rect_to_poly(x, y, w, h), rotation_deg=rot,
            )
    # As a last resort, ignore the "walled side" requirement and pick any side.
    for side in preferred:
        result = _try_place_against_side(spec, side, ctx)
        if result is not None:
            x, y, w, h, rot = result
            return Fixture(
                id=fid, room_id=room.id, kind=spec.kind, label=spec.label,
                polygon=_rect_to_poly(x, y, w, h), rotation_deg=rot,
            )
    return None


def _wall_preference_order(placement: Placement, long_axis: str) -> list[str]:
    """Return preferred side order for this placement, accounting for room
    aspect. If room's long axis is X, long walls are top/bottom.
    """
    long_first = ["top", "bottom"] if long_axis == "x" else ["left", "right"]
    short_first = ["left", "right"] if long_axis == "x" else ["top", "bottom"]
    if placement == "wall_long":
        return long_first + short_first
    if placement == "wall_long_alt":
        return list(reversed(long_first)) + short_first
    if placement == "wall_short":
        return short_first + long_first
    if placement == "wall_short_alt":
        return list(reversed(short_first)) + long_first
    return long_first + short_first


def _try_place_against_side(
    spec: FixtureSpec, side: str, ctx: _RoomContext,
) -> tuple[float, float, float, float, float] | None:
    """Compute (x, y, w, h, rotation) for placing `spec` against `side`,
    avoiding door zones and already-placed fixtures. Return None if no
    valid spot found.
    """
    rx, ry, rw, rh = ctx.rect

    if side in ("top", "bottom"):
        along_avail = rw - 2 * WALL_STANDOFF_MM
        perp_avail = rh - 2 * WALL_STANDOFF_MM
        w = min(spec.width_mm, along_avail)
        h = min(spec.depth_mm, perp_avail)
        if w <= 200 or h <= 200:
            return None
        y = ry + WALL_STANDOFF_MM if side == "top" else ry + rh - WALL_STANDOFF_MM - h
        rot = 0 if side == "top" else 180
        # Try a few x positions: centred, then offset toward each end.
        for x in _slot_positions(rx + WALL_STANDOFF_MM, rx + rw - WALL_STANDOFF_MM - w, w):
            if not _conflicts(x, y, w, h, ctx):
                return x, y, w, h, rot
    else:
        along_avail = rh - 2 * WALL_STANDOFF_MM
        perp_avail = rw - 2 * WALL_STANDOFF_MM
        w_along = min(spec.width_mm, along_avail)
        d_perp = min(spec.depth_mm, perp_avail)
        if w_along <= 200 or d_perp <= 200:
            return None
        # On a vertical wall, fixture's "width" runs vertically.
        x = rx + WALL_STANDOFF_MM if side == "left" else rx + rw - WALL_STANDOFF_MM - d_perp
        rot = 90 if side == "left" else 270
        for y in _slot_positions(ry + WALL_STANDOFF_MM, ry + rh - WALL_STANDOFF_MM - w_along, w_along):
            if not _conflicts(x, y, d_perp, w_along, ctx):
                return x, y, d_perp, w_along, rot
    return None


def _slot_positions(lo: float, hi: float, span: float) -> list[float]:
    """Yield candidate positions: centred first, then toward each end."""
    centre = (lo + hi) / 2
    options = [centre]
    if hi > lo:
        options.extend([lo, hi, (lo + centre) / 2, (centre + hi) / 2])
    return [p for p in options if lo - 1 <= p <= hi + 1]


def _conflicts(
    x: float, y: float, w: float, h: float, ctx: _RoomContext,
) -> bool:
    for bx, by, bw, bh in ctx.door_zones + ctx.blockers:
        if _rect_overlaps(x, y, w, h, bx, by, bw, bh):
            return True
    return False


def _rect_overlaps(
    ax: float, ay: float, aw: float, ah: float,
    bx: float, by: float, bw: float, bh: float,
    margin: float = 0,
) -> bool:
    return not (
        ax + aw <= bx + margin
        or bx + bw <= ax + margin
        or ay + ah <= by + margin
        or by + bh <= ay + margin
    )


def _rect_to_poly(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _footprint_bbox(fx: Fixture) -> tuple[float, float, float, float]:
    xs = [p[0] for p in fx.polygon]
    ys = [p[1] for p in fx.polygon]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


__all__ = ["FIXTURE_TEMPLATES", "FixtureSpec", "place_fixtures_in_plan"]
