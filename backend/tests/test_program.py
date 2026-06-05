"""Step 2: tests for boundary + room-program validation."""
from __future__ import annotations

from app.models import Boundary, RoomRequest
from app.program import check_program, expand_room_requests, summarize_program


def test_expand_assigns_unique_ids():
    rooms = [RoomRequest(type="bedroom", count=3), RoomRequest(type="primary_bedroom", count=1)]
    expanded = expand_room_requests(rooms)
    assert [r["id"] for r in expanded] == [
        "bedroom_1",
        "bedroom_2",
        "bedroom_3",
        "primary_bedroom_1",
    ]
    assert [r["label"] for r in expanded] == [
        "Bedroom 1",
        "Bedroom 2",
        "Bedroom 3",
        "Primary Bedroom",
    ]


def test_single_count_drops_numeric_suffix():
    expanded = expand_room_requests([RoomRequest(type="living_room", count=1)])
    assert expanded[0]["label"] == "Living Room"
    assert expanded[0]["id"] == "living_room_1"


def test_unknown_type_raises():
    import pytest

    with pytest.raises(ValueError):
        expand_room_requests([RoomRequest(type="dragon_lair", count=1)])


def test_check_program_happy_path():
    boundary = Boundary(width_mm=12000, depth_mm=10000)  # 120 m^2
    rooms = [
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=2),
        RoomRequest(type="full_bath", count=2),
        RoomRequest(type="foyer", count=1),
    ]
    result = check_program(boundary, rooms)
    assert result.ok, result.errors
    assert result.summary.usable_area_m2 > result.summary.min_required_m2


def test_check_program_too_small():
    boundary = Boundary(width_mm=4000, depth_mm=4000)  # 16 m^2
    rooms = [
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="primary_bedroom", count=1),
    ]
    result = check_program(boundary, rooms)
    assert not result.ok
    assert any("exceed usable area" in e for e in result.errors)


def test_check_program_warns_when_targets_overflow_but_minimums_fit():
    boundary = Boundary(width_mm=12000, depth_mm=10000)  # 120 m^2, usable ~99
    rooms = [
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="family_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="dining_room", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=2),
        RoomRequest(type="full_bath", count=2),
        RoomRequest(type="foyer", count=1),
    ]
    result = check_program(boundary, rooms)
    assert result.ok, result.errors
    assert result.summary.target_total_m2 > result.summary.usable_area_m2
    assert any("scaled down" in w for w in result.warnings)


def test_boundary_too_small():
    boundary = Boundary(width_mm=2500, depth_mm=2500)
    rooms = [RoomRequest(type="bedroom", count=1)]
    result = check_program(boundary, rooms)
    assert not result.ok
    assert any("at least 3.0m" in e for e in result.errors)


def test_summary_areas_consistent():
    boundary = Boundary(width_mm=12000, depth_mm=10000)
    rooms = [RoomRequest(type="bedroom", count=2)]
    summary = summarize_program(boundary, rooms)
    assert summary.boundary_area_m2 == 120
    # Usable < boundary because of wall + circulation allowance.
    assert summary.usable_area_m2 < summary.boundary_area_m2
    assert summary.min_required_m2 == 20  # 2 * 10 m^2 minimum bedrooms
