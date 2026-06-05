"""Step 7: DXF export round-trip + content checks."""
from __future__ import annotations

import io
from pathlib import Path

import ezdxf

from app.agent.architect import generate_program
from app.engine.anneal import AnnealConfig
from app.engine.pipeline import build_floor_plan
from app.export.dxf_export import (
    LAYER_AREA,
    LAYER_DIMS,
    LAYER_DOOR,
    LAYER_EXTERIOR_WALL,
    LAYER_GLAZ,
    LAYER_INTERIOR_WALL,
    floor_plan_to_dxf,
)
from app.models import Boundary, RoomRequest

OUT_DIR = Path(__file__).resolve().parent.parent / "render_out"
FAST = AnnealConfig(iterations=400, restarts=1, seed=11)


def _build_plan(monkeypatch) -> tuple[Boundary, object]:
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
    plan, _ = build_floor_plan(boundary, program, anneal_config=FAST)
    return boundary, plan


def test_dxf_writes_and_reopens(monkeypatch):
    """The DXF must be readable by ezdxf after writing (spec acceptance check)."""
    _, plan = _build_plan(monkeypatch)
    buf = io.BytesIO()
    floor_plan_to_dxf(plan, buf)
    buf.seek(0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "step7_export.dxf"
    out_path.write_bytes(buf.getvalue())

    doc = ezdxf.read(io.StringIO(buf.getvalue().decode("utf-8")))
    assert doc.header["$INSUNITS"] == 4  # mm
    # NCS layers present.
    layer_names = {l.dxf.name for l in doc.layers}
    for required in [
        LAYER_EXTERIOR_WALL,
        LAYER_INTERIOR_WALL,
        LAYER_DOOR,
        LAYER_GLAZ,
        LAYER_AREA,
        LAYER_DIMS,
    ]:
        assert required in layer_names, f"layer {required!r} missing"


def test_dxf_contains_walls_doors_windows_dims(monkeypatch):
    _, plan = _build_plan(monkeypatch)
    buf = io.BytesIO()
    floor_plan_to_dxf(plan, buf)
    buf.seek(0)
    doc = ezdxf.read(io.StringIO(buf.getvalue().decode("utf-8")))
    msp = doc.modelspace()
    entities = list(msp)

    # At least one of each entity kind from the plan should land in the DXF.
    types = {e.dxftype() for e in entities}
    assert "LWPOLYLINE" in types       # walls + title block
    assert "HATCH" in types            # wall poche
    assert "INSERT" in types           # door + window block references
    assert "MTEXT" in types            # labels + title
    assert "DIMENSION" in types        # real dimension entities

    # Block defs exist.
    assert "DOOR" in doc.blocks
    assert "WINDOW" in doc.blocks
