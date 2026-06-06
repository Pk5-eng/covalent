"""Architectural rules and defaults (Section 7 of the spec).

Illustrative values. Jurisdiction-specific tuning is configurable via the
JURISDICTION dict below. Areas are stored in m^2 because that is how
architects discuss programs; geometry stays in mm everywhere else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Zone = Literal["public", "private", "service", "circulation", "exterior"]


@dataclass(frozen=True)
class RoomSpec:
    type: str
    label: str
    zone: Zone
    target_m2: float
    min_m2: float
    min_width_m: float
    needs_window: bool
    needs_egress: bool
    needs_exterior_wall: bool = False
    max_count: int = 8  # palette stepper cap


# Section 7 catalog. Order matters for UI grouping.
ROOM_CATALOG: list[RoomSpec] = [
    # public
    RoomSpec("foyer",          "Foyer / Entry",     "public",  4,  2,   1.5, False, False, needs_exterior_wall=True, max_count=1),
    RoomSpec("living_room",    "Living Room",       "public",  22, 14,  3.5, True,  False, needs_exterior_wall=True, max_count=2),
    RoomSpec("family_room",    "Family Room",       "public",  18, 12,  3.2, True,  False, needs_exterior_wall=True, max_count=2),
    RoomSpec("dining_room",    "Dining Room",       "public",  14, 9,   3.0, True,  False, needs_exterior_wall=True, max_count=2),
    RoomSpec("kitchen",        "Kitchen",           "public",  12, 7,   2.4, True,  False, needs_exterior_wall=True, max_count=2),
    RoomSpec("sunroom",        "Sunroom",           "public",  12, 8,   2.7, True,  False, needs_exterior_wall=True, max_count=1),
    RoomSpec("media_room",     "Media Room",        "public",  16, 11,  3.2, False, False, max_count=1),
    # service
    RoomSpec("pantry",         "Pantry",            "service", 3,  1.5, 1.2, False, False, max_count=2),
    RoomSpec("full_bath",      "Full Bathroom",     "service", 5,  3.5, 1.8, False, False, max_count=6),
    RoomSpec("powder",         "Half Bath / Powder","service", 2,  1.4, 1.0, False, False, max_count=3),
    RoomSpec("laundry",        "Laundry / Utility", "service", 5,  3,   1.8, False, False, max_count=2),
    RoomSpec("mudroom",        "Mudroom",           "service", 5,  3,   1.5, False, False, max_count=1),
    RoomSpec("garage_single",  "Garage (single)",   "service", 18, 15,  3.0, False, False, needs_exterior_wall=True, max_count=2),
    RoomSpec("garage_double",  "Garage (double)",   "service", 36, 32,  5.5, False, False, needs_exterior_wall=True, max_count=1),
    RoomSpec("storage",        "Storage",           "service", 4,  1.5, 1.0, False, False, max_count=4),
    # private
    RoomSpec("primary_bedroom","Primary Bedroom",   "private", 18, 12,  3.0, True,  True,  needs_exterior_wall=True, max_count=1),
    RoomSpec("bedroom",        "Bedroom",           "private", 13, 10,  2.7, True,  True,  needs_exterior_wall=True, max_count=6),
    RoomSpec("kids_room",      "Kids Room",         "private", 12, 9,   2.7, True,  True,  needs_exterior_wall=True, max_count=4),
    RoomSpec("nursery",        "Nursery",           "private", 9,  7,   2.4, True,  True,  needs_exterior_wall=True, max_count=2),
    RoomSpec("study",          "Home Office",       "private", 10, 7,   2.4, True,  False, needs_exterior_wall=True, max_count=2),
    RoomSpec("guest_room",     "Guest Room",        "private", 12, 9,   2.7, True,  True,  needs_exterior_wall=True, max_count=2),
    RoomSpec("walk_in_closet", "Walk-in Closet",    "private", 4,  2,   1.2, False, False, max_count=4),
    RoomSpec("home_gym",       "Home Gym",          "private", 14, 9,   3.0, False, False, max_count=1),
    RoomSpec("library",        "Library",           "private", 14, 8,   2.7, True,  False, needs_exterior_wall=True, max_count=1),
    RoomSpec("dressing_room",  "Dressing Room",     "private", 8,  5,   2.0, False, False, max_count=2),
    # circulation
    RoomSpec("gallery",        "Gallery / Hall",    "circulation", 8, 4,   1.2, False, False, max_count=2),
    # exterior
    RoomSpec("patio",          "Patio",             "exterior",12, 6,   2.4, False, False, needs_exterior_wall=True, max_count=2),
    RoomSpec("deck",           "Deck",              "exterior",14, 6,   2.4, False, False, needs_exterior_wall=True, max_count=2),
    RoomSpec("balcony",        "Balcony",           "exterior", 5, 3,   1.2, False, False, needs_exterior_wall=True, max_count=2),
    RoomSpec("porch",          "Porch",             "exterior", 6, 3,   1.5, False, False, needs_exterior_wall=True, max_count=2),
]

CATALOG_BY_TYPE: dict[str, RoomSpec] = {r.type: r for r in ROOM_CATALOG}

# Pair adjacency weights (positive = attract, negative = repel).
# Keys are sorted-tuple of room types. Use ROOM_TYPE wildcards via lookup.
ADJACENCY_WEIGHTS: dict[tuple[str, str], float] = {
    ("kitchen", "dining_room"): +3,
    ("kitchen", "living_room"): +2,
    ("dining_room", "living_room"): +2,
    ("primary_bedroom", "full_bath"): +3,
    ("bedroom", "bedroom"): +1,
    ("garage_single", "mudroom"): +3,
    ("garage_double", "mudroom"): +3,
    ("mudroom", "kitchen"): +2,
    ("powder", "living_room"): +2,
    ("powder", "foyer"): +2,
    ("powder", "kitchen"): -2,
    ("powder", "dining_room"): -2,
    ("laundry", "bedroom"): +1,
    ("laundry", "primary_bedroom"): +1,
    ("bedroom", "living_room"): -2,
    ("bedroom", "media_room"): -2,
    ("primary_bedroom", "living_room"): -2,
    ("kids_room", "living_room"): -1,
    # wet rooms cluster (per pair)
    ("full_bath", "full_bath"): +1,
    ("full_bath", "powder"): +1,
    ("full_bath", "laundry"): +1,
}


def adjacency_weight(type_a: str, type_b: str) -> float:
    """Look up an adjacency preference. Symmetric."""
    key = tuple(sorted((type_a, type_b)))
    return ADJACENCY_WEIGHTS.get(key, 0.0)  # type: ignore[arg-type]


# ---------- Cost-function weights (Section 6.3) ----------

@dataclass
class CostWeights:
    """Each term is inspectable and individually tunable."""

    adjacency: float = 1.0
    aspect_ratio: float = 1.0
    zoning: float = 1.0
    daylight: float = 1.5
    area_deviation: float = 1.0
    circulation: float = 2.0
    entry_position: float = 3.0   # entry must touch the boundary
    min_dim_violation: float = 5.0  # heavy: rooms must hit minimums

    # aspect ratio band: comfortable 1:1..1:1.8, hard discomfort past 1:2.5
    aspect_target_min: float = 1.0
    aspect_target_max: float = 1.8
    aspect_hard_max: float = 2.5


DEFAULT_COST_WEIGHTS = CostWeights()


# ---------- Wall / opening / circulation defaults ----------

@dataclass(frozen=True)
class Jurisdiction:
    label: str
    glazing_ratio: float       # window area / floor area for habitable rooms
    bedroom_egress_min_mm: int # min openable window dim for bedroom egress


JURISDICTIONS = {
    "NBC_metric": Jurisdiction("NBC (metric)", 0.10, 760),
    "IRC_imperial": Jurisdiction("IRC (imperial)", 0.08, 610),
}
DEFAULT_JURISDICTION = "NBC_metric"

GRID_MM = 100  # snap grid
EXTERIOR_WALL_MM = 230
INTERIOR_WALL_MM = 115

DOOR_WIDTHS_MM = {
    "entry": 1000,
    "internal": 900,
    "bathroom": 750,
}

CORRIDOR_MIN_WIDTH_MM = 1000
CIRCULATION_TARGET_PCT = 12  # default; agent may override


def catalog_for_palette() -> list[dict]:
    """Catalog entries as plain dicts for the frontend palette."""
    return [
        {
            "type": r.type,
            "label": r.label,
            "zone": r.zone,
            "target_m2": r.target_m2,
            "min_m2": r.min_m2,
            "min_width_m": r.min_width_m,
            "needs_window": r.needs_window,
            "needs_egress": r.needs_egress,
            "needs_exterior_wall": r.needs_exterior_wall,
            "max_count": r.max_count,
        }
        for r in ROOM_CATALOG
    ]
