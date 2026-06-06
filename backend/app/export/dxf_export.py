"""DXF export (Step 7 of the spec).

Uses `ezdxf` to produce a real CAD drawing with NCS/AIA layers, block
references for doors and windows, real DIMENSION entities (editable in
AutoCAD), MTEXT labels, R2018 format, and millimetre units.

The same layer names are used by the SVG renderer in
`frontend/src/lib/render/layers.ts` so the on-screen drawing and the
DXF agree.
"""
from __future__ import annotations

import io
import math
from typing import BinaryIO

import ezdxf
from ezdxf import bbox, colors
from ezdxf.enums import TextEntityAlignment

from app.models import FloorPlan, Opening, Room, Wall

# Layer names (Section 8 of the spec, locked in CLAUDE.md).
LAYER_EXTERIOR_WALL = "A-WALL-EXTR"
LAYER_INTERIOR_WALL = "A-WALL"
LAYER_DOOR = "A-DOOR"
LAYER_GLAZ = "A-GLAZ"
LAYER_FIXT = "A-FLOR-FIXT"
LAYER_AREA = "A-AREA-IDEN"
LAYER_DIMS = "A-ANNO-DIMS"
LAYER_TEXT = "A-ANNO-TEXT"
LAYER_TTLB = "A-ANNO-TTLB"

# ACI colors (AutoCAD Color Index).
LAYER_COLORS = {
    LAYER_EXTERIOR_WALL: colors.WHITE,
    LAYER_INTERIOR_WALL: colors.WHITE,
    LAYER_DOOR: colors.RED,
    LAYER_GLAZ: colors.CYAN,
    LAYER_FIXT: colors.MAGENTA,
    LAYER_AREA: colors.YELLOW,
    LAYER_DIMS: colors.GREEN,
    LAYER_TEXT: colors.WHITE,
    LAYER_TTLB: colors.WHITE,
}


def floor_plan_to_dxf(plan: FloorPlan, output: BinaryIO) -> None:
    """Write a DXF representation of the floor plan to `output`.

    The plan must already be valid (rooms tile the boundary, walls have
    been built). Callers in main.py and the tests handle validation.
    """
    doc = ezdxf.new(dxfversion="R2018", setup=True)

    # mm units (Section 10).
    doc.header["$INSUNITS"] = 4  # 4 = millimetres
    doc.header["$MEASUREMENT"] = 1  # metric

    _ensure_layers(doc)
    _define_blocks(doc)

    msp = doc.modelspace()

    _draw_walls(msp, plan)
    _draw_openings(msp, plan)
    _draw_fixtures(msp, plan)
    _draw_room_labels(msp, plan)
    _draw_dimensions(msp, plan)
    _draw_title_block(msp, plan)

    # Set viewport to cover the plan + margin.
    try:
        bb = bbox.extents(msp)
        if bb.has_data:
            doc.set_modelspace_vport(
                height=max(bb.size.y, bb.size.x) * 1.1,
                center=(bb.center.x, bb.center.y),
            )
    except Exception:
        pass

    # Write to a string buffer first, then encode — wrapping BytesIO directly
    # in TextIOWrapper closes it on garbage collection.
    text_buf = io.StringIO()
    doc.write(text_buf)
    output.write(text_buf.getvalue().encode("utf-8"))


# ----------------------------------------------------------------------
# Layers + blocks
# ----------------------------------------------------------------------


def _ensure_layers(doc) -> None:
    for name, color in LAYER_COLORS.items():
        if name in doc.layers:
            continue
        layer = doc.layers.add(name)
        layer.dxf.color = color


def _define_blocks(doc) -> None:
    """Door + window block definitions, sized at 1000 mm so we can scale them
    by the opening width on insert.
    """
    if "DOOR" not in doc.blocks:
        block = doc.blocks.new(name="DOOR")
        # Door leaf (1 unit long, rotates around origin).
        block.add_line((0, 0), (1, 0), dxfattribs={"layer": LAYER_DOOR})
        # Swing arc (90 degrees).
        block.add_arc(
            center=(0, 0),
            radius=1.0,
            start_angle=0,
            end_angle=90,
            dxfattribs={"layer": LAYER_DOOR},
        )

    if "WINDOW" not in doc.blocks:
        block = doc.blocks.new(name="WINDOW")
        # Two parallel lines representing the glazing line (sill + head).
        block.add_line((0, -0.04), (1, -0.04), dxfattribs={"layer": LAYER_GLAZ})
        block.add_line((0, 0.04), (1, 0.04), dxfattribs={"layer": LAYER_GLAZ})
        # Mullion midline (centerline of glazing).
        block.add_line((0, 0), (1, 0), dxfattribs={"layer": LAYER_GLAZ})


# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------


def _wall_normal(wall: Wall) -> tuple[float, float]:
    dx = wall.b[0] - wall.a[0]
    dy = wall.b[1] - wall.a[1]
    length = math.hypot(dx, dy) or 1
    return (-dy / length, dx / length)


def _wall_unit(wall: Wall) -> tuple[float, float]:
    dx = wall.b[0] - wall.a[0]
    dy = wall.b[1] - wall.a[1]
    length = math.hypot(dx, dy) or 1
    return (dx / length, dy / length)


def _wall_length(wall: Wall) -> float:
    dx = wall.b[0] - wall.a[0]
    dy = wall.b[1] - wall.a[1]
    return math.hypot(dx, dy)


# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------


def _draw_walls(msp, plan: FloorPlan) -> None:
    """Walls as HATCH SOLID poche on the wall layers (Section 10)."""
    for wall in plan.walls:
        layer = LAYER_EXTERIOR_WALL if wall.type == "exterior" else LAYER_INTERIOR_WALL
        n = _wall_normal(wall)
        half = wall.thickness_mm / 2
        a, b = wall.a, wall.b
        p1 = (a[0] + n[0] * half, a[1] + n[1] * half)
        p2 = (b[0] + n[0] * half, b[1] + n[1] * half)
        p3 = (b[0] - n[0] * half, b[1] - n[1] * half)
        p4 = (a[0] - n[0] * half, a[1] - n[1] * half)
        # Hatched solid poche.
        hatch = msp.add_hatch(color=colors.WHITE, dxfattribs={"layer": layer})
        hatch.paths.add_polyline_path([p1, p2, p3, p4], is_closed=True)
        # Boundary lines.
        msp.add_lwpolyline([p1, p2, p3, p4], close=True, dxfattribs={"layer": layer})


def _draw_openings(msp, plan: FloorPlan) -> None:
    walls_by_id = {w.id: w for w in plan.walls}
    for op in plan.openings:
        wall = walls_by_id.get(op.wall_id)
        if wall is None:
            continue
        u = _wall_unit(wall)
        wall_len = _wall_length(wall)
        center = (
            wall.a[0] + u[0] * wall_len * op.position,
            wall.a[1] + u[1] * wall_len * op.position,
        )
        half = op.width_mm / 2
        ins_point = (center[0] - u[0] * half, center[1] - u[1] * half)
        rotation = math.degrees(math.atan2(u[1], u[0]))

        block_name = "DOOR" if op.kind == "door" else "WINDOW"
        msp.add_blockref(
            block_name,
            insert=ins_point,
            dxfattribs={
                "xscale": op.width_mm,
                "yscale": op.width_mm,
                "zscale": 1.0,
                "rotation": rotation,
                "layer": LAYER_DOOR if op.kind == "door" else LAYER_GLAZ,
            },
        )


def _draw_fixtures(msp, plan: FloorPlan) -> None:
    """Furniture/fixtures as lwpolylines on A-FLOR-FIXT, with a small MTEXT label."""
    for fx in plan.fixtures:
        if len(fx.polygon) < 3:
            continue
        msp.add_lwpolyline(
            list(fx.polygon),
            close=True,
            dxfattribs={"layer": LAYER_FIXT, "color": colors.MAGENTA},
        )
        if fx.label:
            cx = sum(p[0] for p in fx.polygon) / len(fx.polygon)
            cy = sum(p[1] for p in fx.polygon) / len(fx.polygon)
            text = msp.add_mtext(
                fx.label,
                dxfattribs={"layer": LAYER_FIXT, "char_height": 120},
            )
            text.set_location(insert=(cx, cy), attachment_point=5)


def _room_centroid(room: Room) -> tuple[float, float]:
    xs = [p[0] for p in room.polygon]
    ys = [p[1] for p in room.polygon]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _draw_room_labels(msp, plan: FloorPlan) -> None:
    for room in plan.rooms:
        if not room.polygon:
            continue
        cx, cy = _room_centroid(room)
        area_m2 = room.area_mm2 / 1_000_000
        text = msp.add_mtext(
            f"{room.label.upper()}\\P{area_m2:.1f} m²",
            dxfattribs={
                "layer": LAYER_AREA,
                "char_height": 200,
                "width": 0,
            },
        )
        text.set_location(insert=(cx, cy), attachment_point=5)  # MIDDLE_CENTER


def _draw_dimensions(msp, plan: FloorPlan) -> None:
    """Overall + per-room linear dimensions as real DIMENSION entities."""
    bw = plan.boundary.width_mm
    bh = plan.boundary.depth_mm
    off = 800
    # Overall width along bottom.
    dim_w = msp.add_linear_dim(
        base=(0, -off),
        p1=(0, 0),
        p2=(bw, 0),
        angle=0,
        dxfattribs={"layer": LAYER_DIMS},
    )
    dim_w.render()
    # Overall depth along right.
    dim_h = msp.add_linear_dim(
        base=(bw + off, 0),
        p1=(bw, 0),
        p2=(bw, bh),
        angle=90,
        dxfattribs={"layer": LAYER_DIMS},
    )
    dim_h.render()

    # Per-room width dimensions, lightly placed inside the room above the label.
    for room in plan.rooms:
        if not room.polygon:
            continue
        xs = [p[0] for p in room.polygon]
        ys = [p[1] for p in room.polygon]
        x0, x1 = min(xs), max(xs)
        y0 = min(ys)
        w = x1 - x0
        if w < 2000:
            continue
        dim = msp.add_linear_dim(
            base=(x0 + w / 2, y0 - 200),
            p1=(x0, y0),
            p2=(x1, y0),
            angle=0,
            dxfattribs={"layer": LAYER_DIMS, "color": colors.GREEN},
        )
        dim.render()


def _draw_title_block(msp, plan: FloorPlan) -> None:
    bw = plan.boundary.width_mm
    bh = plan.boundary.depth_mm
    title_y = bh + 1500
    title = msp.add_mtext(
        f"{plan.meta.title.upper()}\\P"
        f"SCALE {plan.meta.scale}    "
        f"{(bw / 1000):.2f} m × {(bh / 1000):.2f} m    "
        f"NORTH ↑",
        dxfattribs={
            "layer": LAYER_TTLB,
            "char_height": 240,
        },
    )
    title.set_location(insert=(0, title_y), attachment_point=1)  # TOP_LEFT
    # Simple title-block frame.
    msp.add_lwpolyline(
        [
            (0, title_y - 600),
            (bw, title_y - 600),
            (bw, title_y + 200),
            (0, title_y + 200),
        ],
        close=True,
        dxfattribs={"layer": LAYER_TTLB},
    )


__all__ = ["floor_plan_to_dxf"]
