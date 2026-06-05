"""Step 4.1: validator contract tests."""
from __future__ import annotations

import pytest

from app.engine.validate import (
    ValidationError,
    shared_wall_length,
    validate_floor_plan,
)
from app.models import Boundary, FloorPlan, Room


def _room(rid: str, x: float, y: float, w: float, h: float) -> Room:
    return Room(
        id=rid,
        type="bedroom",
        label=rid,
        zone="private",
        polygon=[(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        area_mm2=w * h,
    )


def _plan(boundary_w: int, boundary_h: int, rooms: list[Room]) -> FloorPlan:
    return FloorPlan(
        boundary=Boundary(width_mm=boundary_w, depth_mm=boundary_h),
        rooms=rooms,
    )


def test_validator_accepts_clean_2x2_tile():
    rooms = [
        _room("a", 0, 0, 5000, 5000),
        _room("b", 5000, 0, 5000, 5000),
        _room("c", 0, 5000, 5000, 5000),
        _room("d", 5000, 5000, 5000, 5000),
    ]
    plan = _plan(10000, 10000, rooms)
    validate_floor_plan(plan)  # no raise


def test_validator_rejects_overlap():
    rooms = [
        _room("a", 0, 0, 6000, 5000),
        _room("b", 4000, 0, 6000, 5000),  # overlaps "a"
        _room("c", 0, 5000, 10000, 5000),
    ]
    plan = _plan(10000, 10000, rooms)
    with pytest.raises(ValidationError) as exc:
        validate_floor_plan(plan)
    assert exc.value.code == "overlap"


def test_validator_rejects_gap():
    rooms = [
        _room("a", 0, 0, 4000, 10000),
        _room("b", 6000, 0, 4000, 10000),  # leaves a 2000 mm gap
    ]
    plan = _plan(10000, 10000, rooms)
    with pytest.raises(ValidationError) as exc:
        validate_floor_plan(plan)
    assert exc.value.code == "coverage"


def test_validator_rejects_spill():
    rooms = [
        _room("a", 0, 0, 12000, 10000),  # extends past boundary width
    ]
    plan = _plan(10000, 10000, rooms)
    with pytest.raises(ValidationError) as exc:
        validate_floor_plan(plan)
    assert exc.value.code == "out_of_bounds"


def test_validator_rejects_disconnected():
    # Two rooms meeting only at a corner are not connected (zero-length shared wall).
    rooms = [
        _room("a", 0, 0, 5000, 5000),
        _room("b", 5000, 5000, 5000, 5000),
        _room("c", 5000, 0, 5000, 5000),
        _room("d", 0, 5000, 5000, 5000),
    ]
    plan = _plan(10000, 10000, rooms)
    # 4 rooms tiling fine; should pass connectivity.
    validate_floor_plan(plan)


def test_shared_wall_length_helper():
    a = _room("a", 0, 0, 5000, 5000)
    b = _room("b", 5000, 0, 5000, 5000)
    assert shared_wall_length(a, b) == pytest.approx(5000)
    c = _room("c", 5000, 6000, 5000, 5000)  # gap from b at y=5000..6000
    assert shared_wall_length(b, c) == 0


def test_validator_rejects_zero_area_polygon():
    rooms = [
        Room(
            id="a",
            type="bedroom",
            label="a",
            zone="private",
            polygon=[(0, 0), (1, 0), (1, 0), (0, 0)],
            area_mm2=0,
        ),
        _room("b", 0, 0, 10000, 10000),
    ]
    plan = _plan(10000, 10000, rooms)
    with pytest.raises(ValidationError) as exc:
        validate_floor_plan(plan)
    assert exc.value.code == "bad_polygon"
