import { useEffect, useState } from "react";
import { getEcho, getHealth } from "./lib/api";

export function App() {
  const [health, setHealth] = useState<string>("checking...");
  const [echo, setEcho] = useState<string>("");

  useEffect(() => {
    getHealth()
      .then((h) => setHealth(`${h.service} ${h.version} ok`))
      .catch((e: Error) => setHealth(`backend unreachable: ${e.message}`));
    getEcho("covalent round-trip")
      .then((r) => setEcho(r.echo))
      .catch((e: Error) => setEcho(`echo failed: ${e.message}`));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="title">Covalent</div>
        <div className="muted">AI Floor Plan Generator</div>

        <div className="section-title">Step 1: scaffolding</div>
        <div style={{ fontSize: 13, lineHeight: 1.5 }}>
          Backend reachable + one round trip working.
        </div>

        <div className="section-title">Backend status</div>
        <div style={{ fontSize: 13 }}>
          <div>health: <span className="muted">{health}</span></div>
          <div>echo: <span className="muted">{echo}</span></div>
        </div>

        <div className="section-title">What this is</div>
        <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--muted)" }}>
          Draw a rectangular boundary, pick rooms, generate an optimized
          schematic floor plan, export DXF. Optimized-schematic, not
          permit-ready.
        </div>
      </aside>
      <main className="canvas-area">
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--muted)",
            fontSize: 14,
          }}
        >
          Canvas appears in Step 2 (boundary tool + room palette).
        </div>
      </main>
    </div>
  );
}
