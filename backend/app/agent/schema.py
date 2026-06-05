"""Pydantic schema for the architect agent's JSON output.

Mirrors `Program*` in app.models but ships explicit validators that
enforce: (1) ids unique, (2) adjacency references real ids, (3) no
coordinates accidentally leaked, (4) total target area within usable
area, scaling proportionally if not.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.models import (
    Program,
    ProgramCirculation,
    ProgramGlobal,
    ProgramRoom,
)
from app.rules.defaults import CATALOG_BY_TYPE


class AgentOutputError(ValueError):
    """The agent's response could not be parsed into a valid program."""


def parse_program_json(raw: str) -> Program:
    """Strict parse of the agent's response into a `Program`.

    Tolerates a single layer of markdown code-fences in case the model
    slipped, but never accepts prose.
    """
    text = raw.strip()
    if text.startswith("```"):
        # strip optional ```json ... ``` fence
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AgentOutputError(f"agent response is not JSON: {e}") from e

    return validate_program_dict(data)


def validate_program_dict(data: dict[str, Any]) -> Program:
    if not isinstance(data, dict):
        raise AgentOutputError("agent response must be a JSON object")

    _check_no_coordinates(data)

    try:
        program = Program.model_validate(data)
    except ValidationError as e:
        raise AgentOutputError(f"program does not match schema: {e}") from e

    ids = [r.id for r in program.rooms]
    if len(set(ids)) != len(ids):
        raise AgentOutputError("room ids are not unique")

    for r in program.rooms:
        if r.type not in CATALOG_BY_TYPE:
            raise AgentOutputError(f"unknown room type: {r.type}")
        for ref in r.adjacent_to + r.not_adjacent_to:
            if ref not in ids:
                raise AgentOutputError(
                    f"room {r.id!r} references unknown id {ref!r}"
                )
            if ref == r.id:
                raise AgentOutputError(f"room {r.id!r} lists itself in adjacency")

    if program.circulation.entry_room_id not in ids:
        raise AgentOutputError(
            f"entry_room_id {program.circulation.entry_room_id!r} not in rooms"
        )

    return program


_FORBIDDEN_KEYS = {"polygon", "x", "y", "coordinates", "coords", "points"}


def _check_no_coordinates(node: Any) -> None:
    """Walk the structure and reject any geometry-shaped keys.

    The agent must never output coordinates. If it does, we fail hard
    rather than silently strip them.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _FORBIDDEN_KEYS:
                raise AgentOutputError(
                    f"agent must not output coordinates (found key {k!r})"
                )
            _check_no_coordinates(v)
    elif isinstance(node, list):
        for v in node:
            _check_no_coordinates(v)


def clamp_to_usable_area(program: Program, usable_area_m2: float) -> Program:
    """Scale all target areas down proportionally if their sum exceeds usable.

    Respects per-room minimums where possible. If even the minimums exceed
    the usable area, leave them alone — the engine will surface that as
    a validation failure rather than silently lying.
    """
    total = sum(r.target_area_m2 for r in program.rooms)
    if total <= usable_area_m2 or total <= 0:
        return program

    # First pass: proportional scale.
    scale = usable_area_m2 / total
    new_rooms: list[ProgramRoom] = []
    for r in program.rooms:
        spec = CATALOG_BY_TYPE.get(r.type)
        floor = spec.min_m2 if spec else 0
        scaled = max(floor, round(r.target_area_m2 * scale, 2))
        new_rooms.append(r.model_copy(update={"target_area_m2": scaled}))

    return program.model_copy(
        update={
            "rooms": new_rooms,
            "circulation": ProgramCirculation(
                entry_room_id=program.circulation.entry_room_id,
                notes=(
                    program.circulation.notes
                    + (" Targets clamped to usable area." if program.circulation.notes
                       else "Targets clamped to usable area.")
                ),
            ),
        }
    )


__all__ = [
    "AgentOutputError",
    "Program",
    "ProgramCirculation",
    "ProgramGlobal",
    "ProgramRoom",
    "clamp_to_usable_area",
    "parse_program_json",
    "validate_program_dict",
]
