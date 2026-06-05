"""Architect agent (Step 3).

Sends the requested rooms + usable area to Claude with the spec's Appendix
system prompt. Validates the response into a `Program`, rejects coordinates,
and clamps targets to the usable area.

When `ANTHROPIC_API_KEY` is unset, falls back to a deterministic rule-based
program builder so the rest of the pipeline can be exercised offline. The
fallback emits the same schema and is exercised by tests.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT, build_user_message
from app.agent.schema import (
    AgentOutputError,
    Program,
    clamp_to_usable_area,
    parse_program_json,
    validate_program_dict,
)
from app.models import Boundary, RoomRequest
from app.program import summarize_program
from app.rules.defaults import CATALOG_BY_TYPE, ROOM_CATALOG

logger = logging.getLogger("covalent.agent")

DEFAULT_MODEL = os.environ.get("COVALENT_AGENT_MODEL", "claude-opus-4-7")
DEFAULT_MAX_TOKENS = int(os.environ.get("COVALENT_AGENT_MAX_TOKENS", "4096"))


def generate_program(
    boundary: Boundary,
    rooms: list[RoomRequest],
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> Program:
    """Produce a validated architect program for the given boundary + rooms."""
    summary = summarize_program(boundary, rooms)
    if not summary.rooms_expanded:
        raise ValueError("no rooms requested")

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set; using deterministic fallback program")
        program = _fallback_program(summary.rooms_expanded, summary.usable_area_m2)
    else:
        program = _call_claude(
            usable_area_m2=summary.usable_area_m2,
            rooms_expanded=summary.rooms_expanded,
            model=model or DEFAULT_MODEL,
            api_key=api_key,
        )

    return clamp_to_usable_area(program, summary.usable_area_m2)


def _call_claude(
    *,
    usable_area_m2: float,
    rooms_expanded: list[dict],
    model: str,
    api_key: str,
) -> Program:
    """Hit the Anthropic Messages API and parse the response."""
    # Import inside the function so the module is importable without the SDK
    # when only the fallback is in use (e.g. CI without secrets).
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = build_user_message(usable_area_m2, rooms_expanded)

    logger.info("calling architect agent: model=%s rooms=%d", model, len(rooms_expanded))
    response = client.messages.create(
        model=model,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    # Concatenate text blocks (the model can emit multiple).
    text_chunks: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            text_chunks.append(text)
    raw = "".join(text_chunks).strip()
    if not raw:
        raise AgentOutputError("architect agent returned an empty response")

    try:
        return parse_program_json(raw)
    except AgentOutputError as e:
        logger.warning("architect output rejected: %s\nraw:\n%s", e, raw[:1000])
        raise


# ----------------------------------------------------------------------
# Deterministic fallback. Mirrors the prompt rules well enough that the
# engine and frontend can be developed without an API key.
# ----------------------------------------------------------------------


def _fallback_program(rooms_expanded: list[dict], usable_area_m2: float) -> Program:
    """Build a sensible program from the catalog + the spec's adjacency rules."""

    # 1. Pick an entry room: foyer if present, else any public room, else any room.
    entry_id = _pick_entry(rooms_expanded)

    # 2. Build per-room dicts in the schema shape.
    rooms_payload: list[dict[str, Any]] = []
    for r in rooms_expanded:
        rooms_payload.append(
            {
                "id": r["id"],
                "type": r["type"],
                "label": r["label"],
                "zone": r["zone"],
                "target_area_m2": r["target_area_m2"],
                "min_width_m": r["min_width_m"],
                "priority": _priority_for(r["type"]),
                "needs_exterior_wall": r["needs_exterior_wall"],
                "needs_window": r["needs_window"],
                "needs_egress": r["needs_egress"],
                "adjacent_to": [],
                "not_adjacent_to": [],
            }
        )

    by_type: dict[str, list[dict]] = {}
    for r in rooms_payload:
        by_type.setdefault(r["type"], []).append(r)

    # 3. Apply adjacency rules from the spec text.
    _apply_pair(by_type, rooms_payload, "kitchen", "dining_room", adjacent=True)
    _apply_pair(by_type, rooms_payload, "kitchen", "living_room", adjacent=True)
    _apply_pair(by_type, rooms_payload, "dining_room", "living_room", adjacent=True)
    _apply_pair(by_type, rooms_payload, "mudroom", "kitchen", adjacent=True)
    _apply_pair(by_type, rooms_payload, "garage_single", "mudroom", adjacent=True)
    _apply_pair(by_type, rooms_payload, "garage_double", "mudroom", adjacent=True)
    _apply_pair(by_type, rooms_payload, "powder", "foyer", adjacent=True)
    _apply_pair(by_type, rooms_payload, "powder", "living_room", adjacent=True)
    _apply_pair(by_type, rooms_payload, "powder", "kitchen", adjacent=False)
    _apply_pair(by_type, rooms_payload, "powder", "dining_room", adjacent=False)
    _apply_pair(by_type, rooms_payload, "bedroom", "living_room", adjacent=False)
    _apply_pair(by_type, rooms_payload, "primary_bedroom", "living_room", adjacent=False)

    # Pair primary bedroom with the first full bath.
    primaries = by_type.get("primary_bedroom", [])
    baths = by_type.get("full_bath", [])
    if primaries and baths:
        _link(primaries[0], baths[0], adjacent=True)

    # Cluster bedrooms together.
    bedrooms = (
        by_type.get("primary_bedroom", [])
        + by_type.get("bedroom", [])
        + by_type.get("kids_room", [])
        + by_type.get("guest_room", [])
    )
    for i in range(len(bedrooms) - 1):
        _link(bedrooms[i], bedrooms[i + 1], adjacent=True)

    # Entry adjacencies: link the entry to the first public room.
    public_targets = [r for r in rooms_payload if r["id"] != entry_id and r["zone"] == "public"]
    if public_targets:
        entry_room = next(r for r in rooms_payload if r["id"] == entry_id)
        _link(entry_room, public_targets[0], adjacent=True)

    program_dict: dict[str, Any] = {
        "units": "mm",
        "global": {
            "circulation_target_pct": 12,
            "group_wet_rooms": True,
            "primary_entry_side": "south",
        },
        "rooms": rooms_payload,
        "circulation": {
            "entry_room_id": entry_id,
            "notes": f"Deterministic fallback; usable area {usable_area_m2:.1f} m^2.",
        },
    }
    return validate_program_dict(program_dict)


def _pick_entry(rooms_expanded: list[dict]) -> str:
    for r in rooms_expanded:
        if r["type"] == "foyer":
            return r["id"]
    for r in rooms_expanded:
        if r["type"] == "mudroom":
            return r["id"]
    for r in rooms_expanded:
        if r["zone"] == "public":
            return r["id"]
    return rooms_expanded[0]["id"]


_PRIORITIES: dict[str, int] = {
    "primary_bedroom": 1,
    "living_room": 1,
    "kitchen": 1,
    "foyer": 1,
    "full_bath": 2,
    "dining_room": 2,
    "bedroom": 2,
    "kids_room": 2,
    "guest_room": 3,
    "study": 3,
    "family_room": 2,
    "mudroom": 3,
    "laundry": 3,
    "powder": 3,
    "garage_single": 2,
    "garage_double": 2,
    "pantry": 4,
    "walk_in_closet": 4,
    "storage": 4,
    "patio": 5,
    "deck": 5,
    "balcony": 5,
    "porch": 5,
    "sunroom": 3,
    "media_room": 3,
    "home_gym": 4,
    "nursery": 2,
}


def _priority_for(room_type: str) -> int:
    # Default mid-priority for unlisted catalog entries.
    if room_type not in _PRIORITIES:
        spec = CATALOG_BY_TYPE.get(room_type)
        return 3 if spec else 5
    return _PRIORITIES[room_type]


def _apply_pair(
    by_type: dict[str, list[dict]],
    _all: list[dict],
    type_a: str,
    type_b: str,
    *,
    adjacent: bool,
) -> None:
    """Link every instance of type_a to the first instance of type_b."""
    rooms_a = by_type.get(type_a, [])
    rooms_b = by_type.get(type_b, [])
    if not rooms_a or not rooms_b:
        return
    target = rooms_b[0]
    for r in rooms_a:
        if r["id"] == target["id"]:
            continue
        _link(r, target, adjacent=adjacent)


def _link(a: dict, b: dict, *, adjacent: bool) -> None:
    bucket = "adjacent_to" if adjacent else "not_adjacent_to"
    if b["id"] not in a[bucket]:
        a[bucket].append(b["id"])
    if a["id"] not in b[bucket]:
        b[bucket].append(a["id"])


__all__ = ["generate_program", "ROOM_CATALOG"]
