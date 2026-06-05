import { useEffect, useState } from "react";
import { getHealth } from "./lib/api";
import { BoundaryInputs } from "./components/BoundaryInputs";
import { BoundaryEditor } from "./components/BoundaryEditor";
import { RoomPalette } from "./components/RoomPalette";
import { AreaTally } from "./components/AreaTally";
import { GenerateBar } from "./components/GenerateBar";
import { EditControls } from "./components/EditControls";
import { ExportBar } from "./components/ExportBar";
import { PlanCanvas } from "./components/PlanCanvas";
import { usePlanStore } from "./state/planStore";

export function App() {
  const [health, setHealth] = useState<string>("checking…");
  const plan = usePlanStore((s) => s.plan);
  const generating = usePlanStore((s) => s.generating);

  useEffect(() => {
    getHealth()
      .then((h) => setHealth(`${h.service} ${h.version}`))
      .catch((e: Error) => setHealth(`unreachable: ${e.message}`));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="title">Covalent</div>
        <div className="muted">AI Floor Plan Generator · {health}</div>

        <div style={{ marginTop: 16 }}>
          <BoundaryInputs />
        </div>
        <RoomPalette />
        <AreaTally />
        <GenerateBar />
        {plan && <EditControls />}
        {plan && <ExportBar />}

        <div className="muted" style={{ marginTop: 16, fontSize: 11 }}>
          Optimized-schematic plans. Not permit-ready construction documents.
        </div>
      </aside>
      <main className="canvas-area">
        {plan ? (
          <>
            <PlanCanvas plan={plan} />
            {generating && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "rgba(250, 250, 247, 0.6)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--accent)",
                  fontSize: 13,
                  pointerEvents: "none",
                }}
              >
                Annealing…
              </div>
            )}
          </>
        ) : (
          <BoundaryEditor />
        )}
      </main>
    </div>
  );
}
