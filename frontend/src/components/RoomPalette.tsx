import { useEffect, useMemo } from "react";
import type { CatalogRoom, Zone } from "../lib/model";
import { usePlanStore, totalRoomCount } from "../state/planStore";

const ZONE_ORDER: Zone[] = ["public", "private", "service", "exterior"];
const ZONE_LABEL: Record<Zone, string> = {
  public: "Public",
  private: "Private",
  service: "Service",
  circulation: "Circulation",
  exterior: "Exterior",
};
const ZONE_TINT: Record<Zone, string> = {
  public: "#2a4d3a",
  private: "#4a3a8a",
  service: "#8a553a",
  circulation: "#666666",
  exterior: "#3a6a8a",
};

export function RoomPalette() {
  const catalog = usePlanStore((s) => s.catalog);
  const catalogStatus = usePlanStore((s) => s.catalogStatus);
  const loadCatalog = usePlanStore((s) => s.loadCatalog);
  const rooms = usePlanStore((s) => s.rooms);
  const incRoom = usePlanStore((s) => s.incRoom);
  const resetRooms = usePlanStore((s) => s.resetRooms);
  const runCheck = usePlanStore((s) => s.runCheck);
  const boundary = usePlanStore((s) => s.boundary);

  useEffect(() => {
    if (catalogStatus === "idle") loadCatalog();
  }, [catalogStatus, loadCatalog]);

  // Debounced check whenever boundary or rooms change.
  useEffect(() => {
    const t = window.setTimeout(() => {
      runCheck();
    }, 200);
    return () => window.clearTimeout(t);
  }, [boundary, rooms, runCheck]);

  const grouped = useMemo(() => {
    const g: Record<Zone, CatalogRoom[]> = { public: [], private: [], service: [], circulation: [], exterior: [] };
    for (const r of catalog) g[r.zone].push(r);
    return g;
  }, [catalog]);

  const total = totalRoomCount(rooms);

  return (
    <div>
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span>Rooms</span>
        <button
          style={{ fontSize: 11, padding: "2px 8px" }}
          onClick={resetRooms}
          disabled={total === 0}
        >
          clear
        </button>
      </div>

      {catalogStatus === "loading" && <div className="muted">Loading catalog…</div>}
      {catalogStatus === "error" && <div className="danger">Catalog failed to load.</div>}

      {ZONE_ORDER.map((z) => {
        const list = grouped[z];
        if (!list?.length) return null;
        return (
          <div key={z} style={{ marginTop: 10 }}>
            <div
              style={{
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: ZONE_TINT[z],
                marginBottom: 4,
                fontWeight: 600,
              }}
            >
              {ZONE_LABEL[z]}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 4, columnGap: 8 }}>
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
  if (room.needs_window) flags.push("win");
  if (room.needs_egress) flags.push("egr");
  if (room.needs_exterior_wall) flags.push("ext");

  return (
    <>
      <div style={{ fontSize: 13, lineHeight: 1.3, paddingTop: 3 }}>
        <span style={{ fontWeight: count > 0 ? 600 : 400 }}>{room.label}</span>
        <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
          {room.target_m2} m² · min {room.min_m2}
          {flags.length ? ` · ${flags.join("·")}` : ""}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <button
          onClick={() => onChange(-1)}
          disabled={count <= 0}
          style={{ width: 24, padding: 0, height: 24, fontSize: 13 }}
          aria-label={`decrease ${room.label}`}
        >
          −
        </button>
        <span style={{ width: 18, textAlign: "center", fontVariantNumeric: "tabular-nums" }}>{count}</span>
        <button
          onClick={() => onChange(+1)}
          disabled={count >= room.max_count}
          style={{ width: 24, padding: 0, height: 24, fontSize: 13 }}
          aria-label={`increase ${room.label}`}
        >
          +
        </button>
      </div>
    </>
  );
}
