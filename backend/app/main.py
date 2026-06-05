"""Covalent backend entrypoint (Step 1: scaffolding).

Endpoints land here as steps progress. Step 1 ships only health + echo so
the frontend can prove the round trip works.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent.architect import generate_program
from app.agent.schema import AgentOutputError
from app.engine.pipeline import build_floor_plan, resize_room
from app.engine.slicing import InfeasibleLayout
from app.engine.validate import ValidationError as EngineValidationError
from app.models import Boundary, FloorPlan, Program, RoomRequest
from app.program import check_program
from app.rules.defaults import catalog_for_palette

logger = logging.getLogger("covalent")
logging.basicConfig(level=os.environ.get("COVALENT_LOG", "INFO"))

app = FastAPI(title="Covalent", version="0.1.0")

_allowed_origins = os.environ.get(
    "COVALENT_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "covalent", "version": "0.1.0"}


@app.get("/api/echo")
def echo(message: str = "hello from covalent") -> dict[str, Any]:
    return {"echo": message}


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    """Room catalog for the palette (Section 7)."""
    return {"rooms": catalog_for_palette()}


class _ProgramCheckRequest(BaseModel):
    boundary: Boundary
    rooms: list[RoomRequest]


@app.post("/api/program/check")
def program_check(req: _ProgramCheckRequest) -> dict[str, Any]:
    """Validate a boundary + room selection. Returns warnings + errors + area tally."""
    result = check_program(req.boundary, req.rooms)
    s = result.summary
    return {
        "ok": result.ok,
        "warnings": result.warnings,
        "errors": result.errors,
        "summary": {
            "boundary_area_m2": s.boundary_area_m2,
            "usable_area_m2": s.usable_area_m2,
            "min_required_m2": s.min_required_m2,
            "target_total_m2": s.target_total_m2,
            "rooms_expanded": s.rooms_expanded,
        },
    }


@app.post("/api/program/generate")
def program_generate(req: _ProgramCheckRequest) -> dict[str, Any]:
    """Run the architect agent and return the validated program.

    Geometry-free. See /api/generate for the full plan.
    """
    check = check_program(req.boundary, req.rooms)
    if not check.ok:
        raise HTTPException(status_code=400, detail={"errors": check.errors})
    try:
        program = generate_program(req.boundary, req.rooms)
    except AgentOutputError as e:
        raise HTTPException(status_code=502, detail=f"agent: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "program": program.model_dump(by_alias=True),
        "summary": {
            "boundary_area_m2": check.summary.boundary_area_m2,
            "usable_area_m2": check.summary.usable_area_m2,
        },
    }


class _GenerateRequest(BaseModel):
    boundary: Boundary
    rooms: list[RoomRequest]
    seed: int | None = None


@app.post("/api/generate")
def generate_plan(req: _GenerateRequest) -> dict[str, Any]:
    """Full pipeline: program (agent) -> annealed layout -> finished plan."""
    check = check_program(req.boundary, req.rooms)
    if not check.ok:
        raise HTTPException(status_code=400, detail={"errors": check.errors})
    try:
        program = generate_program(req.boundary, req.rooms)
        plan, diag = build_floor_plan(req.boundary, program, seed=req.seed)
    except AgentOutputError as e:
        raise HTTPException(status_code=502, detail=f"agent: {e}") from e
    except InfeasibleLayout as e:
        raise HTTPException(status_code=400, detail=f"layout: {e}") from e
    except EngineValidationError as e:
        raise HTTPException(status_code=500, detail=f"engine: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "plan": plan.model_dump(),
        "program": program.model_dump(by_alias=True),
        "diagnostics": {
            "cost": diag.cost,
            "iterations": diag.iterations,
            "accepted": diag.accepted,
            "restarts": diag.restarts,
            "breakdown": diag.breakdown.to_dict(),
        },
    }


class _ResizeRequest(BaseModel):
    plan: FloorPlan
    program: Program
    room_id: str
    new_target_area_m2: float


@app.post("/api/resize")
def resize_plan(req: _ResizeRequest) -> dict[str, Any]:
    try:
        plan, diag = resize_room(
            req.plan, req.program, req.room_id, req.new_target_area_m2
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InfeasibleLayout as e:
        raise HTTPException(status_code=400, detail=f"layout: {e}") from e

    return {
        "plan": plan.model_dump(),
        "diagnostics": {
            "cost": diag.cost,
            "iterations": diag.iterations,
            "accepted": diag.accepted,
            "restarts": diag.restarts,
        },
    }
