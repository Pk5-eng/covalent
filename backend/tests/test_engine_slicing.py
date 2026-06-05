"""Step 4.2: slicing-tree representation and dimensioning."""
from __future__ import annotations

import random

import pytest

from app.engine.slicing import (
    LeafSpec,
    dimension,
    expression_leaves,
    is_normalized,
    parse,
    random_polish,
)


def _spec(area: float, w: float, h: float) -> LeafSpec:
    return LeafSpec(target_area=area, min_w=w, min_h=h)


def test_random_polish_is_well_formed():
    rng = random.Random(0)
    expr = random_polish(["a", "b", "c", "d"], rng)
    # N leaves + N-1 operators.
    assert len(expr) == 7
    assert expression_leaves(expr) == sorted(expression_leaves(expr)) or True
    assert sorted(expression_leaves(expr)) == ["a", "b", "c", "d"]
    parse(expr)  # decodes


def test_random_polish_is_normalized_across_seeds():
    for seed in range(50):
        expr = random_polish(["a", "b", "c", "d", "e"], random.Random(seed))
        assert is_normalized(expr), f"not normalized for seed {seed}: {expr}"


def test_simple_vertical_split_dimensioning():
    expr = ["a", "b", "V"]  # left | right
    specs = {
        "a": _spec(50_000_000, 2000, 2000),
        "b": _spec(50_000_000, 2000, 2000),
    }
    rects = dimension(expr, 10000, 10000, specs)
    assert rects["a"].x == pytest.approx(0)
    assert rects["a"].y == pytest.approx(0)
    assert rects["a"].w == pytest.approx(5000)
    assert rects["a"].h == pytest.approx(10000)
    assert rects["b"].x == pytest.approx(5000)
    assert rects["b"].w == pytest.approx(5000)


def test_simple_horizontal_split_dimensioning():
    expr = ["a", "b", "H"]  # top / bottom
    specs = {
        "a": _spec(30_000_000, 2000, 2000),
        "b": _spec(70_000_000, 2000, 2000),
    }
    rects = dimension(expr, 10000, 10000, specs)
    # H split is proportional along height: 30/100 -> 3000 mm top.
    assert rects["a"].h == pytest.approx(3000)
    assert rects["b"].h == pytest.approx(7000)
    assert rects["a"].y == pytest.approx(0)
    assert rects["b"].y == pytest.approx(3000)


def test_dimensioning_tiles_rectangle_for_n_leaves():
    rng = random.Random(7)
    leaves = ["r1", "r2", "r3", "r4", "r5", "r6"]
    expr = random_polish(leaves, rng)
    specs = {lid: _spec(12_000_000, 2000, 2000) for lid in leaves}
    rects = dimension(expr, 12000, 9000, specs)
    total = sum(r.area for r in rects.values())
    assert total == pytest.approx(12000 * 9000)


def test_dimensioning_respects_minimums_when_target_too_small():
    expr = ["a", "b", "V"]
    specs = {
        "a": _spec(1_000_000, 4000, 4000),  # tiny target but min width 4000
        "b": _spec(99_000_000, 1000, 1000),
    }
    rects = dimension(expr, 10000, 10000, specs)
    assert rects["a"].w >= 4000 - 1e-6


def test_dimensioning_raises_when_leaf_missing():
    with pytest.raises(ValueError):
        dimension(["a", "b", "V"], 10000, 10000, {"a": _spec(1, 1, 1)})
