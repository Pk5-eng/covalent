import { useState } from "react";
import { usePlanStore, totalRoomCount, buildProgramRequest } from "../state/planStore";

export function GenerateBar() {
  const boundary = usePlanStore((s) => s.boundary);
  const rooms = usePlanStore((s) => s.rooms);
  const check = usePlanStore((s) => s.check);
  const plan = usePlanStore((s) => s.plan);
  const generating = usePlanStore((s) => s.generating);
  const generateError = usePlanStore((s) => s.generateError);
  const runGenerate = usePlanStore((s) => s.runGenerate);

  const [showRequest, setShowRequest] = useState(false);

  const total = totalRoomCount(rooms);
  const ready = total > 0 && check?.ok === true;

  if (plan) return null; // post-plan, EditControls handles the actions.

  const request = buildProgramRequest(boundary, rooms);

  return (
    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button
          className="primary"
          disabled={!ready || generating}
          onClick={() => runGenerate()}
        >
          {generating ? "Generating…" : "Generate plan"}
        </button>
        <button onClick={() => setShowRequest((v) => !v)} disabled={total === 0}>
          {showRequest ? "Hide request" : "Show request"}
        </button>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        Architect agent decides program + adjacencies. Engine anneals a slicing-tree
        layout. Validator gates the result.
      </div>
      {generateError && (
        <div className="danger" style={{ fontSize: 12, marginTop: 8 }}>
          {generateError}
        </div>
      )}
      {showRequest && (
        <pre
          style={{
            marginTop: 8,
            fontSize: 11,
            background: "#f4f1e8",
            padding: 8,
            borderRadius: 4,
            border: "1px solid var(--line)",
            maxHeight: 200,
            overflow: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
{JSON.stringify(request, null, 2)}
        </pre>
      )}
    </div>
  );
}
