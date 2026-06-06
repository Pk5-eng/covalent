"""Input validation for a user's boundary + room selection (Step 2).

This module turns the palette form into a validated program request.
Geometry is not produced here. We only check that the request is
internally consistent and that it has any hope of fitting the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import Boundary, RoomRequest
from app.rules.defaults import CATALOG_BY_TYPE, CIRCULATION_TARGET_PCT


@dataclass
class ProgramSummary:
    boundary_area_m2: float
    usable_area_m2: float        # boundary minus walls + circulation
    min_required_m2: float       # sum of room minimums
    target_total_m2: float       # sum of typical targets
    rooms_expanded: list[dict]   # one entry per room instance, with ids


def usable_area_m2(boundary: Boundary, circulation_pct: int = CIRCULATION_TARGET_PCT) -> float:
    """Boundary footprint minus an allowance for walls and circulation."""
    area_m2 = (boundary.width_mm * boundary.depth_mm) / 1_000_000.0
    # ~6% wall allowance + the configured circulation target.
    wall_allowance = 0.06
    return area_m2 * (1 - wall_allowance) * (1 - circulation_pct / 100.0)


def expand_room_requests(rooms: list[RoomRequest]) -> list[dict]:
    """Expand counts into per-instance entries with stable ids.

    Handles suite bundles (e.g. "primary_suite" expands to a primary_bedroom
    + a full_bath, with a shared `suite_group` marker so the architect can
    pair them with an ensuite adjacency).

    Labels only get a numeric suffix when more than one of a type exists.
    """
    # First pass: count total instances per CONCRETE component type so we
    # know whether to suffix labels.
    totals: dict[str, int] = {}
    for r in rooms:
        spec = CATALOG_BY_TYPE.get(r.type)
        if spec is None:
            raise ValueError(f"unknown room type: {r.type}")
        if r.count < 1:
            continue
        if spec.bundle:
            for ctype in spec.bundle:
                totals[ctype] = totals.get(ctype, 0) + r.count
        else:
            totals[r.type] = totals.get(r.type, 0) + r.count

    # Second pass: emit per-instance dicts.
    out: list[dict] = []
    counters: dict[str, int] = {}
    suite_counter = 0
    for r in rooms:
        spec = CATALOG_BY_TYPE[r.type]
        if r.count < 1:
            continue
        for _ in range(r.count):
            if spec.bundle:
                suite_counter += 1
                suite_id = f"{r.type}_{suite_counter}"
                for ctype in spec.bundle:
                    comp = CATALOG_BY_TYPE.get(ctype)
                    if comp is None:
                        continue
                    counters[ctype] = counters.get(ctype, 0) + 1
                    idx = counters[ctype]
                    label = comp.label if totals.get(ctype, 0) == 1 else f"{comp.label} {idx}"
                    out.append(_room_dict(comp, idx, label, suite_group=suite_id))
            else:
                counters[r.type] = counters.get(r.type, 0) + 1
                idx = counters[r.type]
                label = spec.label if totals.get(r.type, 0) == 1 else f"{spec.label} {idx}"
                out.append(_room_dict(spec, idx, label, suite_group=None))
    return out


def _room_dict(spec, idx: int, label: str, suite_group: str | None) -> dict:
    return {
        "id": f"{spec.type}_{idx}",
        "type": spec.type,
        "label": label,
        "zone": spec.zone,
        "target_area_m2": spec.target_m2,
        "min_area_m2": spec.min_m2,
        "min_width_m": spec.min_width_m,
        "needs_window": spec.needs_window,
        "needs_egress": spec.needs_egress,
        "needs_exterior_wall": spec.needs_exterior_wall,
        "suite_group": suite_group,
    }


def summarize_program(boundary: Boundary, rooms: list[RoomRequest]) -> ProgramSummary:
    """Compute the area tally for the room palette."""
    expanded = expand_room_requests(rooms)
    boundary_area = (boundary.width_mm * boundary.depth_mm) / 1_000_000.0
    return ProgramSummary(
        boundary_area_m2=boundary_area,
        usable_area_m2=usable_area_m2(boundary),
        min_required_m2=sum(r["min_area_m2"] for r in expanded),
        target_total_m2=sum(r["target_area_m2"] for r in expanded),
        rooms_expanded=expanded,
    )


@dataclass
class ProgramCheck:
    ok: bool
    warnings: list[str]
    errors: list[str]
    summary: ProgramSummary


def check_program(boundary: Boundary, rooms: list[RoomRequest]) -> ProgramCheck:
    """Validate a boundary + room selection. Returns warnings + errors.

    Errors block generation. Warnings inform but allow proceeding.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if boundary.width_mm < 3000 or boundary.depth_mm < 3000:
        errors.append("Boundary must be at least 3.0m x 3.0m.")
    if boundary.width_mm > 60_000 or boundary.depth_mm > 60_000:
        warnings.append("Boundary larger than 60m on a side. Unusual scale.")

    if not rooms:
        errors.append("Select at least one room.")

    summary = summarize_program(boundary, rooms)
    if summary.min_required_m2 > summary.usable_area_m2:
        errors.append(
            f"Room minimums ({summary.min_required_m2:.1f} m^2) exceed usable area "
            f"({summary.usable_area_m2:.1f} m^2). Remove rooms or enlarge the boundary."
        )
    elif summary.target_total_m2 > summary.usable_area_m2:
        warnings.append(
            f"Typical room targets ({summary.target_total_m2:.1f} m^2) exceed usable "
            f"area ({summary.usable_area_m2:.1f} m^2). Rooms will be scaled down."
        )

    return ProgramCheck(ok=not errors, warnings=warnings, errors=errors, summary=summary)
