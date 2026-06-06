"""Architectural cost function (Step 4.3 of the spec).

Each term lives in its own function and is exposed in `CostBreakdown` so
weights can be tuned by eye on rendered layouts. Lower is better.

Terms (Section 6.3):
    - adjacency:    penalize each `adjacent_to` pair that lacks a shared
                    wall long enough for a door; reward shared-wall length;
                    penalize `not_adjacent_to` pairs that touch.
    - aspect_ratio: per room, penalize outside the comfort band; hard past
                    the discomfort threshold.
    - zoning:       reward same-zone rooms forming a contiguous cluster.
    - daylight:     penalize rooms with `needs_exterior_wall` that touch
                    no boundary edge.
    - area_dev:     penalize rooms far from their target area.
    - circulation:  penalize layouts where rooms are not reachable from the
                    entry or where private rooms require passing through
                    other private rooms.
    - min_dim:      heavy penalty for room rectangles below their minimum
                    dimensions (a safety net for when annealing cheats).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
from shapely.geometry import LineString, Polygon, box

from app.engine.slicing import Rect
from app.rules.defaults import (
    DEFAULT_COST_WEIGHTS,
    CostWeights,
    ORIENTATION_PREFERENCE,
    opposite_side,
)

# Door-length threshold: a shared wall shorter than this can't accept a door.
DOOR_THRESHOLD_MM = 900


@dataclass
class CostBreakdown:
    """Each term exposed individually so weights can be tuned."""

    adjacency: float = 0.0
    aspect_ratio: float = 0.0
    zoning: float = 0.0
    daylight: float = 0.0
    area_deviation: float = 0.0
    circulation: float = 0.0
    entry_position: float = 0.0
    orientation: float = 0.0
    privacy_buffer: float = 0.0
    garage_corner: float = 0.0
    min_dim_violation: float = 0.0

    weighted_total: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "adjacency": self.adjacency,
            "aspect_ratio": self.aspect_ratio,
            "zoning": self.zoning,
            "daylight": self.daylight,
            "area_deviation": self.area_deviation,
            "circulation": self.circulation,
            "entry_position": self.entry_position,
            "orientation": self.orientation,
            "privacy_buffer": self.privacy_buffer,
            "garage_corner": self.garage_corner,
            "min_dim_violation": self.min_dim_violation,
            "weighted_total": self.weighted_total,
            "details": self.details,
        }


def evaluate_cost(
    rects: dict[str, Rect],
    program_rooms: list[dict],
    boundary_w: float,
    boundary_h: float,
    weights: CostWeights = DEFAULT_COST_WEIGHTS,
    entry_room_id: str | None = None,
    primary_entry_side: str = "south",
) -> CostBreakdown:
    """Score a layout. All work is deterministic and operator-free here."""
    by_id = {r["id"]: r for r in program_rooms}
    polys = {rid: _poly(rect) for rid, rect in rects.items()}
    boundary = box(0, 0, boundary_w, boundary_h)

    b = CostBreakdown()

    # ---------- shared adjacency graph ----------
    shared = _shared_walls(polys)

    # adjacency penalty/reward
    b.adjacency = _adjacency_term(by_id, shared, b.details)

    # aspect ratio
    b.aspect_ratio = _aspect_term(rects, weights, b.details)

    # zoning coherence
    b.zoning = _zoning_term(by_id, shared, b.details)

    # daylight (boundary contact for needs_exterior_wall)
    b.daylight = _daylight_term(by_id, polys, boundary, b.details)

    # area deviation
    b.area_deviation = _area_dev_term(by_id, rects, b.details)

    # circulation reachability
    b.circulation = _circulation_term(
        by_id, shared, entry_room_id, b.details
    )

    # entry-on-exterior
    b.entry_position = _entry_position_term(
        by_id, polys, boundary_w, boundary_h, entry_room_id, b.details
    )

    # orientation: public rooms toward entry side, private toward opposite
    b.orientation = _orientation_term(
        by_id, polys, boundary_w, boundary_h, primary_entry_side, b.details
    )

    # privacy buffer: bedrooms shouldn't open straight onto public rooms
    b.privacy_buffer = _privacy_buffer_term(by_id, shared, b.details)

    # garage prefers a perimeter corner, not the middle of the floor
    b.garage_corner = _garage_corner_term(
        by_id, polys, boundary_w, boundary_h, b.details
    )

    # minimum-dimension violations (mins came from spec; should never trigger
    # if dimensioning honored them, but a safety net for resize/edits).
    b.min_dim_violation = _min_dim_term(by_id, rects, b.details)

    b.weighted_total = (
        weights.adjacency * b.adjacency
        + weights.aspect_ratio * b.aspect_ratio
        + weights.zoning * b.zoning
        + weights.daylight * b.daylight
        + weights.area_deviation * b.area_deviation
        + weights.circulation * b.circulation
        + weights.entry_position * b.entry_position
        + weights.orientation * b.orientation
        + weights.privacy_buffer * b.privacy_buffer
        + weights.garage_corner * b.garage_corner
        + weights.min_dim_violation * b.min_dim_violation
    )
    return b


# ----------------------------------------------------------------------
# Term implementations
# ----------------------------------------------------------------------


def _poly(rect: Rect) -> Polygon:
    return box(rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)


def _shared_walls(polys: dict[str, Polygon]) -> dict[tuple[str, str], float]:
    """Return shared-wall length for every pair (sorted-id tuple)."""
    ids = list(polys.keys())
    out: dict[tuple[str, str], float] = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            inter = polys[ids[i]].boundary.intersection(polys[ids[j]].boundary)
            length = float(getattr(inter, "length", 0.0))
            if length > 0:
                key = tuple(sorted((ids[i], ids[j])))
                out[key] = length  # type: ignore[assignment]
    return out


def _adjacency_term(
    by_id: dict[str, dict],
    shared: dict[tuple[str, str], float],
    details: dict,
) -> float:
    """Score each unordered pair exactly once."""
    pen = 0.0
    detail = {"missing": [], "satisfied": [], "violations": []}

    # Build set-of-pairs for required-positive and required-negative.
    pos_pairs: set[tuple[str, str]] = set()
    neg_pairs: set[tuple[str, str]] = set()
    for r in by_id.values():
        for ref in r.get("adjacent_to", []):
            if ref in by_id:
                pos_pairs.add(tuple(sorted((r["id"], ref))))  # type: ignore[arg-type]
        for ref in r.get("not_adjacent_to", []):
            if ref in by_id:
                neg_pairs.add(tuple(sorted((r["id"], ref))))  # type: ignore[arg-type]

    for key in pos_pairs:
        length = shared.get(key, 0.0)
        if length < DOOR_THRESHOLD_MM:
            pen += 1.0 if length == 0 else 0.5
            detail["missing"].append({"pair": list(key), "shared_mm": length})
        else:
            pen -= min(length / 5000, 0.5)
            detail["satisfied"].append({"pair": list(key), "shared_mm": length})

    for key in neg_pairs:
        length = shared.get(key, 0.0)
        if length > 0:
            pen += 1.0 + length / 5000
            detail["violations"].append({"pair": list(key), "shared_mm": length})

    details["adjacency"] = detail
    return pen


def _aspect_term(
    rects: dict[str, Rect],
    weights: CostWeights,
    details: dict,
) -> float:
    pen = 0.0
    per_room = {}
    for rid, rect in rects.items():
        if rect.w <= 0 or rect.h <= 0:
            pen += 5
            per_room[rid] = 5
            continue
        ratio = max(rect.w, rect.h) / min(rect.w, rect.h)
        if ratio <= weights.aspect_target_max:
            r_pen = 0.0
        elif ratio <= weights.aspect_hard_max:
            r_pen = (ratio - weights.aspect_target_max) / (
                weights.aspect_hard_max - weights.aspect_target_max
            )
        else:
            r_pen = 1 + (ratio - weights.aspect_hard_max)
        pen += r_pen
        if r_pen > 0:
            per_room[rid] = round(ratio, 2)
    details["aspect_ratio"] = per_room
    return pen


def _zoning_term(
    by_id: dict[str, dict],
    shared: dict[tuple[str, str], float],
    details: dict,
) -> float:
    g = nx.Graph()
    g.add_nodes_from(by_id.keys())
    for (a, b), length in shared.items():
        if length > DOOR_THRESHOLD_MM / 2:
            g.add_edge(a, b)

    zones: dict[str, list[str]] = {}
    for rid, r in by_id.items():
        zones.setdefault(r["zone"], []).append(rid)

    pen = 0.0
    per_zone = {}
    for zone, ids in zones.items():
        if len(ids) <= 1:
            continue
        sub = g.subgraph(ids)
        components = list(nx.connected_components(sub))
        # Penalty grows with the number of separate clusters.
        clusters = len(components)
        pen += clusters - 1
        per_zone[zone] = clusters
    details["zoning"] = per_zone
    return pen


def _daylight_term(
    by_id: dict[str, dict],
    polys: dict[str, Polygon],
    boundary: Polygon,
    details: dict,
) -> float:
    pen = 0.0
    starved = []
    for rid, r in by_id.items():
        if not r.get("needs_exterior_wall") and not r.get("needs_window"):
            continue
        boundary_contact = polys[rid].boundary.intersection(boundary.boundary)
        length = float(getattr(boundary_contact, "length", 0.0))
        if length < 1.0:  # no contact at all
            pen += 1.0
            starved.append(rid)
        elif length < 1500:
            pen += 0.3  # too small to host a real window
    details["daylight"] = {"starved": starved}
    return pen


def _area_dev_term(
    by_id: dict[str, dict],
    rects: dict[str, Rect],
    details: dict,
) -> float:
    pen = 0.0
    per_room = {}
    for rid, r in by_id.items():
        rect = rects[rid]
        actual = rect.w * rect.h
        target = r["target_area_m2"] * 1_000_000
        if target <= 0:
            continue
        dev = (actual - target) / target
        pen += dev * dev  # squared deviation
        per_room[rid] = round(dev, 2)
    details["area_deviation"] = per_room
    return pen


def _circulation_term(
    by_id: dict[str, dict],
    shared: dict[tuple[str, str], float],
    entry_room_id: str | None,
    details: dict,
) -> float:
    g = nx.Graph()
    g.add_nodes_from(by_id.keys())
    for (a, b), length in shared.items():
        if length > DOOR_THRESHOLD_MM:
            g.add_edge(a, b)

    pen = 0.0

    if entry_room_id and entry_room_id in g:
        # Unreachable rooms
        reachable = nx.node_connected_component(g, entry_room_id)
        unreachable = set(by_id) - reachable
        pen += 2 * len(unreachable)
        details["circulation"] = {"unreachable": sorted(unreachable)}
        # No private rooms reached only via other private rooms.
        bad_paths: list[list[str]] = []
        for rid, r in by_id.items():
            if r["zone"] != "private" or rid == entry_room_id or rid not in reachable:
                continue
            try:
                path = nx.shortest_path(g, entry_room_id, rid)
            except nx.NetworkXNoPath:
                continue
            interior = [p for p in path[1:-1] if by_id[p]["zone"] == "private"]
            if interior:
                pen += 0.5 * len(interior)
                bad_paths.append(path)
        details.setdefault("circulation", {})["pass_through"] = bad_paths
    else:
        pen += 1
        details["circulation"] = {"no_entry": True}
    return pen


def _entry_position_term(
    by_id: dict[str, dict],
    polys: dict[str, Polygon],
    boundary_w: float,
    boundary_h: float,
    entry_room_id: str | None,
    details: dict,
) -> float:
    """Entry room must touch the boundary for at least a door's width.

    Without this term the slicing tree happily lands the foyer in the
    middle of the floor, which makes no architectural sense — you can't
    walk into your house through an interior wall.
    """
    if not entry_room_id or entry_room_id not in polys:
        details["entry_position"] = {"no_entry": True}
        return 0.0

    entry_poly = polys[entry_room_id]
    boundary = box(0, 0, boundary_w, boundary_h)
    contact = entry_poly.boundary.intersection(boundary.boundary)
    contact_len = float(getattr(contact, "length", 0.0))

    pen = 0.0
    detail: dict = {"room": entry_room_id, "contact_mm": contact_len}
    if contact_len < DOOR_THRESHOLD_MM:
        # No room for a front door on the boundary — heavy penalty.
        pen += 2.0 if contact_len == 0 else 1.0
        detail["status"] = "interior"
    else:
        detail["status"] = "ok"
    details["entry_position"] = detail
    return pen


def _side_contact_length(poly: Polygon, side: str, w: float, h: float) -> float:
    """How much of the room's boundary lies on the given side of the building."""
    # The boundary side is a single LineString.
    if side == "south":
        # In screen coords y grows down; "south" = bottom = y=h.
        line = LineString([(0, h), (w, h)])
    elif side == "north":
        line = LineString([(0, 0), (w, 0)])
    elif side == "east":
        line = LineString([(w, 0), (w, h)])
    else:  # west
        line = LineString([(0, 0), (0, h)])
    contact = poly.boundary.intersection(line)
    return float(getattr(contact, "length", 0.0))


def _orientation_term(
    by_id: dict[str, dict],
    polys: dict[str, Polygon],
    boundary_w: float,
    boundary_h: float,
    primary_entry_side: str,
    details: dict,
) -> float:
    """Public rooms want the entry side (street + sun); private rooms the opposite.

    The penalty is the missed opportunity: a room that prefers a side and
    has zero contact pays 1.0; a room that has a long contact on the
    preferred side pays nothing. The annealer will pivot the layout to
    line preferences up.
    """
    opp = opposite_side(primary_entry_side)
    pen = 0.0
    detail: dict = {}
    for rid, r in by_id.items():
        pref = ORIENTATION_PREFERENCE.get(r["type"])
        if pref is None:
            continue
        if pref == "entry_side":
            want = primary_entry_side
        elif pref == "opposite_entry":
            want = opp
        else:
            # "side" — give east or west, whichever is longer
            east_contact = _side_contact_length(polys[rid], "east", boundary_w, boundary_h)
            west_contact = _side_contact_length(polys[rid], "west", boundary_w, boundary_h)
            best = max(east_contact, west_contact)
            if best < 500:
                pen += 0.5
                detail[rid] = {"pref": "side", "contact_mm": best}
            continue
        contact = _side_contact_length(polys[rid], want, boundary_w, boundary_h)
        # Normalize: target = 2 m of contact = no penalty.
        if contact < 2000:
            shortfall = (2000 - contact) / 2000
            pen += shortfall
            detail[rid] = {"pref": want, "contact_mm": contact}
    details["orientation"] = detail
    return pen


def _privacy_buffer_term(
    by_id: dict[str, dict],
    shared: dict[tuple[str, str], float],
    details: dict,
) -> float:
    """Bedrooms / bathrooms should not share a long open wall with public rooms.

    Penalizes shared-wall length between a private/service room and a
    public room, except when one of them is circulation (gallery/foyer)
    which is the architectural buffer.
    """
    pen = 0.0
    violators = []
    for (a, b), length in shared.items():
        if length < 500:
            continue
        za = by_id.get(a, {}).get("zone", "")
        zb = by_id.get(b, {}).get("zone", "")
        ta = by_id.get(a, {}).get("type", "")
        tb = by_id.get(b, {}).get("type", "")
        if "circulation" in (za, zb):
            continue  # gallery/hall buffers are fine
        if {za, zb} == {"private", "public"}:
            # tolerate short shared edge but penalize long ones
            extra = max(0.0, length - 1000) / 5000
            pen += extra
            if extra > 0:
                violators.append({"pair": [a, b], "shared_mm": length, "types": [ta, tb]})
    details["privacy_buffer"] = violators
    return pen


def _garage_corner_term(
    by_id: dict[str, dict],
    polys: dict[str, Polygon],
    boundary_w: float,
    boundary_h: float,
    details: dict,
) -> float:
    """Garage should sit at a perimeter corner (two-side contact)."""
    pen = 0.0
    detail = {}
    for rid, r in by_id.items():
        if not r["type"].startswith("garage"):
            continue
        sides = sum(
            1 for s in ("north", "south", "east", "west")
            if _side_contact_length(polys[rid], s, boundary_w, boundary_h) > 1000
        )
        # Reward 2+ sides (corner), penalize 0 (interior) or 1 (mid-edge).
        if sides >= 2:
            continue
        pen += 2 - sides
        detail[rid] = {"sides_on_boundary": sides}
    details["garage_corner"] = detail
    return pen


def _min_dim_term(
    by_id: dict[str, dict],
    rects: dict[str, Rect],
    details: dict,
) -> float:
    pen = 0.0
    violations = {}
    for rid, r in by_id.items():
        rect = rects[rid]
        min_w = r.get("min_width_m", 0) * 1000
        if rect.w + 1 < min_w or rect.h + 1 < min_w:
            pen += 1 + min((min_w - min(rect.w, rect.h)) / 1000, 5)
            violations[rid] = {"got": (rect.w, rect.h), "need_min_side": min_w}
    details["min_dim_violation"] = violations
    return pen


__all__ = ["CostBreakdown", "evaluate_cost", "DOOR_THRESHOLD_MM"]
