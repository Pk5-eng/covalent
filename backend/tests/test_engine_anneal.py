"""Step 4.4: simulated annealing tests + second visual checkpoint."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.agent.architect import generate_program
from app.engine.anneal import (
    AnnealConfig,
    anneal,
    move_complement_chain,
    move_swap_operand_operator,
    move_swap_operands,
)
from app.engine.assemble import build_leaf_specs, floor_plan_from_rects, program_to_rows
from app.engine.cost import evaluate_cost
from app.engine.debug_render import save_floor_plan_svg
from app.engine.slicing import (
    is_feasible,
    is_normalized,
    random_polish,
)
from app.engine.validate import validate_floor_plan
from app.models import Boundary, RoomRequest

RENDER_DIR = Path(__file__).resolve().parent.parent / "render_out"


def _request() -> tuple[Boundary, list[RoomRequest]]:
    boundary = Boundary(width_mm=14000, depth_mm=11000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="dining_room", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=3),
        RoomRequest(type="full_bath", count=2),
        RoomRequest(type="powder", count=1),
    ]
    return boundary, rooms


# ---------- moves ----------


def test_move_swap_operands_preserves_normalization():
    expr = ["a", "b", "V", "c", "H"]
    rng = random.Random(0)
    out = move_swap_operands(expr, rng)
    assert out is not None
    assert is_normalized(out)


def test_move_complement_chain_flips_at_least_one_operator():
    expr = ["a", "b", "V", "c", "H"]
    out = move_complement_chain(expr, random.Random(0))
    assert out is not None
    assert is_normalized(out)
    assert out != expr


def test_move_swap_operand_operator_returns_valid_polish():
    rng = random.Random(0)
    expr = random_polish(["a", "b", "c", "d", "e"], rng)
    # Attempt several times since some configurations have no valid swap.
    seen_valid = False
    for _ in range(20):
        out = move_swap_operand_operator(expr, rng)
        if out is None:
            continue
        seen_valid = True
        assert is_normalized(out)
        # Polish-expression validity:
        operands = sum(1 for t in out if t not in ("H", "V"))
        operators = sum(1 for t in out if t in ("H", "V"))
        assert operands == operators + 1
    assert seen_valid


# ---------- annealing ----------


def test_annealing_does_not_worsen_cost(monkeypatch):
    """Best-of-restarts should beat a random feasible tree on average."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary, room_reqs = _request()
    program = generate_program(boundary, room_reqs)
    rows = program_to_rows(program.rooms)
    specs = build_leaf_specs(rows, boundary.width_mm, boundary.depth_mm)

    rng = random.Random(11)
    leaves = [r["id"] for r in rows]
    expr = None
    for _ in range(200):
        candidate = random_polish(leaves, rng)
        if is_feasible(candidate, boundary.width_mm, boundary.depth_mm, specs):
            expr = candidate
            break
    assert expr is not None

    from app.engine.slicing import dimension
    rects0 = dimension(expr, boundary.width_mm, boundary.depth_mm, specs)
    baseline_cost = evaluate_cost(
        rects0, rows, boundary.width_mm, boundary.depth_mm,
        entry_room_id=program.circulation.entry_room_id,
    ).weighted_total

    result = anneal(
        leaves,
        boundary.width_mm,
        boundary.depth_mm,
        specs,
        rows,
        program.circulation.entry_room_id,
        config=AnnealConfig(iterations=800, restarts=2, seed=11),
    )
    assert result.cost <= baseline_cost + 1e-3


def test_annealing_result_validates_and_renders(monkeypatch):
    """Step 4.4 visual checkpoint: best-of-restarts produces a valid plan."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    boundary, room_reqs = _request()
    program = generate_program(boundary, room_reqs)
    rows = program_to_rows(program.rooms)
    specs = build_leaf_specs(rows, boundary.width_mm, boundary.depth_mm)
    leaves = [r["id"] for r in rows]

    result = anneal(
        leaves,
        boundary.width_mm,
        boundary.depth_mm,
        specs,
        rows,
        program.circulation.entry_room_id,
        config=AnnealConfig(iterations=1200, restarts=3, seed=7),
    )

    plan = floor_plan_from_rects(boundary, rows, result.rects)
    validate_floor_plan(plan)

    out = save_floor_plan_svg(
        plan,
        RENDER_DIR / "step4_checkpoint2_annealed.svg",
        title=(
            f"Step 4.4 annealed plan · cost {result.cost:.2f} · "
            f"{boundary.width_mm}x{boundary.depth_mm}"
        ),
    )
    assert out.exists() and out.stat().st_size > 0
