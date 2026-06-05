"""End-to-end engine pipeline: program -> annealed layout -> finished plan."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.engine.anneal import AnnealConfig, AnnealResult, anneal
from app.engine.assemble import build_leaf_specs, program_to_rows
from app.engine.cost import CostBreakdown
from app.engine.finishing import finish_floor_plan
from app.engine.slicing import (
    InfeasibleLayout,
    dimension,
    is_feasible,
    random_polish,
)
from app.models import Boundary, FloorPlan, Program
from app.rules.defaults import DEFAULT_COST_WEIGHTS

logger = logging.getLogger("covalent.engine")


@dataclass
class LayoutDiagnostics:
    cost: float
    breakdown: CostBreakdown
    expr: list
    iterations: int
    accepted: int
    restarts: int


def build_floor_plan(
    boundary: Boundary,
    program: Program,
    *,
    seed: int | None = None,
    anneal_config: AnnealConfig | None = None,
) -> tuple[FloorPlan, LayoutDiagnostics]:
    """Run annealing + finishing for a Program, return (FloorPlan, diagnostics)."""
    program_rows = program_to_rows(program.rooms)
    if not program_rows:
        raise ValueError("program has no rooms")

    leaves = [r["id"] for r in program_rows]
    specs = build_leaf_specs(program_rows, boundary.width_mm, boundary.depth_mm)

    config = anneal_config or AnnealConfig(seed=seed if seed is not None else AnnealConfig().seed)
    if seed is not None and config.seed is None:
        config = AnnealConfig(
            iterations=config.iterations,
            restarts=config.restarts,
            cool_factor=config.cool_factor,
            start_temp_samples=config.start_temp_samples,
            min_temp=config.min_temp,
            seed=seed,
        )

    try:
        result = anneal(
            leaves,
            boundary.width_mm,
            boundary.depth_mm,
            specs,
            program_rows,
            program.circulation.entry_room_id,
            weights=DEFAULT_COST_WEIGHTS,
            config=config,
        )
    except InfeasibleLayout as e:
        raise ValueError(f"layout infeasible: {e}") from e

    adjacency_pairs = []
    for r in program_rows:
        for ref in r.get("adjacent_to", []):
            adjacency_pairs.append((r["id"], ref))

    plan = finish_floor_plan(
        boundary,
        result.rects,
        program_rows,
        adjacency_pairs,
    )

    diag = LayoutDiagnostics(
        cost=result.cost,
        breakdown=result.breakdown,
        expr=result.expr,
        iterations=result.iterations,
        accepted=result.accepted,
        restarts=result.restarts,
    )
    logger.info(
        "engine pipeline: cost=%.3f iters=%d accepted=%d restarts=%d",
        diag.cost,
        diag.iterations,
        diag.accepted,
        diag.restarts,
    )
    return plan, diag


def resize_room(
    plan: FloorPlan,
    program: Program,
    room_id: str,
    new_target_area_m2: float,
    *,
    anneal_config: AnnealConfig | None = None,
) -> tuple[FloorPlan, LayoutDiagnostics]:
    """Edit operation: change one room's target area, re-anneal, re-finish.

    Topology stays put because we re-use the annealing path from the same
    program, but with the updated target. Requires the program so we can
    rebuild the leaf specs from the same room set.
    """
    target_room = next((r for r in program.rooms if r.id == room_id), None)
    if target_room is None:
        raise ValueError(f"unknown room id: {room_id}")

    new_program = program.model_copy(
        update={
            "rooms": [
                r if r.id != room_id else r.model_copy(update={"target_area_m2": new_target_area_m2})
                for r in program.rooms
            ]
        }
    )
    return build_floor_plan(plan.boundary, new_program, anneal_config=anneal_config)


# Convenience used by tests/scripts that already have the expression.
def dimension_with_expr(
    expr: list,
    boundary: Boundary,
    program: Program,
) -> tuple[FloorPlan, LayoutDiagnostics]:
    rows = program_to_rows(program.rooms)
    specs = build_leaf_specs(rows, boundary.width_mm, boundary.depth_mm)
    if not is_feasible(expr, boundary.width_mm, boundary.depth_mm, specs):
        raise InfeasibleLayout("expression not feasible for this boundary")
    rects = dimension(expr, boundary.width_mm, boundary.depth_mm, specs)
    adjacency_pairs = [(r["id"], ref) for r in rows for ref in r.get("adjacent_to", [])]
    plan = finish_floor_plan(boundary, rects, rows, adjacency_pairs)
    return plan, LayoutDiagnostics(
        cost=0.0,
        breakdown=CostBreakdown(),
        expr=expr,
        iterations=0,
        accepted=0,
        restarts=0,
    )


__all__ = [
    "build_floor_plan",
    "dimension_with_expr",
    "LayoutDiagnostics",
    "resize_room",
]
