"""Tiny SVG renderer for engine visual checkpoints (Step 4 spec mandate).

Not the production renderer (Step 5). This is enough to eyeball overlap,
gaps, and shape. Saves to a path callers control.
"""
from __future__ import annotations

from pathlib import Path

from app.models import FloorPlan

ZONE_FILL = {
    "public": "#e3eee3",
    "private": "#e6e2f0",
    "service": "#f0e3d6",
    "circulation": "#eaeaea",
    "exterior": "#dbeaf0",
}
ZONE_STROKE = {
    "public": "#2a4d3a",
    "private": "#4a3a8a",
    "service": "#8a553a",
    "circulation": "#666666",
    "exterior": "#3a6a8a",
}


def render_floor_plan_svg(
    plan: FloorPlan,
    *,
    pad_mm: float = 500,
    px_per_mm: float | None = None,
    title: str = "",
) -> str:
    """Produce a self-contained SVG string."""
    bw = plan.boundary.width_mm
    bh = plan.boundary.depth_mm
    target_w = 1200  # px
    if px_per_mm is None:
        px_per_mm = target_w / (bw + 2 * pad_mm)
    width = (bw + 2 * pad_mm) * px_per_mm
    height = (bh + 2 * pad_mm) * px_per_mm
    s = px_per_mm

    def x(mm: float) -> float:
        return (mm + pad_mm) * s

    def y(mm: float) -> float:
        return (mm + pad_mm) * s

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">'
    )
    out.append('<rect width="100%" height="100%" fill="#fafaf7"/>')

    # Boundary
    out.append(
        f'<rect x="{x(0):.1f}" y="{y(0):.1f}" width="{bw * s:.1f}" height="{bh * s:.1f}" '
        f'fill="none" stroke="#1a1a1a" stroke-width="2"/>'
    )

    for room in plan.rooms:
        if not room.polygon:
            continue
        pts = " ".join(f"{x(px):.1f},{y(py):.1f}" for (px, py) in room.polygon)
        fill = ZONE_FILL.get(room.zone, "#f0f0f0")
        stroke = ZONE_STROKE.get(room.zone, "#444")
        out.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
        )
        # centroid for label
        cx = sum(p[0] for p in room.polygon) / len(room.polygon)
        cy = sum(p[1] for p in room.polygon) / len(room.polygon)
        area_m2 = room.area_mm2 / 1_000_000
        font = max(8.0, min(14.0, room.area_mm2 ** 0.5 / 1500))
        out.append(
            f'<g transform="translate({x(cx):.1f},{y(cy):.1f})">'
            f'<text text-anchor="middle" dominant-baseline="central" '
            f'font-family="ui-sans-serif,system-ui" font-size="{font:.1f}" fill="{stroke}">'
            f'<tspan x="0" dy="-0.6em">{_escape(room.label)}</tspan>'
            f'<tspan x="0" dy="1.2em" font-size="{font * 0.8:.1f}" fill="#444">{area_m2:.1f} m²</tspan>'
            f'</text></g>'
        )

    if title:
        out.append(
            f'<text x="{pad_mm * s:.1f}" y="{pad_mm * s * 0.5:.1f}" font-family="ui-sans-serif,system-ui" '
            f'font-size="14" fill="#1a1a1a">{_escape(title)}</text>'
        )

    out.append("</svg>")
    return "".join(out)


def save_floor_plan_svg(plan: FloorPlan, path: str | Path, *, title: str = "") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_floor_plan_svg(plan, title=title), encoding="utf-8")
    return p


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
