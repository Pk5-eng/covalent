import { useState } from "react";
import { usePlanStore } from "../state/planStore";

export function ExportBar() {
  const plan = usePlanStore((s) => s.plan);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!plan) return null;

  async function downloadDxf() {
    setExporting(true);
    setError(null);
    try {
      const r = await fetch("/api/export/dxf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(plan),
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`export failed: ${r.status} ${text}`);
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "covalent_plan.dxf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={downloadDxf}
        disabled={exporting}
        style={{ width: "100%" }}
      >
        {exporting ? "Exporting…" : "Export DXF"}
      </button>
      {error && (
        <div className="danger" style={{ fontSize: 12, marginTop: 6 }}>
          {error}
        </div>
      )}
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        Opens in AutoCAD, BricsCAD, LibreCAD. R2018, NCS layers, real DIMENSION entities.
      </div>
    </div>
  );
}
