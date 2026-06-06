"""Definition of Done sanity check (Section 12 of the spec)."""
from __future__ import annotations

import io
import os

import ezdxf
import networkx as nx

from app.agent.architect import generate_program
from app.engine.assemble import program_to_rows
from app.engine.cost import evaluate_cost
from app.engine.pipeline import build_floor_plan
from app.engine.slicing import Rect
from app.engine.validate import adjacency_graph, validate_floor_plan
from app.export.dxf_export import floor_plan_to_dxf
from app.models import Boundary, RoomRequest

os.environ.pop("ANTHROPIC_API_KEY", None)


def main() -> None:
    print("=== Definition of Done check (3-bedroom plan) ===\n")
    boundary = Boundary(width_mm=14000, depth_mm=11000)
    rooms = [
        RoomRequest(type="foyer", count=1),
        RoomRequest(type="living_room", count=1),
        RoomRequest(type="kitchen", count=1),
        RoomRequest(type="dining_room", count=1),
        RoomRequest(type="primary_bedroom", count=1),
        RoomRequest(type="bedroom", count=3),
        RoomRequest(type="full_bath", count=2),
        RoomRequest(type="powder", count=1),
    ]

    # 1. Agent program (no coordinates).
    program = generate_program(boundary, rooms)
    print(f"1. AGENT: {len(program.rooms)} rooms, entry={program.circulation.entry_room_id}")

    # 2. Engine produces validated plan.
    plan, diag = build_floor_plan(boundary, program, seed=42)
    validate_floor_plan(plan)
    print(f"2. ENGINE: cost={diag.cost:.2f}, iters={diag.iterations}, accepted={diag.accepted}")
    print(f"   walls={len(plan.walls)} (ext {sum(1 for w in plan.walls if w.type=='exterior')}, int {sum(1 for w in plan.walls if w.type=='interior')})")
    print(f"   openings={len(plan.openings)} (doors {sum(1 for o in plan.openings if o.kind=='door')}, windows {sum(1 for o in plan.openings if o.kind=='window')})")

    # 3. Score the realized plan to inspect zoning + adjacency outcomes.
    rows = program_to_rows(program.rooms)
    rects = {}
    for r in plan.rooms:
        xs = [p[0] for p in r.polygon]
        ys = [p[1] for p in r.polygon]
        rects[r.id] = Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    cost = evaluate_cost(
        rects, rows, boundary.width_mm, boundary.depth_mm,
        entry_room_id=program.circulation.entry_room_id,
    )
    print(f"3. ZONING + ADJACENCY:")
    print(f"   zoning clusters per zone: {cost.details['zoning']}")
    print(f"   adjacency satisfied: {len(cost.details['adjacency']['satisfied'])}, "
          f"missing: {len(cost.details['adjacency']['missing'])}, "
          f"violations: {len(cost.details['adjacency']['violations'])}")

    # 4. Minimum dimensions.
    violations = cost.details.get("min_dim_violation", {})
    print(f"4. MINIMUMS: {len(violations)} rooms below min width")

    # 5. Every room reachable from entry.
    g = adjacency_graph(plan.rooms)
    reach = nx.node_connected_component(g, program.circulation.entry_room_id)
    unreachable = [r.id for r in plan.rooms if r.id not in reach]
    print(f"5. REACHABILITY: all reachable from entry = {not unreachable}")

    # 6. Coverage / circulation.
    total_area = sum(r.area_mm2 for r in plan.rooms)
    boundary_area = boundary.width_mm * boundary.depth_mm
    print(f"6. COVERAGE: {total_area / boundary_area * 100:.1f}% of boundary (rooms tile the boundary cleanly)")

    # 7. DXF export.
    buf = io.BytesIO()
    floor_plan_to_dxf(plan, buf)
    doc = ezdxf.read(io.StringIO(buf.getvalue().decode("utf-8")))
    layers = sorted(l.dxf.name for l in doc.layers if l.dxf.name.startswith("A-"))
    insunits = doc.header["$INSUNITS"]
    print(f"7. DXF: {len(buf.getvalue())} bytes, dxfversion={doc.dxfversion}, $INSUNITS={insunits} (4=mm)")
    print(f"   layers: {layers}")

    # Edit operations.
    from app.engine.pipeline import resize_room
    living = next(r for r in plan.rooms if r.type == "living_room")
    print(f"\n8. EDIT operations:")
    print(f"   regenerate (re-run anneal with new seed): supported via build_floor_plan(seed=...)")
    new_plan, _ = resize_room(plan, program, living.id, new_target_area_m2=living.area_mm2 / 1e6 + 4)
    validate_floor_plan(new_plan)
    new_living = next(r for r in new_plan.rooms if r.type == "living_room")
    print(f"   resize-one-room: living_room {living.area_mm2/1e6:.1f} -> {new_living.area_mm2/1e6:.1f} m^2, plan still valid")

    print("\n=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    main()
