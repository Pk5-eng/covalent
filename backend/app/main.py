"""Covalent backend entrypoint (Step 1: scaffolding).

Endpoints land here as steps progress. Step 1 ships only health + echo so
the frontend can prove the round trip works.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models import Boundary, RoomRequest
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
