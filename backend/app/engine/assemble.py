"""Turn an annealer/slicing output into a `FloorPlan` for validation + render.

Step 4.2 stops at room rectangles. Walls and openings come in Step 4.5.
We still build a minimal FloorPlan so validate.py runs and the render
helper can draw something.
"""
from __future__ import annotations

from app.engine.slicing import LeafSpec, Rect
from app.models import Boundary, FloorPlan, PlanMeta, Room
from app.rules.defaults import CATALOG_BY_TYPE


def build_leaf_specs(
    program_rooms: list[dict],
    boundary_w: float,
    boundary_h: float,
) -> dict[str, LeafSpec]:
    """Translate a program (or its frontend mirror) into LeafSpec entries.

    `target_area_m2` is in m^2; mins are in m. Everything else is mm.
    """
    out: dict[str, LeafSpec] = {}
    for r in program_rooms:
        out[r["id"]] = LeafSpec(
            target_area=r["target_area_m2"] * 1_000_000,
            min_w=r["min_width_m"] * 1000,
            min_h=r.get("min_depth_m", r["min_width_m"]) * 1000,
        )
    # Sanity: a single leaf should not exceed the boundary.
    for spec in out.values():
        spec.min_w = min(spec.min_w, boundary_w)
        spec.min_h = min(spec.min_h, boundary_h)
    return out


def floor_plan_from_rects(
    boundary: Boundary,
    program_rooms: list[dict],
    rects: dict[str, Rect],
    snap_mm: float = 0,  # snap is a Step 4.5 finishing pass; keep tiling exact here.
) -> FloorPlan:
    """Assemble a `FloorPlan` from per-room rectangles."""
    rooms: list[Room] = []
    for spec in program_rooms:
        rect = rects[spec["id"]]
        snapped = _snap_rect(rect, boundary, snap_mm) if snap_mm > 0 else rect
        polygon = snapped.as_polygon()[:-1]  # open polygon (4 pts) for the model
        # `Room` model expects a typed catalog entry; defaults pull flags from catalog.
        catalog = CATALOG_BY_TYPE.get(spec["type"])
        rooms.append(
            Room(
                id=spec["id"],
                type=spec["type"],
                label=spec["label"],
                zone=spec["zone"],
                polygon=[(p[0], p[1]) for p in polygon],
                area_mm2=snapped.area,
                needs_window=catalog.needs_window if catalog else spec.get("needs_window", False),
                needs_egress=catalog.needs_egress if catalog else spec.get("needs_egress", False),
                needs_exterior_wall=catalog.needs_exterior_wall if catalog else spec.get("needs_exterior_wall", False),
            )
        )

    return FloorPlan(
        boundary=boundary,
        rooms=rooms,
        walls=[],
        openings=[],
        meta=PlanMeta(),
    )


def _snap_rect(rect: Rect, boundary: Boundary, snap: float) -> Rect:
    """Snap origins to the grid; keep widths/heights such that the boundary
    still tiles exactly. Snap is best-effort here: the slicing-tree splits
    are already snapped during dimensioning when we pass snapped specs,
    but the post-pass guarantees rect edges land on the grid for export.
    """
    if snap <= 0:
        return rect
    x = round(rect.x / snap) * snap
    y = round(rect.y / snap) * snap
    # Snap far edges as well, then derive width/height to keep alignment.
    x2 = round((rect.x + rect.w) / snap) * snap
    y2 = round((rect.y + rect.h) / snap) * snap
    x = max(0.0, min(x, boundary.width_mm))
    y = max(0.0, min(y, boundary.depth_mm))
    x2 = max(x, min(x2, boundary.width_mm))
    y2 = max(y, min(y2, boundary.depth_mm))
    return Rect(x, y, x2 - x, y2 - y)


def program_to_rows(program_rooms: list) -> list[dict]:
    """Coerce either a `Program.rooms` list (pydantic) or list of dicts into
    the dict shape used by the engine helpers.
    """
    out = []
    for r in program_rooms:
        if isinstance(r, dict):
            out.append(r)
        else:
            out.append(
                {
                    "id": r.id,
                    "type": r.type,
                    "label": r.label,
                    "zone": r.zone,
                    "target_area_m2": r.target_area_m2,
                    "min_width_m": r.min_width_m,
                    "needs_window": r.needs_window,
                    "needs_egress": r.needs_egress,
                    "needs_exterior_wall": r.needs_exterior_wall,
                    "min_area_m2": r.target_area_m2,
                }
            )
    return out
