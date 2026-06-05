"""Slicing-tree representation + dimensioning (Step 4.2 of the spec).

The slicing tree is encoded as a *normalized Polish (postfix) expression*
(Wong-Liu 1986). Leaves are room ids; internal nodes are cut operators
H (horizontal cut: top child stacked on bottom child) or V (vertical cut:
left child beside right child).

A normalized Polish expression of N leaves and N-1 operators decodes to
exactly one slicing layout. The "normalized" property forbids two
adjacent operators of the same kind; this gives the representation
unique decoding (no aliasing).

Dimensioning a tree, given the boundary and per-leaf target areas:
    - at every internal node, split the rectangle between the two
      children proportional to the total target area of each subtree
      along the cut axis,
    - clamp each child to its leaf-min dimension and renormalize the
      remainder.
The result is exact rectangles tiling the boundary.

This module exports:
    PolishExpr               : a tuple-based slicing tree
    random_polish(ids, rng)  : seedable random normalized expression
    dimension(expr, ...)     : produce per-leaf rectangles
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal, Union

# ----------------------------------------------------------------------
# Polish expression as a list of tokens.
# Operands are room id strings; operators are "H" or "V" literals.
# ----------------------------------------------------------------------

Token = Union[str, Literal["H", "V"]]
Operator = Literal["H", "V"]


def is_operator(tok: Token) -> bool:
    return tok == "H" or tok == "V"


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h

    def as_polygon(self) -> list[tuple[float, float]]:
        """Closed polygon (5 points). Origin is top-left, y grows down."""
        return [
            (self.x, self.y),
            (self.x + self.w, self.y),
            (self.x + self.w, self.y + self.h),
            (self.x, self.y + self.h),
            (self.x, self.y),
        ]


@dataclass
class LeafSpec:
    """Per-leaf constraints used when dimensioning a tree."""

    target_area: float
    min_w: float
    min_h: float

    @property
    def target_area_clamped(self) -> float:
        return max(self.target_area, self.min_w * self.min_h)


# ----------------------------------------------------------------------
# Tree decoding
# ----------------------------------------------------------------------


@dataclass
class _Node:
    """Internal binary-tree representation built from a Polish expression."""

    operator: Operator | None = None
    leaf: str | None = None
    children: tuple["_Node", "_Node"] | None = None
    leaves: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_leaf(self) -> bool:
        return self.leaf is not None


def is_normalized(expr: list[Token]) -> bool:
    """No two adjacent operators may be the same."""
    last_op: Operator | None = None
    for tok in expr:
        if is_operator(tok):
            if last_op == tok:
                return False
            last_op = tok  # type: ignore[assignment]
        else:
            last_op = None
    return True


def parse(expr: list[Token]) -> _Node:
    """Decode a Polish expression into a binary tree.

    Raises ValueError on malformed expressions.
    """
    stack: list[_Node] = []
    for tok in expr:
        if is_operator(tok):
            if len(stack) < 2:
                raise ValueError(f"malformed expression near operator {tok}")
            right = stack.pop()
            left = stack.pop()
            node = _Node(
                operator=tok,  # type: ignore[arg-type]
                children=(left, right),
                leaves=left.leaves + right.leaves,
            )
            stack.append(node)
        else:
            stack.append(_Node(leaf=tok, leaves=(tok,)))
    if len(stack) != 1:
        raise ValueError("malformed expression: extra operands")
    return stack[0]


def expression_leaves(expr: list[Token]) -> list[str]:
    return [t for t in expr if not is_operator(t)]


# ----------------------------------------------------------------------
# Dimensioning
# ----------------------------------------------------------------------


class InfeasibleLayout(ValueError):
    """A tree's minimum dimensions exceed the available rectangle."""


def is_feasible(
    expr: list[Token],
    boundary_w: float,
    boundary_h: float,
    leaf_specs: dict[str, LeafSpec],
) -> bool:
    """Cheap check: do the subtree min-dims fit the boundary?"""
    tree = parse(expr)
    min_w, min_h = _min_dims(tree, leaf_specs)
    return min_w <= boundary_w + 1e-6 and min_h <= boundary_h + 1e-6


def dimension(
    expr: list[Token],
    boundary_w: float,
    boundary_h: float,
    leaf_specs: dict[str, LeafSpec],
) -> dict[str, Rect]:
    """Produce exact rectangles for every leaf id in the expression.

    Splits proportional to subtree target-area sum along the cut axis,
    clamped to each child's minimum dimension. Children of an H-cut split
    the parent's height (top child on top, bottom child on bottom);
    children of a V-cut split the parent's width (left child on the left).

    Raises `InfeasibleLayout` if the tree's structural minimums exceed
    the boundary (in which case no honest dimensioning exists).
    """
    leaves = expression_leaves(expr)
    missing = [lid for lid in leaves if lid not in leaf_specs]
    if missing:
        raise ValueError(f"missing leaf specs: {missing}")

    if not is_feasible(expr, boundary_w, boundary_h, leaf_specs):
        raise InfeasibleLayout(
            f"slicing tree minimums exceed boundary {boundary_w}x{boundary_h}"
        )

    tree = parse(expr)
    out: dict[str, Rect] = {}
    _layout_node(tree, Rect(0, 0, boundary_w, boundary_h), leaf_specs, out)
    return out


def _layout_node(
    node: _Node,
    rect: Rect,
    leaf_specs: dict[str, LeafSpec],
    out: dict[str, Rect],
) -> None:
    if node.is_leaf:
        out[node.leaf] = rect  # type: ignore[index]
        return

    assert node.operator and node.children
    a, b = node.children

    a_target = sum(leaf_specs[lid].target_area_clamped for lid in a.leaves)
    b_target = sum(leaf_specs[lid].target_area_clamped for lid in b.leaves)
    total = a_target + b_target if (a_target + b_target) > 0 else 1.0
    ratio_a = a_target / total

    if node.operator == "V":
        # Vertical cut splits width. Left child gets ratio_a of the width.
        w_a = rect.w * ratio_a
        w_a, w_b = _clamp_split_along_axis(
            full=rect.w,
            initial_a=w_a,
            min_a=_min_along_axis(a, leaf_specs, axis="w"),
            min_b=_min_along_axis(b, leaf_specs, axis="w"),
        )
        a_rect = Rect(rect.x, rect.y, w_a, rect.h)
        b_rect = Rect(rect.x + w_a, rect.y, w_b, rect.h)
    else:  # "H"
        # Horizontal cut splits height. Top child on top.
        h_a = rect.h * ratio_a
        h_a, h_b = _clamp_split_along_axis(
            full=rect.h,
            initial_a=h_a,
            min_a=_min_along_axis(a, leaf_specs, axis="h"),
            min_b=_min_along_axis(b, leaf_specs, axis="h"),
        )
        a_rect = Rect(rect.x, rect.y, rect.w, h_a)
        b_rect = Rect(rect.x, rect.y + h_a, rect.w, h_b)

    _layout_node(a, a_rect, leaf_specs, out)
    _layout_node(b, b_rect, leaf_specs, out)


def _min_dims(node: _Node, leaf_specs: dict[str, LeafSpec]) -> tuple[float, float]:
    """Recursively compute (min_w, min_h) the subtree's rectangle must satisfy.

    Stacking direction matters:
        V-cut: children are side by side, so widths add and heights take max.
        H-cut: children are stacked, so heights add and widths take max.
    """
    if node.is_leaf:
        spec = leaf_specs[node.leaf]  # type: ignore[index]
        return spec.min_w, spec.min_h
    assert node.children and node.operator
    aw, ah = _min_dims(node.children[0], leaf_specs)
    bw, bh = _min_dims(node.children[1], leaf_specs)
    if node.operator == "V":
        return aw + bw, max(ah, bh)
    return max(aw, bw), ah + bh


def _min_along_axis(node: _Node, leaf_specs: dict[str, LeafSpec], axis: str) -> float:
    mw, mh = _min_dims(node, leaf_specs)
    return mw if axis == "w" else mh


def _clamp_split_along_axis(
    *, full: float, initial_a: float, min_a: float, min_b: float
) -> tuple[float, float]:
    """Return (a, b) with a + b == full, honoring both minimums where possible.

    If min_a + min_b > full, return the minimums and accept overflow; the
    validator will catch the infeasibility downstream rather than us
    silently lying.
    """
    if min_a + min_b > full:
        return min_a, min_b
    a = max(min_a, min(initial_a, full - min_b))
    b = full - a
    return a, b


# ----------------------------------------------------------------------
# Random initial expressions
# ----------------------------------------------------------------------


def random_polish(ids: list[str], rng: random.Random) -> list[Token]:
    """Build a random normalized Polish expression over the given leaves.

    Constructed by repeatedly merging two random sub-expressions with a
    random operator. Guarantees normalization by checking the boundary
    tokens of each child before pairing them.
    """
    if not ids:
        return []
    if len(ids) == 1:
        return [ids[0]]

    pool: list[list[Token]] = [[lid] for lid in ids]
    rng.shuffle(pool)

    while len(pool) > 1:
        i = rng.randrange(len(pool))
        a = pool.pop(i)
        j = rng.randrange(len(pool))
        b = pool.pop(j)
        op = pick_normalizing_operator(a, b, rng)
        pool.append(a + b + [op])

    return pool[0]


def pick_normalizing_operator(a: list[Token], b: list[Token], rng: random.Random) -> Operator:
    """Choose H or V so that the merged expression stays normalized.

    The only adjacencies created by the merge are:
        ... last(a) | first(b) ...     (b is right after a)
        ... last(b) | op               (op is right after b)
    last(a)/first(b) are at sub-expression boundaries and don't create
    adjacent operators of the same kind because each subexpression is
    itself a valid Polish expression ending in an operand-or-operator
    that we already controlled. What we DO need to avoid is the new `op`
    matching the trailing operator of b, since `b + [op]` would produce
    an adjacent same-kind operator pair.
    """
    last_b = b[-1]
    if is_operator(last_b):
        forced: Operator = "H" if last_b == "V" else "V"
        return forced
    # Both options are valid; flip a coin.
    return "V" if rng.random() < 0.5 else "H"
