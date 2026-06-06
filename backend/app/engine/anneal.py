"""Simulated annealing on the slicing tree (Step 4.4 of the spec).

Three Polish-expression moves (Wong-Liu):
    M1  swap two adjacent operands
    M2  complement a chain of operators (flip H<->V on a maximal run)
    M3  swap an adjacent operand and operator (only when normalization is
        preserved and the balloting property still holds)

Geometric cooling. Start temperature derived from the average uphill
delta of random moves. Multi-restart loop keeps the lowest-cost layout.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from app.engine.cost import CostBreakdown, evaluate_cost
from app.engine.slicing import (
    InfeasibleLayout,
    LeafSpec,
    Token,
    dimension,
    is_feasible,
    is_normalized,
    is_operator,
    random_polish,
)
from app.rules.defaults import CostWeights, DEFAULT_COST_WEIGHTS


@dataclass
class AnnealResult:
    expr: list[Token]
    rects: dict
    cost: float
    breakdown: CostBreakdown
    iterations: int
    accepted: int
    restarts: int

    def __repr__(self) -> str:
        return (
            f"AnnealResult(cost={self.cost:.3f}, iters={self.iterations}, "
            f"accepted={self.accepted}, restarts={self.restarts})"
        )


@dataclass
class AnnealConfig:
    iterations: int = 4000
    restarts: int = 4
    cool_factor: float = 0.995
    start_temp_samples: int = 60
    min_temp: float = 1e-4
    seed: int | None = None


# ----------------------------------------------------------------------
# Moves
# ----------------------------------------------------------------------


def _operand_positions(expr: list[Token]) -> list[int]:
    return [i for i, t in enumerate(expr) if not is_operator(t)]


def _operator_positions(expr: list[Token]) -> list[int]:
    return [i for i, t in enumerate(expr) if is_operator(t)]


def move_swap_operands(expr: list[Token], rng: random.Random) -> list[Token] | None:
    """M1: swap two adjacent operands (with nothing between, or with
    operators between but still adjacent in operand-order).
    """
    positions = _operand_positions(expr)
    if len(positions) < 2:
        return None
    i = rng.randrange(len(positions) - 1)
    a, b = positions[i], positions[i + 1]
    new = expr.copy()
    new[a], new[b] = new[b], new[a]
    return new if is_normalized(new) else None


def move_complement_chain(expr: list[Token], rng: random.Random) -> list[Token] | None:
    """M2: flip a maximal run of operators between two operands."""
    positions = _operator_positions(expr)
    if not positions:
        return None
    # Group consecutive operator indices into runs.
    runs: list[list[int]] = []
    current: list[int] = []
    for p in positions:
        if current and p == current[-1] + 1:
            current.append(p)
        else:
            if current:
                runs.append(current)
            current = [p]
    if current:
        runs.append(current)
    run = rng.choice(runs)
    new = expr.copy()
    for idx in run:
        new[idx] = "H" if new[idx] == "V" else "V"
    return new if is_normalized(new) else None


def move_swap_operand_operator(expr: list[Token], rng: random.Random) -> list[Token] | None:
    """M3: swap an operand with an adjacent operator. Preserves the Polish
    property only when (a) the swap stays normalized and (b) the
    "balloting" invariant holds: at every prefix, operand count exceeds
    operator count by at least one.
    """
    candidates: list[int] = []
    for i in range(len(expr) - 1):
        a, b = expr[i], expr[i + 1]
        if is_operator(a) ^ is_operator(b):  # exactly one is an operator
            candidates.append(i)
    if not candidates:
        return None

    rng.shuffle(candidates)
    for i in candidates:
        new = expr.copy()
        new[i], new[i + 1] = new[i + 1], new[i]
        if not is_normalized(new):
            continue
        if not _balloting_property(new):
            continue
        return new
    return None


def _balloting_property(expr: list[Token]) -> bool:
    """A Polish expression is valid iff every prefix has strictly more
    operands than operators, and the final counts satisfy
    operands == operators + 1.
    """
    operands = 0
    operators = 0
    for t in expr:
        if is_operator(t):
            operators += 1
        else:
            operands += 1
        if operands <= operators:
            return False
    return operands == operators + 1


# ----------------------------------------------------------------------
# Annealing loop
# ----------------------------------------------------------------------


MOVES = (move_swap_operands, move_complement_chain, move_swap_operand_operator)


def _propose(expr: list[Token], rng: random.Random, attempts: int = 12) -> list[Token] | None:
    """Try moves in random order until one returns a valid expression."""
    for _ in range(attempts):
        move = rng.choice(MOVES)
        candidate = move(expr, rng)
        if candidate is not None:
            return candidate
    return None


def _cost_of(
    expr: list[Token],
    boundary_w: float,
    boundary_h: float,
    leaf_specs: dict[str, LeafSpec],
    program_rooms: list[dict],
    entry_room_id: str | None,
    weights: CostWeights,
    primary_entry_side: str = "south",
) -> tuple[float, dict, CostBreakdown] | None:
    """Return (cost, rects, breakdown) for `expr`, or None if infeasible."""
    if not is_feasible(expr, boundary_w, boundary_h, leaf_specs):
        return None
    try:
        rects = dimension(expr, boundary_w, boundary_h, leaf_specs)
    except InfeasibleLayout:
        return None
    breakdown = evaluate_cost(
        rects,
        program_rooms,
        boundary_w,
        boundary_h,
        weights=weights,
        entry_room_id=entry_room_id,
        primary_entry_side=primary_entry_side,
    )
    return breakdown.weighted_total, rects, breakdown


def _estimate_start_temp(
    expr: list[Token],
    rng: random.Random,
    cost0: float,
    boundary_w: float,
    boundary_h: float,
    leaf_specs: dict[str, LeafSpec],
    program_rooms: list[dict],
    entry_room_id: str | None,
    weights: CostWeights,
    samples: int,
    primary_entry_side: str = "south",
) -> float:
    """Average |delta| of accepted-or-not random moves."""
    deltas: list[float] = []
    for _ in range(samples):
        candidate = _propose(expr, rng)
        if candidate is None:
            continue
        result = _cost_of(
            candidate,
            boundary_w,
            boundary_h,
            leaf_specs,
            program_rooms,
            entry_room_id,
            weights,
            primary_entry_side=primary_entry_side,
        )
        if result is None:
            continue
        deltas.append(abs(result[0] - cost0))
    if not deltas:
        return 1.0
    avg = sum(deltas) / len(deltas)
    # Acceptance probability ~= 0.8 for the average move at start.
    return max(0.5, avg / -math.log(0.8) if avg > 0 else 1.0)


def anneal(
    leaves: list[str],
    boundary_w: float,
    boundary_h: float,
    leaf_specs: dict[str, LeafSpec],
    program_rooms: list[dict],
    entry_room_id: str | None,
    *,
    weights: CostWeights = DEFAULT_COST_WEIGHTS,
    config: AnnealConfig | None = None,
    primary_entry_side: str = "south",
) -> AnnealResult:
    """Run simulated annealing on the slicing tree.

    Multi-restart from different random seeds; keep the lowest-cost
    layout that is feasible.
    """
    cfg = config or AnnealConfig()
    master_rng = random.Random(cfg.seed)

    best: AnnealResult | None = None
    total_iters = 0
    total_accept = 0
    for restart in range(cfg.restarts):
        rng = random.Random(master_rng.randint(0, 2**31 - 1))

        # Build a feasible initial tree (try up to 200 times).
        expr: list[Token] | None = None
        for _ in range(200):
            candidate = random_polish(leaves, rng)
            if is_feasible(candidate, boundary_w, boundary_h, leaf_specs):
                expr = candidate
                break
        if expr is None:
            # Infeasible boundary for this room set. Bail out cleanly.
            continue

        baseline = _cost_of(
            expr, boundary_w, boundary_h, leaf_specs, program_rooms, entry_room_id, weights,
            primary_entry_side=primary_entry_side,
        )
        assert baseline is not None
        cost, rects, breakdown = baseline

        temp = _estimate_start_temp(
            expr, rng, cost, boundary_w, boundary_h, leaf_specs,
            program_rooms, entry_room_id, weights, cfg.start_temp_samples,
            primary_entry_side=primary_entry_side,
        )

        best_expr = expr
        best_rects = rects
        best_cost = cost
        best_breakdown = breakdown
        accepted = 0

        for _ in range(cfg.iterations):
            total_iters += 1
            candidate = _propose(expr, rng)
            if candidate is None:
                temp *= cfg.cool_factor
                continue
            result = _cost_of(
                candidate, boundary_w, boundary_h, leaf_specs,
                program_rooms, entry_room_id, weights,
                primary_entry_side=primary_entry_side,
            )
            if result is None:
                temp *= cfg.cool_factor
                continue
            new_cost, new_rects, new_breakdown = result
            delta = new_cost - cost
            if delta <= 0 or rng.random() < math.exp(-delta / max(temp, cfg.min_temp)):
                expr = candidate
                cost = new_cost
                rects = new_rects
                breakdown = new_breakdown
                accepted += 1
                if cost < best_cost:
                    best_expr = expr
                    best_rects = rects
                    best_cost = cost
                    best_breakdown = breakdown
            temp *= cfg.cool_factor
            if temp < cfg.min_temp:
                temp = cfg.min_temp

        total_accept += accepted
        candidate_result = AnnealResult(
            expr=best_expr,
            rects=best_rects,
            cost=best_cost,
            breakdown=best_breakdown,
            iterations=cfg.iterations,
            accepted=accepted,
            restarts=restart + 1,
        )
        if best is None or best_cost < best.cost:
            best = candidate_result

    if best is None:
        raise InfeasibleLayout("no feasible slicing tree found across restarts")
    return AnnealResult(
        expr=best.expr,
        rects=best.rects,
        cost=best.cost,
        breakdown=best.breakdown,
        iterations=total_iters,
        accepted=total_accept,
        restarts=cfg.restarts,
    )


__all__ = [
    "AnnealConfig",
    "AnnealResult",
    "anneal",
    "move_swap_operands",
    "move_complement_chain",
    "move_swap_operand_operator",
]
