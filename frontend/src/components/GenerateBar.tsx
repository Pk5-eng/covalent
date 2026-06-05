import { useState } from "react";
import { usePlanStore, totalRoomCount, buildProgramRequest } from "../state/planStore";

export function GenerateBar() {
  const boundary = usePlanStore((s) => s.boundary);
  const rooms = usePlanStore((s) => s.rooms);
  const check = usePlanStore((s) => s.check);
  const program = usePlanStore((s) => s.program);
  const generating = usePlanStore((s) => s.generating);
  const generateError = usePlanStore((s) => s.generateError);
  const runGenerate = usePlanStore((s) => s.runGenerate);

  const [showRequest, setShowRequest] = useState(false);
  const [showProgram, setShowProgram] = useState(true);

  const total = totalRoomCount(rooms);
  const ready = total > 0 && check?.ok === true;

  const request = buildProgramRequest(boundary, rooms);

  return (
    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button
          className="primary"
          disabled={!ready || generating}
          onClick={() => runGenerate()}
        >
          {generating ? "Generating…" : program ? "Regenerate program" : "Generate program"}
        </button>
        <button onClick={() => setShowRequest((v) => !v)} disabled={total === 0}>
          {showRequest ? "Hide request" : "Show request"}
        </button>
      </div>

      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        Architect agent returns program + adjacency only. Layout (Step 4) lands next.
      </div>

      {generateError && (
        <div className="danger" style={{ fontSize: 12, marginTop: 8 }}>
          {generateError}
        </div>
      )}

      {showRequest && (
        <pre style={preStyle}>
{JSON.stringify(request, null, 2)}
        </pre>
      )}

      {program && (
        <div style={{ marginTop: 12 }}>
          <div
            className="section-title"
            style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}
          >
            <span>Program (no coordinates)</span>
            <button
              style={{ fontSize: 11, padding: "2px 8px" }}
              onClick={() => setShowProgram((v) => !v)}
            >
              {showProgram ? "hide" : "show"}
            </button>
          </div>
          {showProgram && <ProgramSummary />}
        </div>
      )}
    </div>
  );
}

const preStyle: React.CSSProperties = {
  marginTop: 8,
  fontSize: 11,
  background: "#f4f1e8",
  padding: 8,
  borderRadius: 4,
  border: "1px solid var(--line)",
  maxHeight: 240,
  overflow: "auto",
  whiteSpace: "pre-wrap",
};

function ProgramSummary() {
  const program = usePlanStore((s) => s.program);
  if (!program) return null;
  return (
    <div>
      <div style={{ fontSize: 12, marginBottom: 6 }}>
        Entry: <strong>{program.circulation.entry_room_id}</strong> · circulation target{" "}
        {program.global.circulation_target_pct}%
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", rowGap: 2, fontSize: 12 }}>
        <span style={{ color: "var(--muted)", fontSize: 11 }}>Room</span>
        <span style={{ color: "var(--muted)", fontSize: 11, textAlign: "right" }}>Target</span>
        <span style={{ color: "var(--muted)", fontSize: 11, textAlign: "right" }}>Adj</span>
        {program.rooms.map((r) => (
          <RoomLine key={r.id} room={r} />
        ))}
      </div>
      {program.circulation.notes && (
        <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
          {program.circulation.notes}
        </div>
      )}
    </div>
  );
}

function RoomLine({ room }: { room: { label: string; zone: string; target_area_m2: number; adjacent_to: string[] } }) {
  return (
    <>
      <span>
        {room.label}{" "}
        <span style={{ color: "var(--muted)", fontSize: 10 }}>· {room.zone}</span>
      </span>
      <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {room.target_area_m2.toFixed(1)} m²
      </span>
      <span style={{ textAlign: "right", color: "var(--muted)" }}>
        {room.adjacent_to.length}
      </span>
    </>
  );
}
