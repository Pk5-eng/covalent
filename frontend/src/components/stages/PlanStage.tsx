import { useMemo, useState } from "react";
import { PlanCanvas } from "../PlanCanvas";
import { ExportBar } from "../ExportBar";
import { usePlanStore } from "../../state/planStore";

export function PlanStage() {
  const plan = usePlanStore((s) => s.plan);
  const program = usePlanStore((s) => s.program);
  const generating = usePlanStore((s) => s.generating);
  const diagnostics = usePlanStore((s) => s.diagnostics);
  const generateError = usePlanStore((s) => s.generateError);
  const runGenerate = usePlanStore((s) => s.runGenerate);
  const runResize = usePlanStore((s) => s.runResize);
  const startOver = usePlanStore((s) => s.startOver);
  const goBack = usePlanStore((s) => s.goBack);

  const [selectedId, setSelectedId] = useState("");
  const [newTarget, setNewTarget] = useState("");

  const sortedRooms = useMemo(() => {
    if (!plan) return [];
    return [...plan.rooms].sort((a, b) => a.label.localeCompare(b.label));
  }, [plan]);

  const currentTarget = useMemo(() => {
    if (!program || !selectedId) return null;
    return program.rooms.find((r) => r.id === selectedId)?.target_area_m2 ?? null;
  }, [program, selectedId]);

  const parsed = parseFloat(newTarget);

  if (!plan) {
    return (
      <div className="canvas">
        <div className="center-msg">
          <h2>No plan yet</h2>
          <p>Go back and generate one.</p>
          <button onClick={goBack}>← Back</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stage">
      <aside className="panel">
        <div className="section">
          <span className="eyebrow">Step 4 of 4</span>
          <h2 className="stage-title">Refine & export</h2>
          <p className="stage-sub">
            Regenerate for a different layout, resize a single room, or export the
            DXF for AutoCAD.
          </p>
        </div>

        <div className="section">
          <button
            className="primary"
            disabled={generating}
            onClick={() => runGenerate()}
            style={{ width: "100%" }}
          >
            {generating ? "Working…" : "Regenerate layout"}
          </button>
          <p className="muted">Re-runs simulated annealing with a fresh seed.</p>
        </div>

        <div className="divider" />

        <div className="section">
          <span className="eyebrow">Resize one room</span>
          <select
            value={selectedId}
            onChange={(e) => {
              setSelectedId(e.target.value);
              const pr = program?.rooms.find((r) => r.id === e.target.value);
              setNewTarget(pr ? pr.target_area_m2.toString() : "");
            }}
          >
            <option value="">Select a room…</option>
            {sortedRooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label} ({(r.area_mm2 / 1_000_000).toFixed(1)} m²)
              </option>
            ))}
          </select>
          {selectedId && (
            <div style={{ display: "flex", gap: "var(--s2)", alignItems: "flex-end" }}>
              <div style={{ flex: 1 }}>
                <label>New target (m²)</label>
                <input
                  type="number"
                  min={1}
                  step={0.5}
                  value={newTarget}
                  onChange={(e) => setNewTarget(e.target.value)}
                />
              </div>
              <button
                disabled={
                  generating ||
                  !Number.isFinite(parsed) ||
                  parsed <= 0 ||
                  parsed === currentTarget
                }
                onClick={() => runResize(selectedId, parsed)}
              >
                Apply
              </button>
            </div>
          )}
          {currentTarget != null && (
            <p className="muted">Current target: {currentTarget.toFixed(1)} m²</p>
          )}
        </div>

        <div className="divider" />

        <div className="section">
          <span className="eyebrow">Export</span>
          <ExportBar />
        </div>

        {generateError && (
          <div className="notes">
            <div className="note danger"><span className="dot" />{generateError}</div>
          </div>
        )}

        <div className="divider" />

        {diagnostics && (
          <div className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
            <div>Cost {diagnostics.cost.toFixed(2)}</div>
            <div>{diagnostics.iterations.toLocaleString()} iters · {diagnostics.accepted.toLocaleString()} accepted</div>
            <div>{diagnostics.restarts} restart{diagnostics.restarts === 1 ? "" : "s"}</div>
          </div>
        )}

        <div className="panel-actions">
          <button onClick={startOver}>Start over</button>
        </div>
      </aside>

      <main className="canvas">
        <PlanCanvas plan={plan} />
        {generating && (
          <div className="overlay">
            <div className="spinner" />
            <p className="muted">Re-annealing…</p>
          </div>
        )}
      </main>
    </div>
  );
}
