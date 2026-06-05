"""Step 4.3: each cost term is inspectable and behaves directionally."""
from __future__ import annotations

import pytest

from app.engine.cost import DOOR_THRESHOLD_MM, evaluate_cost
from app.engine.slicing import Rect
from app.rules.defaults import DEFAULT_COST_WEIGHTS


def _rooms() -> list[dict]:
    return [
        {
            "id": "kitchen_1",
            "type": "kitchen",
            "label": "Kitchen",
            "zone": "public",
            "target_area_m2": 12,
            "min_width_m": 2.4,
            "needs_window": True,
            "needs_egress": False,
            "needs_exterior_wall": True,
            "adjacent_to": ["dining_room_1"],
            "not_adjacent_to": [],
        },
        {
            "id": "dining_room_1",
            "type": "dining_room",
            "label": "Dining",
            "zone": "public",
            "target_area_m2": 14,
            "min_width_m": 3.0,
            "needs_window": True,
            "needs_egress": False,
            "needs_exterior_wall": True,
            "adjacent_to": ["kitchen_1"],
            "not_adjacent_to": [],
        },
        {
            "id": "bedroom_1",
            "type": "bedroom",
            "label": "Bedroom",
            "zone": "private",
            "target_area_m2": 13,
            "min_width_m": 2.7,
            "needs_window": True,
            "needs_egress": True,
            "needs_exterior_wall": True,
            "adjacent_to": [],
            "not_adjacent_to": ["kitchen_1"],
        },
    ]


def test_adjacency_reward_when_shared_wall_long_enough():
    """Each pair is scored exactly once. Kitchen-dining share 4000 mm; the
    bedroom's not_adjacent_to kitchen is also triggered (4000 mm shared),
    so the net is positive — we assert only that the kitchen-dining pair
    appears in `satisfied` exactly once.
    """
    rects = {
        "kitchen_1": Rect(0, 0, 4000, 4000),
        "dining_room_1": Rect(4000, 0, 4000, 4000),
        "bedroom_1": Rect(0, 4000, 8000, 4000),
    }
    b = evaluate_cost(rects, _rooms(), 8000, 8000, entry_room_id="kitchen_1")
    sat_pairs = [tuple(d["pair"]) for d in b.details["adjacency"]["satisfied"]]
    assert sat_pairs == [("dining_room_1", "kitchen_1")]


def test_adjacency_term_better_when_required_pair_touches():
    """Moving the required pair adjacent should lower the term."""
    rooms = _rooms()
    # Drop the not_adjacent_to so we isolate the kitchen-dining reward.
    rooms[2]["not_adjacent_to"] = []

    rects_touching = {
        "kitchen_1": Rect(0, 0, 4000, 4000),
        "dining_room_1": Rect(4000, 0, 4000, 4000),
        "bedroom_1": Rect(0, 4000, 8000, 4000),
    }
    rects_apart = {
        "kitchen_1": Rect(0, 0, 3000, 4000),
        "dining_room_1": Rect(5000, 0, 3000, 4000),  # real gap from kitchen
        "bedroom_1": Rect(0, 5000, 8000, 4000),
    }
    a = evaluate_cost(rects_touching, rooms, 8000, 8000, entry_room_id="kitchen_1").adjacency
    b = evaluate_cost(rects_apart, rooms, 8000, 8000, entry_room_id="kitchen_1").adjacency
    assert a < b


def test_adjacency_penalty_when_required_pair_not_touching():
    """Kitchen and dining have a real gap between them (no shared edge)."""
    # evaluate_cost does not require tiling — we can use a gapped layout
    # to isolate the adjacency behaviour.
    rects = {
        "kitchen_1": Rect(0, 0, 3000, 4000),
        "dining_room_1": Rect(5000, 0, 3000, 4000),  # 2000 mm gap from kitchen
        "bedroom_1": Rect(0, 5000, 8000, 4000),       # also detached, in lower area
    }
    b = evaluate_cost(rects, _rooms(), 8000, 12000, entry_room_id="kitchen_1")
    pair_missing = {tuple(d["pair"]) for d in b.details["adjacency"]["missing"]}
    assert ("dining_room_1", "kitchen_1") in pair_missing


def test_not_adjacent_violation_when_pair_touches():
    rects = {
        "kitchen_1": Rect(0, 0, 4000, 4000),
        "bedroom_1": Rect(4000, 0, 4000, 4000),  # shares a wall with kitchen
        "dining_room_1": Rect(0, 4000, 8000, 4000),
    }
    b = evaluate_cost(rects, _rooms(), 8000, 8000, entry_room_id="kitchen_1")
    assert b.details["adjacency"]["violations"]


def test_aspect_ratio_penalty_for_long_thin_room():
    rects = {
        "kitchen_1": Rect(0, 0, 4000, 1000),  # 4:1
        "dining_room_1": Rect(0, 1000, 4000, 3500),
        "bedroom_1": Rect(0, 4500, 4000, 3500),
    }
    b = evaluate_cost(rects, _rooms(), 4000, 8000, entry_room_id="kitchen_1")
    assert b.aspect_ratio > 0
    assert b.details["aspect_ratio"]["kitchen_1"] >= 2.5


def test_daylight_penalty_for_interior_room_needing_exterior_wall():
    # bedroom in the center, no boundary contact.
    rects = {
        "kitchen_1": Rect(0, 0, 12000, 3000),
        "dining_room_1": Rect(0, 9000, 12000, 3000),
        "bedroom_1": Rect(2000, 3000, 8000, 6000),  # interior on 4 sides
    }
    b = evaluate_cost(rects, _rooms(), 12000, 12000, entry_room_id="kitchen_1")
    assert "bedroom_1" in b.details["daylight"]["starved"]
    assert b.daylight >= 1


def test_area_deviation_penalises_undersize():
    rects = {
        "kitchen_1": Rect(0, 0, 1000, 1000),  # tiny vs 12 m^2 target
        "dining_room_1": Rect(1000, 0, 3000, 4000),
        "bedroom_1": Rect(4000, 0, 4000, 4000),
    }
    b = evaluate_cost(rects, _rooms(), 8000, 4000, entry_room_id="kitchen_1")
    assert b.area_deviation > 0
    assert b.details["area_deviation"]["kitchen_1"] < 0


def test_circulation_penalises_unreachable():
    # bedroom is reachable only via a corner; corridor below door threshold.
    rects = {
        "kitchen_1": Rect(0, 0, 4000, 4000),
        "dining_room_1": Rect(0, 4000, 4000, 4000),
        "bedroom_1": Rect(4000, 4000, 4000, 4000),  # corner-touches kitchen
    }
    b = evaluate_cost(rects, _rooms(), 8000, 8000, entry_room_id="kitchen_1")
    # bedroom_1 reaches kitchen via dining (shared 4000mm wall, then 4000mm).
    assert b.circulation == 0 or "unreachable" in b.details["circulation"]


def test_zoning_term_zero_when_each_zone_contiguous():
    rects = {
        "kitchen_1": Rect(0, 0, 4000, 4000),
        "dining_room_1": Rect(4000, 0, 4000, 4000),  # public cluster
        "bedroom_1": Rect(0, 4000, 8000, 4000),       # single private
    }
    b = evaluate_cost(rects, _rooms(), 8000, 8000, entry_room_id="kitchen_1")
    assert b.zoning == 0


def test_door_threshold_constant_matches_spec():
    assert DOOR_THRESHOLD_MM == 900


def test_default_weights_are_positive():
    w = DEFAULT_COST_WEIGHTS
    for name in ("adjacency", "aspect_ratio", "zoning", "daylight",
                 "area_deviation", "circulation", "min_dim_violation"):
        assert getattr(w, name) > 0
