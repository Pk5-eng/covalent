"""Step 4.2 visual checkpoint: 3-bedroom random tree -> validated plan -> SVG.

This test does what the spec calls for at the end of sub-step 2: render
the layout and run validate.py on it. It also writes the SVG to
backend/render_out/ so we can eyeball it.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.agent.architect import generate_program
from app.engine.assemble import build_leaf_specs, floor_plan_from_rects, program_to_rows
from app.engine.debug_render import save_floor_plan_svg
from app.engine.slicing import InfeasibleLayout, dimension, is_feasible, random_polish
from app.engine.validate import validate_floor_plan
from app.models import Boundary, RoomRequest

RENDER_DIR = Path(__file__).resolve().parent.parent / "render_out"


def _request() -> tuple[Boundary, list[RoomRequest]]:
    boundary = Boundary(width_mm=14000, depth_mm=11000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=3),
        RoomRequest(type="full_bath", count=2),
    ]
    return boundary, rooms


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_feasible_slicing_layout_tiles_and_validates(monkeypatch, seed):
    """Random trees can be infeasible. When one IS feasible, dimensioning
    must produce a layout that tiles the boundary cleanly (validate.py passes).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary, room_reqs = _request()
    program = generate_program(boundary, room_reqs)
    rows = program_to_rows(program.rooms)
    specs = build_leaf_specs(rows, boundary.width_mm, boundary.depth_mm)

    rng = random.Random(seed)
    leaves = [r["id"] for r in rows]

    # Take the first feasible random tree (caps to avoid pathological seeds).
    expr = None
    for _ in range(200):
        candidate = random_polish(leaves, rng)
        if is_feasible(candidate, boundary.width_mm, boundary.depth_mm, specs):
            expr = candidate
            break
    if expr is None:
        pytest.skip(f"no feasible random tree for seed {seed}")

    rects = dimension(expr, boundary.width_mm, boundary.depth_mm, specs)
    plan = floor_plan_from_rects(boundary, rows, rects)

    validate_floor_plan(plan)

    out = save_floor_plan_svg(
        plan,
        RENDER_DIR / f"step4_checkpoint1_seed{seed}.svg",
        title=f"Step 4.2 random feasible tree · seed {seed} · {boundary.width_mm}x{boundary.depth_mm}",
    )
    assert out.exists() and out.stat().st_size > 0


def test_infeasible_layout_raises(monkeypatch):
    """A pathological tree (all rooms side-by-side in V) on a narrow boundary."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary, room_reqs = _request()
    program = generate_program(boundary, room_reqs)
    rows = program_to_rows(program.rooms)
    specs = build_leaf_specs(rows, boundary.width_mm, boundary.depth_mm)
    # Force every cut V: all rooms side-by-side; sum of min widths exceeds 14m.
    leaves = [r["id"] for r in rows]
    expr: list = [leaves[0]]
    for lid in leaves[1:]:
        expr.extend([lid, "V"])
    with pytest.raises(InfeasibleLayout):
        dimension(expr, boundary.width_mm, boundary.depth_mm, specs)
