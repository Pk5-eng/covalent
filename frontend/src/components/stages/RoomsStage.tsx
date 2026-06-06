import { useEffect, useMemo } from "react";
import { BoundaryEditor } from "../BoundaryEditor";
import type { CatalogRoom, Zone } from "../../lib/model";
import { totalRoomCount, usePlanStore } from "../../state/planStore";

const ZONE_ORDER: Zone[] = ["public", "private", "service", "circulation", "exterior"];
const ZONE_LABEL: Record<Zone, string> = {
  public: "Public",
  private: "Private",
  service: "Service",
  circulation: "Circulation",
  exterior: "Exterior",
};
const ZONE_COLOR: Record<Zone, string> = {
  public: "#2a4d3a",
  private: "#4a3a8a",
  service: "#8a553a",
  circulation: "#5a5a52",
  exterior: "#3a6a8a",
};

export function RoomsStage() {
  const boundary = usePlanStore((s) => s.boundary);
  const catalog = usePlanStore((s) => s.catalog);
  const catalogStatus = usePlanStore((s) => s.catalogStatus);
  const loadCatalog = usePlanStore((s) => s.loadCatalog);
  const rooms = usePlanStore((s) => s.rooms);
  const incRoom = usePlanStore((s) => s.incRoom);
  const resetRooms = usePlanStore((s) => s.resetRooms);
  const runCheck = usePlanStore((s) => s.runCheck);
  const check = usePlanStore((s) => s.check);
  const checking = usePlanStore((s) => s.checking);
  const goBack = usePlanStore((s) => s.goBack);
  const runGenerate = usePlanStore((s) => s.runGenerate);
  const generateError = usePlanStore((s) => s.generateError);

  useEffect(() => {
    if (catalogStatus === "idle") loadCatalog();
  }, [catalogStatus, loadCatalog]);

  useEffect(() => {
    const t = window.setTimeout(() => runCheck(), 200);
    return () => window.clearTimeout(t);
  }, [boundary, rooms, runCheck]);

  const grouped = useMemo(() => {
    const g: Record<Zone, CatalogRoom[]> = {
      public: [], private: [], service: [], circulation: [], exterior: [],
    };
    for (const r of catalog) g[r.zone].push(r);
    return g;
  }, [catalog]);

  const total = totalRoomCount(rooms);
  const ready = total > 0 && check?.ok === true;

  return (
    <div className="stage">
      <aside className="panel">
        <div className="section">
          <span className="eyebrow">Step 2 of 4</span>
          <h2 className="stage-title">Choose your rooms</h2>
          <p className="stage-sub">
            Pick what you want. The architect agent will allocate areas and zone them.
            Adjacencies are decided automatically.
          </p>
        </div>

        {catalogStatus === "loading" && (
          <div className="muted">Loading catalog…</div>
        )}
        {catalogStatus === "error" && (
          <div className="notes">
            <div className="note danger">
              <span className="dot" />
              <span>
                Catalog failed to load. The backend may not be reachable —
                check the API URL in <code className="kbd">frontend/vercel.json</code>.
              </span>
            </div>
          </div>
        )}

        <Tally />

        <div className="panel-actions">
          <button onClick={goBack}>← Back</button>
          <button
            className="primary"
            disabled={!ready || checking}
            onClick={() => runGenerate()}
          >
            Generate plan →
          </button>
        </div>
        {generateError && (
          <div className="notes">
            <div className="note danger"><span className="dot" />{generateError}</div>
          </div>
        )}
      </aside>

      <main className="canvas" style={{ overflow: "auto", padding: "var(--s5)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 280px", gap: "var(--s5)", height: "100%" }}>
          <div className="section">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h3 style={{ fontFamily: "Fraunces, Georgia, serif", fontSize: 18, margin: 0, fontWeight: 500 }}>
                Room catalogue
              </h3>
              <div style={{ display: "flex", gap: "var(--s2)" }}>
                <span className="muted">{total} room{total === 1 ? "" : "s"} selected</span>
                <button className="ghost" onClick={resetRooms} disabled={total === 0}>Clear</button>
              </div>
            </div>

            <div className="section">
              {ZONE_ORDER.map((z) => {
                const list = grouped[z];
                if (!list?.length) return null;
                return (
                  <div key={z} className="zone-section">
                    <div className="zone-header" style={{ color: ZONE_COLOR[z] }}>
                      <span className="swatch" style={{ background: ZONE_COLOR[z] }} />
                      {ZONE_LABEL[z]}
                    </div>
                    <div style={{ display: "grid", gap: 2 }}>
                      {list.map((r) => (
                        <RoomRow
                          key={r.type}
                          room={r}
                          count={rooms[r.type] ?? 0}
                          onChange={(d) => incRoom(r.type, d, r.max_count)}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <aside style={{ position: "sticky", top: 0, height: "max-content" }}>
            <div style={{ border: "1px solid var(--line)", borderRadius: "var(--r2)", padding: "var(--s3)", background: "var(--paper-2)" }}>
              <div className="muted" style={{ marginBottom: "var(--s2)" }}>Your boundary</div>
              <div style={{ aspectRatio: `${boundary.width_mm} / ${boundary.depth_mm}`, position: "relative", background: "var(--paper)", border: "1px solid var(--line)", borderRadius: "var(--r1)" }}>
                <BoundaryEditor />
              </div>
              <div className="muted" style={{ marginTop: "var(--s2)", fontVariantNumeric: "tabular-nums" }}>
                {(boundary.width_mm / 1000).toFixed(1)} × {(boundary.depth_mm / 1000).toFixed(1)} m ·{" "}
                {((boundary.width_mm * boundary.depth_mm) / 1_000_000).toFixed(1)} m²
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function RoomRow({
  room,
  count,
  onChange,
}: {
  room: CatalogRoom;
  count: number;
  onChange: (delta: number) => void;
}) {
  const flags: string[] = [];
  if (room.bundle && room.bundle.length) flags.push("bedroom + ensuite");
  if (room.needs_window) flags.push("window");
  if (room.needs_egress) flags.push("egress");
  return (
    <div className={`room-row ${count > 0 ? "active" : ""}`}>
      <div>
        <div className="name">{room.label}</div>
        <span className="meta">
          {room.target_m2} m² typical · min {room.min_m2} m² · {room.min_width_m} m wide
          {flags.length ? ` · ${flags.join(", ")}` : ""}
        </span>
      </div>
      <div className="stepper-mini">
        <button
          className="icon"
          onClick={() => onChange(-1)}
          disabled={count <= 0}
          aria-label={`decrease ${room.label}`}
        >
          −
        </button>
        <span className="count">{count}</span>
        <button
          className="icon"
          onClick={() => onChange(+1)}
          disabled={count >= room.max_count}
          aria-label={`increase ${room.label}`}
        >
          +
        </button>
      </div>
    </div>
  );
}

const BATHROOM_TYPES = new Set(["full_bath", "powder"]);

function Tally() {
  const check = usePlanStore((s) => s.check);
  const rooms = usePlanStore((s) => s.rooms);
  if (totalRoomCount(rooms) === 0) {
    return (
      <p className="muted">Pick at least one room to continue.</p>
    );
  }
  if (!check) return <p className="muted">Checking…</p>;
  const s = check.summary;
  const usagePct = (s.target_total_m2 / s.usable_area_m2) * 100;
  const cls = !check.ok ? "tally-bar danger" : usagePct > 100 ? "tally-bar warn" : "tally-bar";

  // Architectural nudges: complete homes almost always need a bathroom + entry.
  const advisories: string[] = [];
  const hasBathroom = Object.entries(rooms).some(
    ([type, count]) => BATHROOM_TYPES.has(type) && count > 0,
  );
  if (!hasBathroom) {
    advisories.push("No bathroom selected. Most homes need at least one full bath or powder room.");
  }
  const hasEntry = (rooms["foyer"] ?? 0) > 0 || (rooms["mudroom"] ?? 0) > 0;
  if (!hasEntry) {
    advisories.push("No foyer or mudroom selected. The front door will be placed on the first public room.");
  }

  return (
    <div className="tally">
      <div className="tally-row"><span>Usable area</span><span>{s.usable_area_m2.toFixed(1)} m²</span></div>
      <div className="tally-row"><span>Room minimums</span><span>{s.min_required_m2.toFixed(1)} m²</span></div>
      <div className="tally-row"><span>Room targets</span><span>{s.target_total_m2.toFixed(1)} m²</span></div>
      <div className={cls}>
        <div className="fill" style={{ width: `${Math.min(100, usagePct)}%` }} />
      </div>
      {check.errors.length > 0 && (
        <div className="notes">
          {check.errors.map((e, i) => (
            <div key={`e${i}`} className="note danger"><span className="dot" />{e}</div>
          ))}
        </div>
      )}
      {check.warnings.length > 0 && (
        <div className="notes">
          {check.warnings.map((w, i) => (
            <div key={`w${i}`} className="note warn"><span className="dot" />{w}</div>
          ))}
        </div>
      )}
      {advisories.length > 0 && (
        <div className="notes">
          {advisories.map((a, i) => (
            <div key={`a${i}`} className="note warn"><span className="dot" />{a}</div>
          ))}
        </div>
      )}
    </div>
  );
}
