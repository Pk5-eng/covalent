"""Step 4.5: finishing passes (snap, walls, openings) + full pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.architect import generate_program
from app.engine.anneal import AnnealConfig
from app.engine.assemble import program_to_rows  # noqa: F401
from app.engine.debug_render import save_floor_plan_svg
from app.engine.finishing import snap_rects_to_grid
from app.engine.pipeline import build_floor_plan
from app.engine.slicing import Rect
from app.engine.validate import validate_floor_plan
from app.models import Boundary, RoomRequest

# Light annealing config for tests; production uses the default.
FAST_ANNEAL = AnnealConfig(iterations=400, restarts=2, seed=0)

RENDER_DIR = Path(__file__).resolve().parent.parent / "render_out"


def test_snap_preserves_adjacency():
    """Cluster-aligned snapping must keep shared edges shared."""
    rects = {
        "a": Rect(0, 0, 4053, 4012),  # off-grid edges
        "b": Rect(4053, 0, 3947, 4012),
        "c": Rect(0, 4012, 8000, 3988),
    }
    out = snap_rects_to_grid(rects, 8000, 8000, grid=100)
    # Boundary edges land on 0 and 8000 exactly.
    assert out["a"].x == 0
    assert out["a"].y == 0
    # Shared x-line at ~4053 snaps to the same value in both.
    assert out["a"].x + out["a"].w == out["b"].x
    assert out["a"].y + out["a"].h == out["c"].y
    # Total tiling preserved.
    assert out["a"].x + out["a"].w + out["b"].w == 8000
    assert out["c"].y + out["c"].h == 8000


def test_pipeline_end_to_end_validates_and_has_walls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary = Boundary(width_mm=14000, depth_mm=11000)
    room_reqs = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="dining_room", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=3),
        RoomRequest(type="full_bath", count=2),
    ]
    program = generate_program(boundary, room_reqs)
    plan, diag = build_floor_plan(
        boundary, program, anneal_config=AnnealConfig(iterations=800, restarts=2, seed=42)
    )

    # Validate passes (assemble.finish_floor_plan already calls it).
    validate_floor_plan(plan)

    assert plan.walls, "walls were not generated"
    assert plan.openings, "openings were not generated"
    # Mix of exterior and interior walls.
    assert any(w.type == "exterior" for w in plan.walls)
    assert any(w.type == "interior" for w in plan.walls)
    # Doors only on interior walls, windows only on exterior walls.
    by_wall = {w.id: w for w in plan.walls}
    for op in plan.openings:
        wall = by_wall[op.wall_id]
        if op.kind == "door":
            assert wall.type == "interior", f"door {op.id} on exterior wall"
        else:
            assert wall.type == "exterior", f"window {op.id} on interior wall"

    # Render the final visual.
    out = save_floor_plan_svg(
        plan,
        RENDER_DIR / "step4_checkpoint3_finished.svg",
        title=f"Step 4.5 finished plan · cost {diag.cost:.2f}",
    )
    assert out.exists() and out.stat().st_size > 0


def test_pipeline_validates_for_multiple_seeds(monkeypatch):
    """Multiple seeds must all produce valid finished plans."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary = Boundary(width_mm=12000, depth_mm=10000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=2),
        RoomRequest(type="full_bath", count=2),
    ]
    program = generate_program(boundary, rooms)
    for seed in [1, 2, 3]:
        plan, _ = build_floor_plan(
            boundary, program, anneal_config=AnnealConfig(iterations=400, restarts=1, seed=seed)
        )
        validate_floor_plan(plan)


def test_resize_one_room_keeps_topology(monkeypatch):
    """Editing a single room's target should re-anneal but stay valid."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary = Boundary(width_mm=12000, depth_mm=10000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=1),
        RoomRequest(type="full_bath", count=1),
    ]
    program = generate_program(boundary, rooms)
    plan, _ = build_floor_plan(boundary, program, anneal_config=FAST_ANNEAL)

    from app.engine.pipeline import resize_room

    living = next(r for r in plan.rooms if r.type == "living_room")
    new_plan, _ = resize_room(
        plan, program, living.id, new_target_area_m2=28, anneal_config=FAST_ANNEAL,
    )
    validate_floor_plan(new_plan)
    # The living room target should now reflect the change.
    new_living_area = next(r for r in new_plan.rooms if r.type == "living_room").area_mm2
    old_living_area = living.area_mm2
    assert new_living_area != old_living_area
