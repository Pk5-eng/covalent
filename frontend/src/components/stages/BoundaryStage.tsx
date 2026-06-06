import { BoundaryEditor } from "../BoundaryEditor";
import { usePlanStore } from "../../state/planStore";

const GRID_MM = 100;
const MIN_MM = 3000;
const MAX_MM = 30000;

const PRESETS: { label: string; w: number; d: number }[] = [
  { label: "Studio",    w: 6000,  d: 5000 },
  { label: "1-bedroom", w: 9000,  d: 7000 },
  { label: "2-bedroom", w: 12000, d: 9000 },
  { label: "3-bedroom", w: 14000, d: 11000 },
  { label: "4-bedroom", w: 16000, d: 12000 },
  { label: "Large home", w: 20000, d: 15000 },
];

function clampSnap(value: number): number {
  if (!Number.isFinite(value)) return MIN_MM;
  const snapped = Math.round(value / GRID_MM) * GRID_MM;
  return Math.max(MIN_MM, Math.min(MAX_MM, snapped));
}

export function BoundaryStage() {
  const boundary = usePlanStore((s) => s.boundary);
  const setBoundary = usePlanStore((s) => s.setBoundary);
  const goNext = usePlanStore((s) => s.goNext);
  const areaM2 = (boundary.width_mm * boundary.depth_mm) / 1_000_000;

  return (
    <div className="stage">
      <aside className="panel">
        <div className="section">
          <span className="eyebrow">Step 1 of 4</span>
          <h2 className="stage-title">Draw the building boundary</h2>
          <p className="stage-sub">
            Rectangular footprint. Drag the handles in the canvas or type exact
            dimensions. Everything snaps to a 100 mm grid.
          </p>
        </div>

        <div className="section">
          <div className="field-grid">
            <div>
              <label>Width (m)</label>
              <input
                type="number"
                step={0.5}
                min={MIN_MM / 1000}
                max={MAX_MM / 1000}
                value={(boundary.width_mm / 1000).toFixed(1)}
                onChange={(e) =>
                  setBoundary({ width_mm: clampSnap(parseFloat(e.target.value) * 1000) })
                }
              />
            </div>
            <div>
              <label>Depth (m)</label>
              <input
                type="number"
                step={0.5}
                min={MIN_MM / 1000}
                max={MAX_MM / 1000}
                value={(boundary.depth_mm / 1000).toFixed(1)}
                onChange={(e) =>
                  setBoundary({ depth_mm: clampSnap(parseFloat(e.target.value) * 1000) })
                }
              />
            </div>
          </div>

          <div>
            <div className="eyebrow" style={{ marginBottom: 6 }}>Quick sizes</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6 }}>
              {PRESETS.map((p) => {
                const active =
                  boundary.width_mm === p.w && boundary.depth_mm === p.d;
                return (
                  <button
                    key={p.label}
                    className={active ? "primary" : ""}
                    onClick={() => setBoundary({ width_mm: p.w, depth_mm: p.d })}
                    style={{ fontSize: 12, padding: "6px 8px", textAlign: "left" }}
                  >
                    <strong>{p.label}</strong>
                    <span style={{ marginLeft: 6, opacity: 0.7 }}>
                      {p.w / 1000}×{p.d / 1000} m
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="tally">
            <div className="tally-row">
              <span>Footprint area</span>
              <span>{areaM2.toFixed(1)} m²</span>
            </div>
            <div className="tally-row">
              <span>Min boundary</span>
              <span>{MIN_MM / 1000} × {MIN_MM / 1000} m</span>
            </div>
            <div className="tally-row">
              <span>Max boundary</span>
              <span>{MAX_MM / 1000} × {MAX_MM / 1000} m</span>
            </div>
          </div>

          <p className="muted">
            Optimized-schematic plans only — not permit-ready construction documents.
            Rectangular boundary only (locked spec).
          </p>
        </div>

        <div className="panel-actions">
          <button className="primary" onClick={goNext}>
            Continue to rooms →
          </button>
        </div>
      </aside>

      <main className="canvas">
        <BoundaryEditor />
      </main>
    </div>
  );
}
