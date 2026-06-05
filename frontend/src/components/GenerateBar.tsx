import { useState } from "react";
import { usePlanStore, totalRoomCount, buildProgramRequest } from "../state/planStore";

export function GenerateBar() {
  const boundary = usePlanStore((s) => s.boundary);
  const rooms = usePlanStore((s) => s.rooms);
  const check = usePlanStore((s) => s.check);
  const [showJson, setShowJson] = useState(false);

  const total = totalRoomCount(rooms);
  const ready = total > 0 && check?.ok === true;

  const request = buildProgramRequest(boundary, rooms);

  return (
    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          className="primary"
          disabled={!ready}
          title={ready ? "Generation lands in Step 3+" : "Resolve errors and pick at least one room"}
        >
          Generate plan
        </button>
        <button onClick={() => setShowJson((v) => !v)} disabled={total === 0}>
          {showJson ? "Hide JSON" : "Show JSON"}
        </button>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        Generation lands in Step 3 (architect agent) + Step 4 (layout engine).
      </div>
      {showJson && (
        <pre
          style={{
            marginTop: 8,
            fontSize: 11,
            background: "#f4f1e8",
            padding: 8,
            borderRadius: 4,
            border: "1px solid var(--line)",
            maxHeight: 240,
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
