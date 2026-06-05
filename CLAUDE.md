# CLAUDE.md — Covalent

Read this every session before writing code. Source of truth is `covalent-build-spec.md` (intended path: `docs/covalent-build-spec.md`). If anything here conflicts with the spec, the spec wins.

---

## 0. Locked constraints and scope

These are settled. Build to them. Do not route around them.

### Architecture (locked)

1. **The LLM never outputs geometry.** Claude decides the program (which rooms, target sizes from norms, public/private/service zoning) and the room-to-room adjacency graph. A deterministic engine packs the geometry and guarantees validity. **If you ever prompt Claude for room coordinates, stop and re-read this.**
2. **Layout method is fixed: a slicing-tree representation (normalized Polish expression) optimized by simulated annealing, with an architectural cost function.** The representation guarantees rectangular rooms that tile the boundary with no gaps and no overlaps. The annealer optimizes for adjacency, aspect ratio, zoning coherence, daylight, and circulation. **Do not substitute greedy subdivision. Do not reach for ML models.**

### Scope (downsized on purpose — be excellent within these limits)

3. **Export is DXF only.** No DWG. AutoCAD opens DXF natively.
4. **Boundary is rectangular only** for the MVP. L-shapes and free polygons are out of scope.
5. **Editing is limited to two operations:** regenerate, and resize a single room. Nothing else (no wall dragging, no add/remove room, no swap).
6. **No authentication, no onboarding.** Open the link, start drawing. Anonymous session id only.

### Quality target

7. The target is an **optimized-schematic plan**: valid, dimensioned, NCS-layered, with honored adjacencies and clean proportions. It is **not** permit-ready construction documents, and it is **not** architect-grade naturalism. State this honestly in the UI if needed.

### Division of labor (do not blur)

- **Claude** = architectural judgment. Program, area allocation from norms, zoning, adjacency relationships, special requirements (egress, daylight, wet-core grouping). Structured JSON only, no prose, no markdown fences.
- **Engine** = correctness and optimization. Slicing-tree + annealing → rectangular rooms tiling the boundary, scored by the cost function. Pure deterministic code.
- **Validator** = the gate. Geometric checks (no overlaps, full coverage, connectivity) run on every layout. Nothing renders or exports unless it passes.

### Non-negotiables / gotchas

- Never ask Claude for coordinates. Program and adjacency only.
- Validate the agent's JSON against a pydantic schema. Clamp to boundary. Never trust raw model output to fit.
- Internal units are **millimetres**. Display toggle metric/imperial.
- Walls: exterior 230mm, interior 115mm. Snap to 100mm grid.
- Slicing trees cannot represent every layout (pinwheels are not sliceable). That is the accepted ceiling.
- Confirm `ezdxf` features exist in the installed version before using them.
- Keep cost-function terms individually inspectable. Tune weights by eye on rendered images, not by trusting an "annealing converged" message.
- Jurisdiction values (NBC vs IRC, glazing %, etc.) live behind a config object.

---

## Build plan (Section 11)

Each step is independently runnable with an acceptance check. Start a fresh session per step. Plan before coding. Commit working state.

- **Step 0 — Setup (this step).** CLAUDE.md with locked constraints + scope. Build plan and file structure. No code.
- **Step 1 — Scaffolding.** Monorepo, Vite + React + TS frontend, FastAPI backend, one end-to-end round trip. Document local run commands.
- **Step 2 — Input.** Rectangular boundary tool + room palette (Section 7). Outputs a valid boundary + room program JSON (Section 4).
- **Step 3 — Architect agent.** Claude call using the Appendix prompt. Outputs program + adjacency graph, validated by pydantic, no coordinates. Add a 3-bedroom test.
- **Step 4 — Engine (incremental, render + validate at each sub-step, do not advance until it passes):**
  1. `validate.py` first (no overlaps, full coverage, connectivity) — this is the contract.
  2. Slicing-tree representation + dimensioning that tiles the rectangle for N rooms. Render. Validate. **First visual checkpoint.**
  3. Cost function with each term inspectable (Section 6.3).
  4. Simulated annealing: three Polish-expression moves, geometric cooling, multi-restart keep-best. Render the best. **Second visual checkpoint.**
  5. Circulation, doors, windows, walls (Section 6.5).
- **Step 5 — Renderer.** Architectural SVG per Section 8 with NCS layer mapping.
- **Step 6 — Editing.** Regenerate and resize-one-room only (Section 9). Validate after each.
- **Step 7 — DXF export.** `ezdxf` per Section 10. Verify file opens in a DXF reader.

### Definition of done (Section 12)

Open link → draw rectangular boundary → pick rooms → generate optimized valid dimensioned plan → regenerate or resize one room → export DXF, no login. Plans honor zoning + adjacency, meet minimums, circulation under 15%, every room reachable. Renders as professional line work. DXF opens in a CAD viewer with NCS layers, correct scale, editable dimensions.

---

## File structure (Section 3)

```
covalent/
  README.md
  CLAUDE.md                       # this file — locked constraints + scope
  docs/
    covalent-build-spec.md        # full spec (currently at repo root, move in Step 1)
  frontend/                       # Vite + React + TypeScript, raw SVG, Zustand
    src/
      components/
        BoundaryEditor.tsx        # rectangular boundary tool (Section 8)
        RoomPalette.tsx           # room steppers + area tally (Section 7)
        PlanCanvas.tsx            # architectural SVG renderer
        EditControls.tsx          # regenerate + resize-one-room (Section 9)
      lib/
        model.ts                  # TS types mirroring backend models
        api.ts                    # POST boundary + program; receive FloorPlan + DXF
        render/                   # SVG helpers: poche, door arc, window, dims
      state/planStore.ts          # plan state
      App.tsx
    package.json
  backend/                        # Python 3.11+, FastAPI, uvicorn
    app/
      main.py                     # FastAPI app, endpoints
      agent/
        architect.py              # Claude call → program JSON
        prompts.py                # Appendix system prompt
        schema.py                 # pydantic I/O models for the agent
      engine/
        slicing.py                # slicing-tree (Polish expression) + dimensioning
        anneal.py                 # simulated annealing loop + moves
        cost.py                   # architectural cost function (inspectable terms)
        circulation.py            # corridors + connectivity repair
        openings.py               # doors + windows placement
        walls.py                  # wall offsetting + merging (230 ext / 115 int)
        validate.py               # geometric + rule checks — THE CONTRACT
      rules/defaults.py           # room catalog, min sizes, adjacency weights, jurisdiction config
      export/dxf_export.py        # ezdxf writer, NCS layers, R2018
      models.py                   # shared FloorPlan data model (Section 4)
    requirements.txt
```

### Tech stack

- **Frontend:** React + Vite + TypeScript, raw SVG, thin state (Zustand or context).
- **Backend:** Python 3.11+, FastAPI, uvicorn.
- **Engine:** `numpy` (slicing-tree + annealing), `shapely` (polygon ops + validity), `networkx` (adjacency graph + connectivity).
- **LLM:** Anthropic API.
- **Export:** `ezdxf` only. No DWG tooling.
- **Deploy:** Vercel (frontend) + Railway (backend).

### NCS / AIA DXF layers (lock these names now)

`A-WALL`, `A-WALL-EXTR`, `A-DOOR`, `A-GLAZ`, `A-FLOR-FIXT`, `A-AREA-IDEN`, `A-ANNO-DIMS`, `A-ANNO-TEXT`, `A-ANNO-TTLB`.
