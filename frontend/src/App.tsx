import { useEffect, useState } from "react";
import { getHealth } from "./lib/api";
import { BoundaryInputs } from "./components/BoundaryInputs";
import { BoundaryEditor } from "./components/BoundaryEditor";
import { RoomPalette } from "./components/RoomPalette";
import { AreaTally } from "./components/AreaTally";
import { GenerateBar } from "./components/GenerateBar";

export function App() {
  const [health, setHealth] = useState<string>("checking…");

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

        <div className="muted" style={{ marginTop: 16, fontSize: 11 }}>
          Optimized-schematic plans. Not permit-ready construction documents.
        </div>
      </aside>
      <main className="canvas-area">
        <BoundaryEditor />
      </main>
    </div>
  );
}
