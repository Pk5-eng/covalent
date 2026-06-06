"""Fixture / furniture placement for finished rooms.

Each catalog room type maps to a small list of fixtures (bed, sink,
toilet, sofa, ...). The placer reads room rectangles after the
finishing pass and lays out fixtures along walls or at the centre.
Rendered on the A-FLOR-FIXT layer in both SVG and DXF.

The point isn't precise furniture layout — it's enough graphic content
to make the plan read as a real residential drawing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models import Fixture, Room

# Standoff from the wall poche so fixtures don't sit on top of the wall line.
WALL_STANDOFF_MM = 80


Placement = Literal[
    "wall_long",       # along the longer wall
    "wall_short",      # along the shorter wall
    "wall_long_alt",   # second fixture along long wall (opposite side or same wall, offset)
    "wall_short_alt",  # second fixture along short wall (opposite side)
    "corner_long_short",  # corner where long + short meet (start of long wall)
    "center",          # geometric centre of the room
    "counter_run",     # along entire long wall, against it (kitchen counter style)
]


@dataclass(frozen=True)
class FixtureSpec:
    kind: str
    label: str
    width_mm: int      # dim along the wall (or X if centred)
    depth_mm: int      # dim away from the wall (or Y if centred)
    placement: Placement


# Per-room-type fixture lists. Order matters: earlier fixtures get first dibs
# on the preferred wall; later ones take what's left.
FIXTURE_TEMPLATES: dict[str, list[FixtureSpec]] = {
    "primary_bedroom": [
        FixtureSpec("bed", "King bed", 2000, 2000, "wall_long"),
        FixtureSpec("nightstand", "", 500, 400, "wall_long_alt"),
        FixtureSpec("wardrobe", "Wardrobe", 1800, 600, "wall_short"),
    ],
    "bedroom": [
        FixtureSpec("bed", "Bed", 1900, 1500, "wall_long"),
        FixtureSpec("wardrobe", "Wardrobe", 1500, 600, "wall_short"),
    ],
    "kids_room": [
        FixtureSpec("bed", "Bed", 1900, 1200, "wall_long"),
        FixtureSpec("desk", "Desk", 1200, 600, "wall_short"),
    ],
    "guest_room": [
        FixtureSpec("bed", "Bed", 1900, 1500, "wall_long"),
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
        FixtureSpec("wardrobe", "", 2000, 600, "wall_long"),
    ],
    "dressing_room": [
        FixtureSpec("wardrobe", "Wardrobe", 2000, 600, "wall_long"),
        FixtureSpec("wardrobe", "", 1500, 600, "wall_short"),
    ],
    # public
    "living_room": [
        FixtureSpec("sofa", "Sofa", 2300, 900, "wall_long"),
        FixtureSpec("coffee_table", "", 1100, 600, "center"),
    ],
    "family_room": [
        FixtureSpec("sofa", "Sofa", 2200, 900, "wall_long"),
        FixtureSpec("coffee_table", "", 1100, 600, "center"),
    ],
    "media_room": [
        FixtureSpec("sofa", "Sofa", 2400, 900, "wall_long"),
    ],
    "dining_room": [
        FixtureSpec("table", "Dining table", 1800, 1000, "center"),
    ],
    "kitchen": [
        FixtureSpec("counter", "", 600, 600, "counter_run"),
        FixtureSpec("fridge", "Fridge", 700, 700, "wall_short"),
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
    # service
    "full_bath": [
        FixtureSpec("tub", "Tub", 1700, 750, "wall_long"),
        FixtureSpec("toilet", "WC", 400, 700, "wall_short"),
        FixtureSpec("sink", "Sink", 600, 500, "wall_short_alt"),
    ],
    "powder": [
        FixtureSpec("toilet", "WC", 400, 700, "wall_short"),
        FixtureSpec("sink", "Sink", 500, 500, "wall_long"),
    ],
    "laundry": [
        FixtureSpec("washer", "Washer", 700, 700, "wall_long"),
        FixtureSpec("dryer", "Dryer", 700, 700, "wall_long_alt"),
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
    # exterior
    "patio": [
        FixtureSpec("table", "Table", 1400, 1400, "center"),
    ],
    "deck": [
        FixtureSpec("table", "Table", 1400, 1400, "center"),
    ],
    "balcony": [],
    "porch": [],
}


def place_fixtures_in_plan(rooms: list[Room]) -> list[Fixture]:
    """Generate fixtures for every room in the plan."""
    out: list[Fixture] = []
    counter = 0
    for room in rooms:
        specs = FIXTURE_TEMPLATES.get(room.type, [])
        for spec in specs:
            placed = _place_one(room, spec, counter)
            if placed is None:
                continue
            counter += 1
            out.append(placed)
    return out


# ----------------------------------------------------------------------
# Placement implementation
# ----------------------------------------------------------------------


def _room_rect(room: Room) -> tuple[float, float, float, float]:
    xs = [p[0] for p in room.polygon]
    ys = [p[1] for p in room.polygon]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return x0, y0, x1 - x0, y1 - y0


def _place_one(room: Room, spec: FixtureSpec, idx: int) -> Fixture | None:
    rx, ry, rw, rh = _room_rect(room)
    inner_w = rw - 2 * WALL_STANDOFF_MM
    inner_h = rh - 2 * WALL_STANDOFF_MM
    if inner_w <= 0 or inner_h <= 0:
        return None

    long_axis = "x" if rw >= rh else "y"

    fid = f"fx{idx + 1}"

    def fixture_polygon(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
        return [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]

    if spec.placement == "center":
        w = min(spec.width_mm, inner_w * 0.7)
        h = min(spec.depth_mm, inner_h * 0.7)
        x = rx + (rw - w) / 2
        y = ry + (rh - h) / 2
        return Fixture(
            id=fid,
            room_id=room.id,
            kind=spec.kind,
            label=spec.label,
            polygon=fixture_polygon(x, y, w, h),
            rotation_deg=0,
        )

    if spec.placement == "counter_run":
        # L-shaped counter along the longer + adjacent short wall.
        depth = min(spec.depth_mm, inner_w * 0.4, inner_h * 0.4)
        if long_axis == "x":
            # counter along top wall (y = ry) full width, depth into room.
            x = rx + WALL_STANDOFF_MM
            y = ry + WALL_STANDOFF_MM
            w = rw - 2 * WALL_STANDOFF_MM
            h = depth
        else:
            # counter along left wall (x = rx) full height.
            x = rx + WALL_STANDOFF_MM
            y = ry + WALL_STANDOFF_MM
            w = depth
            h = rh - 2 * WALL_STANDOFF_MM
        return Fixture(
            id=fid,
            room_id=room.id,
            kind=spec.kind,
            label=spec.label,
            polygon=fixture_polygon(x, y, w, h),
            rotation_deg=0,
        )

    # Wall-placed fixtures: figure out which wall and where on it.
    wall = _pick_wall(spec.placement, long_axis)
    return _place_against_wall(room, spec, fid, wall, rx, ry, rw, rh)


def _pick_wall(placement: Placement, long_axis: str) -> str:
    """Return one of: 'top', 'bottom', 'left', 'right'."""
    # If room's long axis is X, the longer walls are top/bottom (horizontal),
    # and the shorter walls are left/right (vertical).
    if placement == "wall_long":
        return "top" if long_axis == "x" else "left"
    if placement == "wall_long_alt":
        return "bottom" if long_axis == "x" else "right"
    if placement == "wall_short":
        return "left" if long_axis == "x" else "top"
    if placement == "wall_short_alt":
        return "right" if long_axis == "x" else "bottom"
    if placement == "corner_long_short":
        return "top" if long_axis == "x" else "left"
    return "top"


def _place_against_wall(
    room: Room,
    spec: FixtureSpec,
    fid: str,
    wall: str,
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> Fixture | None:
    # Along-wall axis vs perpendicular axis.
    if wall in ("top", "bottom"):
        along_avail = rw - 2 * WALL_STANDOFF_MM
        perp_avail = rh - 2 * WALL_STANDOFF_MM
        w_along = min(spec.width_mm, along_avail)
        d_perp = min(spec.depth_mm, perp_avail)
        if w_along <= 100 or d_perp <= 100:
            return None
        x = rx + (rw - w_along) / 2
        if wall == "top":
            y = ry + WALL_STANDOFF_MM
        else:
            y = ry + rh - WALL_STANDOFF_MM - d_perp
        rot = 0 if wall == "top" else 180
        return Fixture(
            id=fid,
            room_id=room.id,
            kind=spec.kind,
            label=spec.label,
            polygon=[
                (x, y),
                (x + w_along, y),
                (x + w_along, y + d_perp),
                (x, y + d_perp),
            ],
            rotation_deg=rot,
        )
    # Left or right wall: spec.width_mm is along the wall (vertical), depth is into the room.
    along_avail = rh - 2 * WALL_STANDOFF_MM
    perp_avail = rw - 2 * WALL_STANDOFF_MM
    w_along = min(spec.width_mm, along_avail)
    d_perp = min(spec.depth_mm, perp_avail)
    if w_along <= 100 or d_perp <= 100:
        return None
    y = ry + (rh - w_along) / 2
    if wall == "left":
        x = rx + WALL_STANDOFF_MM
        rot = 90
    else:
        x = rx + rw - WALL_STANDOFF_MM - d_perp
        rot = 270
    return Fixture(
        id=fid,
        room_id=room.id,
        kind=spec.kind,
        label=spec.label,
        polygon=[
            (x, y),
            (x + d_perp, y),
            (x + d_perp, y + w_along),
            (x, y + w_along),
        ],
        rotation_deg=rot,
    )


__all__ = ["FIXTURE_TEMPLATES", "FixtureSpec", "place_fixtures_in_plan"]
