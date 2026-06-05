import { usePlanStore } from "../state/planStore";

const GRID_MM = 100;
const MIN_MM = 3000;
const MAX_MM = 30000;

function clampSnap(value: number): number {
  if (!Number.isFinite(value)) return MIN_MM;
  const snapped = Math.round(value / GRID_MM) * GRID_MM;
  return Math.max(MIN_MM, Math.min(MAX_MM, snapped));
}

export function BoundaryInputs() {
  const boundary = usePlanStore((s) => s.boundary);
  const setBoundary = usePlanStore((s) => s.setBoundary);

  return (
    <div>
      <div className="section-title">Boundary (rectangular)</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label style={{ fontSize: 12 }}>
          Width (m)
          <input
            type="number"
            step={0.1}
            min={MIN_MM / 1000}
            max={MAX_MM / 1000}
            value={(boundary.width_mm / 1000).toFixed(1)}
            onChange={(e) =>
              setBoundary({ width_mm: clampSnap(parseFloat(e.target.value) * 1000) })
            }
          />
        </label>
        <label style={{ fontSize: 12 }}>
          Depth (m)
          <input
            type="number"
            step={0.1}
            min={MIN_MM / 1000}
            max={MAX_MM / 1000}
            value={(boundary.depth_mm / 1000).toFixed(1)}
            onChange={(e) =>
              setBoundary({ depth_mm: clampSnap(parseFloat(e.target.value) * 1000) })
            }
          />
        </label>
      </div>
      <div className="muted" style={{ marginTop: 6 }}>
        Snapped to 100 mm grid. Footprint: {((boundary.width_mm * boundary.depth_mm) / 1_000_000).toFixed(1)} m².
      </div>
    </div>
  );
}
