import { usePlanStore } from "../state/planStore";

export function AreaTally() {
  const check = usePlanStore((s) => s.check);
  const checking = usePlanStore((s) => s.checking);
  const lastError = usePlanStore((s) => s.lastError);

  if (lastError) {
    return (
      <div className="danger" style={{ fontSize: 12, marginTop: 8 }}>
        {lastError}
      </div>
    );
  }

  if (!check) {
    return (
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        {checking ? "Checking…" : "Pick rooms to see the area tally."}
      </div>
    );
  }

  const s = check.summary;
  const usagePct = (s.target_total_m2 / s.usable_area_m2) * 100;
  const fillColor = !check.ok
    ? "var(--danger)"
    : usagePct > 100
      ? "var(--warn)"
      : "var(--accent)";

  return (
    <div style={{ marginTop: 10 }}>
      <div className="section-title">Area tally</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 2, fontSize: 12 }}>
        <span>Boundary</span><span>{s.boundary_area_m2.toFixed(1)} m²</span>
        <span>Usable (after walls + circulation)</span><span>{s.usable_area_m2.toFixed(1)} m²</span>
        <span>Room minimums</span><span>{s.min_required_m2.toFixed(1)} m²</span>
        <span>Room targets</span><span>{s.target_total_m2.toFixed(1)} m²</span>
      </div>
      <div style={{ height: 8, background: "#ece9e0", marginTop: 8, borderRadius: 4, overflow: "hidden" }}>
        <div
          style={{
            width: `${Math.min(100, usagePct)}%`,
            height: "100%",
            background: fillColor,
            transition: "width 150ms ease-out",
          }}
        />
      </div>

      {check.errors.map((e, i) => (
        <div key={`e${i}`} className="danger" style={{ fontSize: 12, marginTop: 6 }}>● {e}</div>
      ))}
      {check.warnings.map((w, i) => (
        <div key={`w${i}`} className="warn" style={{ fontSize: 12, marginTop: 6 }}>● {w}</div>
      ))}
    </div>
  );
}
