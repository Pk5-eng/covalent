# Covalent: AI Floor Plan Generator (DXF)

**Goal:** A single-flow web tool. An architect draws a rectangular building boundary, selects rooms and quantities, and an AI agent produces an optimized, valid, dimensioned architectural floor plan that exports to clean DXF.

**Repo:** `covalent` (monorepo: `frontend/` + `backend/`).

**Build with:** Claude Code, milestone by milestone.

---

## 0. Read this first: locked decisions and scope

These are settled. Build to them. Do not route around them.

**Architecture**
1. The LLM never outputs geometry. Claude decides the program (which rooms, target sizes from norms, public/private/service zoning) and the room-to-room adjacency graph. A deterministic engine packs the geometry and guarantees validity. If you ever prompt Claude for room coordinates, stop and re-read this.
2. **Layout method is fixed: a slicing-tree representation optimized by simulated annealing, with an architectural cost function.** The representation guarantees rectangular rooms that tile the boundary with no gaps and no overlaps. The annealer optimizes for adjacency, aspect ratio, zoning coherence, daylight, and circulation. Do not substitute greedy subdivision, and do not reach for ML models.

**Scope (downsized on purpose, must be excellent within these limits)**
3. **Export is DXF only.** No DWG. AutoCAD opens DXF natively.
4. **Boundary is rectangular only** for the MVP. L-shapes and free polygons are out of scope.
5. **Editing is limited** to two operations: regenerate, and resize a single room. Nothing else.
6. **No authentication, no onboarding.** Open the link, start drawing. Anonymous session id only.

**Quality target**
7. The target is an optimized-schematic plan: valid, dimensioned, NCS-layered, with honored adjacencies and clean proportions. It is not permit-ready construction documents, and it is not architect-grade naturalism. State this honestly in the UI if needed.

---

## 1. Product summary and user flow

1. **Open link.** Blank canvas, no onboarding.
2. **Draw boundary.** Rectangular footprint. Enter width and depth, or drag, snapped to a 100mm grid.
3. **Select rooms.** Palette of room types with quantity steppers. Running area tally warns when the request exceeds usable area.
4. **Generate.** The architect agent (Claude) returns a program plus adjacency graph. The engine anneals a slicing-tree layout, then produces a validated floor-plan model. The canvas renders it as an architectural drawing.
5. **Edit.** Regenerate for a new optimized layout, or resize one room.
6. **Export DXF.**

---

## 2. Architecture

```
[ Browser: React + Vite ]
   - Rectangular boundary tool (SVG)
   - Room palette + quantity selector
   - Architectural renderer (SVG: poche walls, doors, windows, dims, labels)
   - Edit controls (regenerate, resize one room)
        |
        |  POST boundary + room program (JSON)
        v
[ Backend: FastAPI (Python) ]
   - Architect Agent (Anthropic API)
        -> program + adjacency graph (JSON, NO coordinates)
   - Layout Engine (slicing-tree + simulated annealing)
        -> optimized rectangular layout, then walls/doors/windows
   - Validator (deterministic): no overlaps, full coverage, connectivity
   - DXF Exporter (ezdxf): NCS layers, blocks, real dimensions
        |
        v
[ Returns floor-plan model (JSON) + DXF file ]
```

**Division of labor**
- **Claude = architectural judgment.** Program, area allocation from norms, zoning, adjacency relationships, special requirements (egress, daylight, wet-core grouping). Structured JSON only.
- **Engine = correctness and optimization.** Slicing-tree plus annealing turns the program and adjacency graph into clean rectangular rooms that tile the boundary and score well on the cost function. Pure deterministic code.
- **Validator = the gate.** Geometric checks run on every layout. Nothing renders or exports unless it passes.

---

## 3. Tech stack and repo layout

**Frontend:** React + Vite + TypeScript. Raw SVG for the canvas and renderer with a thin state layer (Zustand or context). The drawing must read as professional line work.

**Backend:** Python 3.11+, FastAPI, uvicorn.

**Engine:** pure Python with `numpy` for the slicing-tree and annealing, `shapely` for polygon operations and validity, `networkx` for the adjacency graph and connectivity checks.

**LLM:** Anthropic API for the architect agent.

**Export:** `ezdxf` for DXF. No DWG tooling.

**Deploy:** Vercel (frontend) + Railway (backend).

```
covalent/
  README.md
  CLAUDE.md                     # the locked constraints + scope, read every session
  docs/
    covalent-build-spec.md      # this file
  frontend/
    src/
      components/
        BoundaryEditor.tsx
        RoomPalette.tsx
        PlanCanvas.tsx
        EditControls.tsx
      lib/
        model.ts                # TS types mirroring the model
        api.ts
        render/                 # SVG helpers: poche, door arc, window, dims
      state/planStore.ts
      App.tsx
    package.json
  backend/
    app/
      main.py
      agent/
        architect.py            # Claude call -> program JSON
        prompts.py              # system prompt (Appendix)
        schema.py               # pydantic models for agent I/O
      engine/
        slicing.py              # slicing-tree (Polish expression) + dimensioning
        anneal.py               # simulated annealing loop + moves
        cost.py                 # architectural cost function
        circulation.py          # corridors + connectivity
        openings.py             # doors + windows
        walls.py                # wall offsetting + merging
        validate.py             # geometric + rule checks (the contract)
      rules/defaults.py         # room catalog, min sizes, adjacency matrix
      export/dxf_export.py      # ezdxf writer
      models.py                 # shared floor-plan data model
    requirements.txt
```

---

## 4. Floor-plan data model

One model flows through the system. Internal units are millimetres. Display units configurable (metric default).

```python
Boundary = {
  "width_mm": int, "depth_mm": int,     # rectangular MVP
  "units_display": "metric"             # "metric" | "imperial"
}

Room = {
  "id": "bedroom_1",
  "type": "bedroom",
  "label": "Bedroom 1",
  "zone": "private",                    # public | private | service
  "polygon": [[x, y], ...],             # filled by the engine, mm, rectangular
  "area_mm2": int,
  "needs_window": True,
  "needs_egress": True
}

Wall = {
  "id": "w_12", "a": [x, y], "b": [x, y],
  "thickness_mm": 115,                  # 230 exterior, 115 interior
  "type": "interior"                    # exterior | interior
}

Opening = {
  "id": "d_3", "kind": "door",          # door | window
  "wall_id": "w_12", "position": 0.5,   # 0..1 along wall
  "width_mm": 900, "swing": "in_left"   # doors only
}

FloorPlan = {
  "boundary": Boundary,
  "rooms": [Room, ...],
  "walls": [Wall, ...],
  "openings": [Opening, ...],
  "meta": { "scale": "1:100", "north_deg": 0, "title": "..." }
}
```

---

## 5. The architect agent (Claude)

**Role:** Given usable area and the room selection, output a design program and adjacency graph. Apply architectural judgment. Never output coordinates.

**Input:** usable area (boundary area minus a wall and circulation allowance) and the room list with counts.

**Output:** strict JSON only, no prose, no markdown fences:

```json
{
  "units": "mm",
  "global": {
    "circulation_target_pct": 12,
    "group_wet_rooms": true,
    "primary_entry_side": "south"
  },
  "rooms": [
    {
      "id": "living_1",
      "type": "living_room",
      "label": "Living Room",
      "zone": "public",
      "target_area_m2": 22,
      "min_width_m": 3.5,
      "priority": 1,
      "needs_exterior_wall": true,
      "needs_window": true,
      "needs_egress": false,
      "adjacent_to": ["dining_1", "entry_1"],
      "not_adjacent_to": ["wc_1"]
    }
  ],
  "circulation": { "entry_room_id": "entry_1", "notes": "..." }
}
```

**Reason about:** zoning (public near entry, private deepest, service buffering), adjacency (kitchen near dining and living, primary bedroom paired with its bath, bedrooms clustered away from noisy public zones, garage to mudroom to kitchen, powder room near public space but never opening into kitchen or dining, wet rooms grouped to share plumbing), area allocation scaled to fit usable area, and special requirements (bedrooms need exterior wall, window, egress).

**Validation:** parse and validate against a pydantic schema, clamp total target area to fit usable area, and confirm adjacencies reference real room ids before passing to the engine.

Full system prompt in the Appendix.

---

## 6. The layout engine (slicing-tree + simulated annealing)

This is the centerpiece and where quality is won. Deterministic. The representation makes invalid layouts impossible; the annealer makes good ones likely.

### 6.1 Representation

A slicing floorplan is built from recursive horizontal (H) and vertical (V) cuts, encoded as a binary tree: leaves are rooms, internal nodes are cut operators. Encode it as a normalized Polish (postfix) expression, for example `12V3H`, which maps one-to-one to a slicing layout (Wong-Liu). This guarantees rectangular rooms with gap-free, overlap-free tiling of the rectangular boundary.

### 6.2 Dimensioning a tree

Given a tree, the boundary, and per-room target areas: at each cut, split the parent rectangle between its two children in proportion to the total target area of each child's subtree, along the cut axis. Clamp each child to its minimum dimension, then renormalize the remainder. Recurse to the leaves. This produces exact room rectangles. Area targets are approximate, so the cost function includes an area-deviation term.

### 6.3 Cost function (the architectural intelligence, keep each term inspectable)

Weighted sum, lower is better:
- **Adjacency:** penalize each `adjacent_to` pair that does not share a wall segment long enough for a door; reward shared-wall length. Penalize `not_adjacent_to` pairs that touch.
- **Aspect ratio:** per room, penalize deviation from a target range (about 1:1 to 1:1.8, hard discomfort past 1:2.5).
- **Zoning:** reward rooms of the same zone forming a contiguous cluster; penalize interleaving.
- **Daylight:** penalize rooms with `needs_exterior_wall` that touch no boundary edge.
- **Area deviation:** penalize rooms far from their target area.
- **Circulation:** penalize layouts where rooms are not reachable from the entry, or where reaching private rooms requires passing through other private rooms.

Expose the weights in `rules/defaults.py`. Tuning these weights is how the architect controls what "good" means.

### 6.4 Annealing loop

- Moves on the normalized Polish expression: swap two adjacent operands, complement a chain of operators, swap an adjacent operand and operator. Optionally perturb area proportions.
- Geometric cooling schedule. Derive the start temperature from the average cost change of random moves. Accept worse moves with the standard Metropolis probability.
- Multiple restarts from different random trees. Keep the lowest-cost valid layout.

### 6.5 Finishing passes (after the best layout is chosen)

1. Snap all wall lines to the 100mm grid.
2. Circulation and connectivity: insert a corridor or spine where needed, confirm every room is reachable from the entry, repair if not.
3. Doors: on shared walls between graph-adjacent rooms, offset from corners, widths per type.
4. Windows: on exterior walls of rooms needing daylight, sized to the glazing rule, bedroom egress flagged.
5. Walls: offset room rectangles to wall thickness (exterior 230mm, interior 115mm), merge shared interior walls.
6. Run `validate.py`. Return the `FloorPlan`.

### 6.6 Honest limits

Slicing trees cannot represent every layout (some pinwheel arrangements are not sliceable). The result is optimized-schematic, not naturalistic. This is the accepted ceiling for the scope.

---

## 7. Architectural rules and defaults

Illustrative defaults in `rules/defaults.py`, configurable. Metric-leaning (NBC-style); imperial (IRC-style) noted. Real projects need jurisdiction-specific rules.

### Room catalog (include all)

| Room type | Zone | Target (m^2) | Min area (m^2) | Min width (m) | Window | Egress |
|---|---|---|---|---|---|---|
| Foyer / entry | public | 4 | 2 | 1.5 | optional | no |
| Living room | public | 22 | 14 | 3.5 | yes | no |
| Family room | public | 18 | 12 | 3.2 | yes | no |
| Dining room | public | 14 | 9 | 3.0 | yes | no |
| Kitchen | public | 12 | 7 | 2.4 | yes | no |
| Pantry | service | 3 | 1.5 | 1.2 | no | no |
| Primary bedroom | private | 18 | 12 | 3.0 | yes | yes |
| Bedroom | private | 13 | 10 | 2.7 | yes | yes |
| Kids room | private | 12 | 9 | 2.7 | yes | yes |
| Nursery | private | 9 | 7 | 2.4 | yes | yes |
| Home office / study | private | 10 | 7 | 2.4 | yes | no |
| Guest room | private | 12 | 9 | 2.7 | yes | yes |
| Full bathroom | service | 5 | 3.5 | 1.8 | optional | no |
| Half bath / powder | service | 2 | 1.4 | 1.0 | optional | no |
| Walk-in closet | private | 4 | 2 | 1.2 | no | no |
| Laundry / utility | service | 5 | 3 | 1.8 | optional | no |
| Mudroom | service | 5 | 3 | 1.5 | optional | no |
| Garage (single) | service | 18 | 15 | 3.0 | no | no |
| Garage (double) | service | 36 | 32 | 5.5 | no | no |
| Gallery / hallway | circulation | varies | n/a | 1.0 | optional | no |
| Patio | exterior | 12 | 6 | 2.4 | n/a | no |
| Deck | exterior | 14 | 6 | 2.4 | n/a | no |
| Balcony | exterior | 5 | 3 | 1.2 | n/a | no |
| Porch | exterior | 6 | 3 | 1.5 | n/a | no |
| Sunroom | public | 12 | 8 | 2.7 | yes | no |
| Media room | public | 16 | 11 | 3.2 | optional | no |
| Home gym | private | 14 | 9 | 3.0 | optional | no |
| Storage | service | 4 | 1.5 | 1.0 | no | no |

Exterior rooms attach to a boundary edge and have no interior wall on the open side.

### Zoning
Public near entry, private deepest, service buffering.

### Adjacency weights (positive attract, negative repel)
Kitchen-dining +3, kitchen-living +2, dining-living +2, primary bedroom-its bath +3, bedroom-bedroom +1, garage-mudroom +3, mudroom-kitchen +2, powder-living/entry +2, powder-kitchen/dining -2, laundry-bedrooms +1, laundry-service +2, bedrooms-noisy public -2, wet rooms cluster +1 per pair.

### Circulation
Target under 15 percent of gross area. No pass-through bedrooms.

### Daylight
Habitable rooms need a window. Default glazing 10 percent of floor area (NBC) or 8 percent with 4 percent openable (IRC). Bedrooms need an egress window.

### Walls
Exterior 230mm, interior 115mm.

### Doors and corridors
Entry door 1000mm, internal 900mm, bathroom 750mm. Corridor min width 1000mm.

### Units and jurisdiction
Store in mm. Display toggle metric or imperial. Put jurisdiction values behind a config object.

---

## 8. Architectural renderer

Two jobs: the rectangular boundary tool and the architectural drawing. The drawing must read as professional line work.

**Boundary tool:** enter width and depth or drag, snap to 100mm grid, live area readout.

**Room palette:** grouped by zone, quantity steppers, running area tally with an over-budget warning.

**Drawing (SVG):**
- Walls as filled poche, exterior heavier than interior.
- Doors as a wall gap plus a quarter-circle swing arc.
- Windows as a wall gap with parallel lines across the opening.
- Dimensions as lines with terminators and extension lines, overall plus per room.
- Room labels: name plus area, for example "BEDROOM 1 / 12.5 m^2".
- North arrow, scale bar, simple title block.
- Line weight hierarchy: exterior walls heaviest, then interior, then openings and fixtures, then dimensions and text.

**Map elements to NCS / AIA layer names now** (these become DXF layers): `A-WALL`, `A-WALL-EXTR`, `A-DOOR`, `A-GLAZ`, `A-FLOR-FIXT`, `A-AREA-IDEN`, `A-ANNO-DIMS`, `A-ANNO-TEXT`, `A-ANNO-TTLB`.

---

## 9. Editing (MVP, limited on purpose)

Only two operations. Validate after each so the model is never invalid.

1. **Regenerate.** Re-run annealing from a new random seed for a different optimized layout.
2. **Resize one room.** Keep the existing slicing-tree topology, change that room's target area, re-run the dimensioning pass (Section 6.2), re-run the finishing passes. This keeps the layout stable so the change is predictable.

No wall dragging, no add or remove room, no swaps. Those are out of scope.

---

## 10. DXF export

Use `ezdxf`. Produce a real CAD drawing, not lines plus text.

- First confirm the ezdxf features you will use exist in the installed version.
- Set units (`$INSUNITS`) to millimetres (4).
- Create the NCS layers from Section 8 with sensible colors and linetypes.
- Walls as HATCH SOLID poche on the wall layers.
- Doors and windows as `BLOCK` definitions inserted as block references.
- Dimensions as real `DIMENSION` entities, editable in AutoCAD, not static lines and text.
- Labels as `MTEXT` on `A-AREA-IDEN`, notes on `A-ANNO-TEXT`.
- Save as R2018.
- Add a check that the file opens in a DXF reader.

No DWG. AutoCAD opens DXF natively and can save as DWG if a user needs it.

---

## 11. Build sequence (prompt Claude Code in this order)

Each step is independently runnable with an acceptance check. Start a fresh session per step, let CLAUDE.md carry the constraints, plan before coding, commit working state.

**Step 0. Setup.** Read this spec. Create CLAUDE.md with the Section 0 constraints and scope. Give a build plan and file structure. No code yet.

**Step 1. Scaffolding.** Monorepo, Vite + React + TS frontend, FastAPI backend, one end-to-end round trip. Show how to run locally.

**Step 2. Input.** Rectangular boundary tool plus room palette from Section 7, output a valid boundary and room program as JSON (Section 4).

**Step 3. Architect agent.** Claude call with the Appendix prompt, output program plus adjacency graph, validated against a pydantic schema, no coordinates. Add a 3-bedroom test.

**Step 4. Engine (build incrementally, render an image and run validate.py at every sub-step, do not advance until it passes):**
  1. `validate.py` first (no overlaps, full coverage, connectivity). This is the contract.
  2. Slicing-tree representation and dimensioning that tiles the rectangle for N rooms. Render. Validate.
  3. The cost function with each term inspectable (Section 6.3).
  4. Simulated annealing with the three Polish-expression moves, cooling, and multi-restart keep-best. Render the best.
  5. Circulation, doors, windows, walls (Section 6.5).
  Stop after sub-step 2 for the first visual check, and again after sub-step 4.

**Step 5. Renderer.** Architectural SVG per Section 8 with NCS layer mapping.

**Step 6. Editing.** Regenerate and resize-one-room only (Section 9). Validate after each.

**Step 7. DXF export.** ezdxf per Section 10.

---

## 12. Definition of done

- Open link, draw a rectangular boundary, pick rooms, generate an optimized valid dimensioned plan, regenerate or resize one room, export DXF, all with no login.
- Plans honor zoning and adjacency, meet minimum sizes, keep circulation under 15 percent, and have every room reachable.
- The plan renders as professional architectural line work.
- The DXF opens correctly in a CAD viewer with NCS layers, correct scale, and editable dimensions.

---

## 13. Risks and gotchas

- Do not ask Claude for coordinates. Program and adjacency only.
- Do not substitute a greedy or ML method for the engine. Slicing-tree plus annealing is the decided method.
- The cost function and validator are where quality lives. Review the cost terms and tune the weights yourself; verify layouts by eye on rendered images, not by trusting the engine's own success message.
- Validate the agent's JSON against the schema and clamp to the boundary. Never trust raw model output to fit.
- Code values are illustrative. Keep the jurisdiction profile configurable.
- Confirm ezdxf features exist in the installed version before using them.

---

## Appendix: architect agent system prompt

```
You are a senior residential architect producing a design program for an
automated floor-plan engine. You apply established residential planning
practice. You do NOT draw the plan and you NEVER output coordinates.

You receive:
- the total usable floor area (square metres),
- a list of requested rooms with quantities,
- a reference table of typical room areas, minimum sizes, and adjacency
  guidance.

Produce a design program that the engine will pack into the building
boundary. Reason about:

1. ZONING. Separate public (living, dining, kitchen), private (bedrooms,
   ensuite baths), and service (garage, laundry, utility, mudroom). Place
   public near the entry, private deepest, service buffering the rest.

2. AREA ALLOCATION. Start from typical areas, then scale so the total of all
   room target areas fits within the usable area. Never exceed it. Respect
   each room's minimum area and minimum width.

3. ADJACENCY. Encode which rooms should sit next to each other and which must
   not. Kitchen near dining and living. Primary bedroom paired with its
   bathroom. Bedrooms clustered and kept away from noisy public rooms. Garage
   to mudroom to kitchen. Powder room near public space but never opening into
   kitchen or dining. Group wet rooms to share plumbing walls.

4. REQUIREMENTS. Bedrooms need an exterior wall, a window, and egress.
   Habitable rooms need daylight. Mark these flags per room.

5. CIRCULATION. Set a circulation target as a percentage of floor area
   (default 12). Identify the entry room.

Output STRICT JSON only. No prose. No markdown code fences. Match this schema
exactly:

{
  "units": "mm",
  "global": {
    "circulation_target_pct": <int>,
    "group_wet_rooms": <bool>,
    "primary_entry_side": "<north|south|east|west>"
  },
  "rooms": [
    {
      "id": "<unique_id>",
      "type": "<catalog_type>",
      "label": "<human label>",
      "zone": "<public|private|service>",
      "target_area_m2": <number>,
      "min_width_m": <number>,
      "priority": <int, 1 highest>,
      "needs_exterior_wall": <bool>,
      "needs_window": <bool>,
      "needs_egress": <bool>,
      "adjacent_to": ["<room_id>", ...],
      "not_adjacent_to": ["<room_id>", ...]
    }
  ],
  "circulation": { "entry_room_id": "<room_id>", "notes": "<short note>" }
}

If the requested rooms cannot fit the usable area at their minimums, scale down
proportionally toward minimums and note the constraint in circulation.notes.
Do not invent rooms the user did not request. Do not output anything except
the JSON object.
```
