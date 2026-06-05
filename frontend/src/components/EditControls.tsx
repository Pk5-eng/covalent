import { useMemo, useState } from "react";
import type { Room } from "../lib/model";
import { usePlanStore } from "../state/planStore";

export function EditControls() {
  const plan = usePlanStore((s) => s.plan);
  const program = usePlanStore((s) => s.program);
  const generating = usePlanStore((s) => s.generating);
  const generateError = usePlanStore((s) => s.generateError);
  const runGenerate = usePlanStore((s) => s.runGenerate);
  const runResize = usePlanStore((s) => s.runResize);
  const diagnostics = usePlanStore((s) => s.diagnostics);

  const [selectedRoomId, setSelectedRoomId] = useState<string>("");

  const sortedRooms: Room[] = useMemo(() => {
    if (!plan) return [];
    return [...plan.rooms].sort((a, b) => a.label.localeCompare(b.label));
  }, [plan]);

  const selected = useMemo(() => {
    if (!plan || !selectedRoomId) return null;
    return plan.rooms.find((r) => r.id === selectedRoomId) ?? null;
  }, [plan, selectedRoomId]);

  const currentTargetM2 = useMemo(() => {
    if (!program || !selectedRoomId) return null;
    const pr = program.rooms.find((r) => r.id === selectedRoomId);
    return pr?.target_area_m2 ?? null;
  }, [program, selectedRoomId]);

  const [newTarget, setNewTarget] = useState<string>("");
  const newTargetParsed = parseFloat(newTarget);

  if (!plan || !program) return null;

  return (
    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
      <div className="section-title">Edit</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          className="primary"
          disabled={generating}
          onClick={() => runGenerate()}
          title="Re-run annealing from a new random seed"
        >
          {generating ? "Working…" : "Regenerate"}
        </button>
      </div>

      <div style={{ marginTop: 12 }}>
        <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
          Resize one room
        </div>
        <select
          value={selectedRoomId}
          onChange={(e) => {
            setSelectedRoomId(e.target.value);
            const pr = program.rooms.find((r) => r.id === e.target.value);
            setNewTarget(pr ? pr.target_area_m2.toString() : "");
          }}
          style={{
            width: "100%",
            font: "inherit",
            padding: "6px 8px",
            border: "1px solid var(--line)",
            borderRadius: 4,
            background: "var(--panel)",
            marginBottom: 6,
          }}
        >
          <option value="">Pick a room…</option>
          {sortedRooms.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label} ({(r.area_mm2 / 1_000_000).toFixed(1)} m²)
            </option>
          ))}
        </select>
        {selected && (
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="number"
              min={1}
              step={0.5}
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              placeholder="Target m²"
              style={{ width: 80 }}
            />
            <span className="muted" style={{ fontSize: 11 }}>
              now {currentTargetM2?.toFixed(1)} m²
            </span>
            <button
              disabled={
                generating ||
                !Number.isFinite(newTargetParsed) ||
                newTargetParsed <= 0 ||
                newTargetParsed === currentTargetM2
              }
              onClick={() => runResize(selected.id, newTargetParsed)}
            >
              Apply
            </button>
          </div>
        )}
      </div>

      {generateError && (
        <div className="danger" style={{ fontSize: 12, marginTop: 8 }}>
          {generateError}
        </div>
      )}

      {diagnostics && (
        <div className="muted" style={{ fontSize: 11, marginTop: 10 }}>
          Annealing cost {diagnostics.cost.toFixed(2)} · {diagnostics.iterations} iters ·{" "}
          {diagnostics.accepted} accepted · {diagnostics.restarts} restarts
        </div>
      )}
    </div>
  );
}
