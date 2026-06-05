"""Smoke tests for the public API endpoints (Steps 1 + 2)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "covalent"


def test_echo():
    r = client.get("/api/echo", params={"message": "hello"})
    assert r.status_code == 200
    assert r.json() == {"echo": "hello"}


def test_catalog_shape():
    r = client.get("/api/catalog")
    assert r.status_code == 200
    rooms = r.json()["rooms"]
    assert len(rooms) > 10
    sample = rooms[0]
    for key in ("type", "label", "zone", "target_m2", "min_m2", "min_width_m"):
        assert key in sample
    assert any(r["type"] == "primary_bedroom" for r in rooms)


def test_program_check_happy():
    payload = {
        "boundary": {"width_mm": 12000, "depth_mm": 10000, "units_display": "metric"},
        "rooms": [
            {"type": "living_room", "count": 1},
            {"type": "kitchen", "count": 1},
            {"type": "primary_bedroom", "count": 1},
            {"type": "bedroom", "count": 2},
            {"type": "full_bath", "count": 2},
        ],
    }
    r = client.post("/api/program/check", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["summary"]["boundary_area_m2"] == 120
    assert len(body["summary"]["rooms_expanded"]) == 7


def test_program_check_overflow_errors():
    payload = {
        "boundary": {"width_mm": 4000, "depth_mm": 4000, "units_display": "metric"},
        "rooms": [{"type": "living_room", "count": 1}, {"type": "primary_bedroom", "count": 1}],
    }
    r = client.post("/api/program/check", json=payload)
    body = r.json()
    assert body["ok"] is False
    assert any("exceed" in e for e in body["errors"])
