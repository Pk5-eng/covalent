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
