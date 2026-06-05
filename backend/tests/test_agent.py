"""Step 3 tests: architect agent schema, fallback, 3-bedroom case."""
from __future__ import annotations

import json

import pytest

from app.agent.architect import generate_program
from app.agent.schema import (
    AgentOutputError,
    clamp_to_usable_area,
    parse_program_json,
    validate_program_dict,
)
from app.models import Boundary, RoomRequest


# ---------- Schema parser ----------


def _good_payload() -> dict:
    return {
        "units": "mm",
        "global": {
            "circulation_target_pct": 12,
            "group_wet_rooms": True,
            "primary_entry_side": "south",
        },
        "rooms": [
            {
                "id": "foyer_1",
                "type": "foyer",
                "label": "Foyer",
                "zone": "public",
                "target_area_m2": 4,
                "min_width_m": 1.5,
                "priority": 1,
                "needs_exterior_wall": False,
                "needs_window": False,
                "needs_egress": False,
                "adjacent_to": ["living_room_1"],
                "not_adjacent_to": [],
            },
            {
                "id": "living_room_1",
                "type": "living_room",
                "label": "Living Room",
                "zone": "public",
                "target_area_m2": 22,
                "min_width_m": 3.5,
                "priority": 1,
                "needs_exterior_wall": True,
                "needs_window": True,
                "needs_egress": False,
                "adjacent_to": ["foyer_1"],
                "not_adjacent_to": [],
            },
        ],
        "circulation": {"entry_room_id": "foyer_1", "notes": "ok"},
    }


def test_parse_strict_json_accepts_clean_payload():
    program = parse_program_json(json.dumps(_good_payload()))
    assert len(program.rooms) == 2
    assert program.circulation.entry_room_id == "foyer_1"
    assert program.global_.circulation_target_pct == 12


def test_parse_tolerates_markdown_fence_but_not_prose():
    raw = "```json\n" + json.dumps(_good_payload()) + "\n```"
    program = parse_program_json(raw)
    assert program.rooms[0].id == "foyer_1"


def test_parser_rejects_prose():
    raw = "Here is your program: " + json.dumps(_good_payload())
    with pytest.raises(AgentOutputError):
        parse_program_json(raw)


def test_parser_rejects_coordinates():
    payload = _good_payload()
    payload["rooms"][0]["polygon"] = [[0, 0], [1, 0], [1, 1], [0, 1]]
    with pytest.raises(AgentOutputError, match="coordinates"):
        validate_program_dict(payload)


def test_parser_rejects_dangling_adjacency_ref():
    payload = _good_payload()
    payload["rooms"][0]["adjacent_to"] = ["does_not_exist"]
    with pytest.raises(AgentOutputError, match="unknown id"):
        validate_program_dict(payload)


def test_parser_rejects_self_adjacency():
    payload = _good_payload()
    payload["rooms"][0]["adjacent_to"] = ["foyer_1"]
    with pytest.raises(AgentOutputError, match="itself"):
        validate_program_dict(payload)


def test_parser_rejects_duplicate_ids():
    payload = _good_payload()
    payload["rooms"][1]["id"] = "foyer_1"
    payload["circulation"]["entry_room_id"] = "foyer_1"
    with pytest.raises(AgentOutputError, match="unique"):
        validate_program_dict(payload)


def test_parser_rejects_unknown_room_type():
    payload = _good_payload()
    payload["rooms"][0]["type"] = "wine_cellar"
    with pytest.raises(AgentOutputError, match="unknown room type"):
        validate_program_dict(payload)


def test_parser_rejects_missing_entry_room():
    payload = _good_payload()
    payload["circulation"]["entry_room_id"] = "ghost_1"
    with pytest.raises(AgentOutputError, match="entry_room_id"):
        validate_program_dict(payload)


# ---------- Clamping ----------


def test_clamp_scales_targets_toward_minimums():
    program = parse_program_json(json.dumps(_good_payload()))
    # Generous usable that still forces scaling (26 -> ~18).
    clamped = clamp_to_usable_area(program, usable_area_m2=18)
    total = sum(r.target_area_m2 for r in clamped.rooms)
    assert total <= 19  # tight to target, allowing rounding
    # Per-room minimums respected (foyer min 2, living min 14).
    by_type = {r.type: r.target_area_m2 for r in clamped.rooms}
    assert by_type["foyer"] >= 2
    assert by_type["living_room"] >= 14
    assert "clamped" in clamped.circulation.notes.lower()


def test_clamp_floors_at_minimums_when_usable_is_too_small():
    """If even the minimums don't fit, clamp stops at the per-room floors
    rather than silently lying. The engine catches infeasibility downstream.
    """
    program = parse_program_json(json.dumps(_good_payload()))
    clamped = clamp_to_usable_area(program, usable_area_m2=5)  # impossible
    total = sum(r.target_area_m2 for r in clamped.rooms)
    # foyer min 2 + living min 14 = 16
    assert total >= 16


def test_clamp_no_op_when_within_budget():
    program = parse_program_json(json.dumps(_good_payload()))
    clamped = clamp_to_usable_area(program, usable_area_m2=200)
    totals = [r.target_area_m2 for r in clamped.rooms]
    originals = [r.target_area_m2 for r in program.rooms]
    assert totals == originals


# ---------- 3-bedroom fallback (no API key) ----------


def test_three_bedroom_fallback(monkeypatch):
    """Spec requires a 3-bedroom test. Run the deterministic fallback."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary = Boundary(width_mm=14000, depth_mm=11000)  # 154 m^2
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="dining_room", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=3),
        RoomRequest(type="full_bath", count=2),
        RoomRequest(type="powder", count=1),
        RoomRequest(type="laundry", count=1),
    ]
    program = generate_program(boundary, rooms)

    ids = {r.id for r in program.rooms}
    # 3 bedrooms + 1 primary
    assert sum(1 for r in program.rooms if r.type == "bedroom") == 3
    assert sum(1 for r in program.rooms if r.type == "primary_bedroom") == 1

    # All adjacency references must resolve.
    for r in program.rooms:
        for ref in r.adjacent_to + r.not_adjacent_to:
            assert ref in ids
            assert ref != r.id

    # Entry exists.
    assert program.circulation.entry_room_id in ids
    # Primary paired with a bath.
    primary = next(r for r in program.rooms if r.type == "primary_bedroom")
    assert any(
        next(rr for rr in program.rooms if rr.id == ref).type == "full_bath"
        for ref in primary.adjacent_to
    )
    # Kitchen near dining + living.
    kitchen = next(r for r in program.rooms if r.type == "kitchen")
    neighbour_types = {
        next(rr for rr in program.rooms if rr.id == ref).type for ref in kitchen.adjacent_to
    }
    assert "dining_room" in neighbour_types
    assert "living_room" in neighbour_types
    # Bedroom-living negative adjacency present.
    bed = next(r for r in program.rooms if r.type == "bedroom")
    living = next(r for r in program.rooms if r.type == "living_room")
    assert living.id in bed.not_adjacent_to

    # Targets respect usable area after clamping.
    total = sum(r.target_area_m2 for r in program.rooms)
    boundary_area = boundary.width_mm * boundary.depth_mm / 1_000_000
    assert total <= boundary_area


def test_fallback_uses_foyer_as_entry(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary = Boundary(width_mm=12000, depth_mm=10000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="bedroom", count=1),
        RoomRequest(type="full_bath", count=1),
    ]
    program = generate_program(boundary, rooms)
    assert program.circulation.entry_room_id == "foyer_1"


def test_generate_program_rejects_empty():
    with pytest.raises(ValueError, match="no rooms"):
        generate_program(Boundary(width_mm=12000, depth_mm=10000), [])
