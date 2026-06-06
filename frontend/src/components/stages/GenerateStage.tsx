import { totalRoomCount, usePlanStore } from "../../state/planStore";

export function GenerateStage() {
  const generating = usePlanStore((s) => s.generating);
  const error = usePlanStore((s) => s.generateError);
  const rooms = usePlanStore((s) => s.rooms);
  const boundary = usePlanStore((s) => s.boundary);
  const goBack = usePlanStore((s) => s.goBack);
  const runGenerate = usePlanStore((s) => s.runGenerate);

  const total = totalRoomCount(rooms);

  return (
    <div className="canvas" style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="center-msg">
        {generating ? (
          <>
            <div className="spinner" />
            <h2>Annealing your floor plan</h2>
            <p>
              The architect agent has set the program. The engine is now placing
              {" "}{total} rooms inside a {(boundary.width_mm / 1000).toFixed(1)} ×{" "}
              {(boundary.depth_mm / 1000).toFixed(1)} m boundary using a slicing-tree
              optimizer. This typically takes 10-30 seconds.
            </p>
          </>
        ) : error ? (
          <>
            <h2>Couldn't generate a plan</h2>
            <p className="danger">{error}</p>
            <div style={{ display: "flex", gap: "var(--s2)" }}>
              <button onClick={goBack}>← Back to rooms</button>
              <button className="primary" onClick={() => runGenerate()}>Try again</button>
            </div>
          </>
        ) : (
          <>
            <h2>Ready to generate</h2>
            <p>The engine will run automatically.</p>
            <button className="primary" onClick={() => runGenerate()}>Start</button>
          </>
        )}
      </div>
    </div>
  );
}
