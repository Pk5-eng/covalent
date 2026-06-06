import { useEffect, useMemo, useRef, useState } from "react";
import type { FloorPlan, Fixture, Opening, Room, Wall } from "../lib/model";
import { LAYER_STYLE, ZONE_FILL } from "../lib/render/layers";
import { wallLength, wallNormal, wallVector } from "../lib/render/geometry";

type Props = {
  plan: FloorPlan | null;
  emptyMessage?: string;
};

const PADDING_MM = 1200;
const TARGET_WIDTH_PX = 1100;

export function PlanCanvas({ plan, emptyMessage }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: r.width, h: r.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const transform = useMemo(() => {
    if (!plan) return null;
    const bw = plan.boundary.width_mm + 2 * PADDING_MM;
    const bh = plan.boundary.depth_mm + 2 * PADDING_MM;
    if (size.w === 0 || size.h === 0) {
      const s = TARGET_WIDTH_PX / bw;
      return {
        scale: s,
        offsetX: PADDING_MM * s,
        offsetY: PADDING_MM * s,
        viewW: bw * s,
        viewH: bh * s,
      };
    }
    const s = Math.min(size.w / bw, size.h / bh);
    return {
      scale: s,
      offsetX: PADDING_MM * s + (size.w - bw * s) / 2,
      offsetY: PADDING_MM * s + (size.h - bh * s) / 2,
      viewW: size.w,
      viewH: size.h,
    };
  }, [plan, size.w, size.h]);

  if (!plan) {
    return (
      <div
        ref={containerRef}
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
        {emptyMessage ?? "No plan yet."}
      </div>
    );
  }

  if (!transform) {
    return <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />;
  }

  const { scale: s, offsetX, offsetY, viewW, viewH } = transform;
  const X = (mm: number) => mm * s + offsetX;
  const Y = (mm: number) => mm * s + offsetY;

  const byWallId = new Map<string, Wall>(plan.walls.map((w) => [w.id, w]));

  return (
    <div ref={containerRef} style={{ position: "absolute", inset: 0 }}>
      <svg
        width={viewW}
        height={viewH}
        viewBox={`0 0 ${viewW} ${viewH}`}
        style={{ display: "block" }}
      >
        {/* paper background */}
        <rect width={viewW} height={viewH} fill="#fafaf7" />

        {/* room fills (zone tint) */}
        <g>
          {plan.rooms.map((room) => (
            <polygon
              key={`fill-${room.id}`}
              points={polygonPoints(room, X, Y)}
              fill={ZONE_FILL[room.zone] ?? "#f4f4f1"}
              stroke="none"
            />
          ))}
        </g>

        {/* dimensions: overall + per-room (drawn under walls) */}
        <g>
          <OverallDims plan={plan} X={X} Y={Y} />
          {plan.rooms.map((room) => (
            <RoomDims key={`dim-${room.id}`} room={room} X={X} Y={Y} />
          ))}
        </g>

        {/* fixtures (drawn under walls so wall lines crisp through) */}
        <g>
          {plan.fixtures.map((fx) => (
            <FixtureGlyph key={fx.id} fixture={fx} X={X} Y={Y} />
          ))}
        </g>

        {/* walls (poche) */}
        <g>
          {plan.walls.map((w) => (
            <WallPoche key={w.id} wall={w} X={X} Y={Y} scalePxPerMm={s} />
          ))}
        </g>

        {/* openings: doors and windows */}
        <g>
          {plan.openings.map((op) => (
            <OpeningGlyph
              key={op.id}
              opening={op}
              wall={byWallId.get(op.wall_id)}
              X={X}
              Y={Y}
            />
          ))}
        </g>

        {/* labels */}
        <g>
          {plan.rooms.map((room) => (
            <RoomLabel key={`lbl-${room.id}`} room={room} X={X} Y={Y} />
          ))}
        </g>

        {/* title block + north arrow + scale bar */}
        <TitleBlock plan={plan} viewH={viewH} X={X} Y={Y} scalePxPerMm={s} />
      </svg>
    </div>
  );
}

// ---------- Rendering primitives ----------

function polygonPoints(room: Room, X: (m: number) => number, Y: (m: number) => number): string {
  return room.polygon.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ");
}

function WallPoche({
  wall,
  X,
  Y,
  scalePxPerMm,
}: {
  wall: Wall;
  X: (m: number) => number;
  Y: (m: number) => number;
  scalePxPerMm: number;
}) {
  const thickness = wall.thickness_mm * scalePxPerMm;
  const n = wallNormal(wall);
  const half = thickness / 2;
  const a = { x: X(wall.a[0]), y: Y(wall.a[1]) };
  const b = { x: X(wall.b[0]), y: Y(wall.b[1]) };
  const pts = [
    { x: a.x + n.x * half, y: a.y + n.y * half },
    { x: b.x + n.x * half, y: b.y + n.y * half },
    { x: b.x - n.x * half, y: b.y - n.y * half },
    { x: a.x - n.x * half, y: a.y - n.y * half },
  ];
  const style = LAYER_STYLE[wall.type === "exterior" ? "A-WALL-EXTR" : "A-WALL"];
  return (
    <polygon
      points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
      fill={style.stroke}
      stroke="none"
    />
  );
}

function OpeningGlyph({
  opening,
  wall,
  X,
  Y,
}: {
  opening: Opening;
  wall?: Wall;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  if (!wall) return null;
  const v = wallVector(wall);
  const totalLen = wallLength(wall);
  if (totalLen === 0) return null;

  const center = {
    x: wall.a[0] + v.x * opening.position,
    y: wall.a[1] + v.y * opening.position,
  };
  const halfMm = opening.width_mm / 2;
  const dir = { x: v.x / totalLen, y: v.y / totalLen };
  const a = { x: center.x - dir.x * halfMm, y: center.y - dir.y * halfMm };
  const b = { x: center.x + dir.x * halfMm, y: center.y + dir.y * halfMm };

  if (opening.kind === "door") {
    const swing = wallNormal(wall);
    // Door leaf goes from `a` perpendicular into the room on the swing side.
    const hinge = a;
    const tip = {
      x: hinge.x + dir.x * opening.width_mm,
      y: hinge.y + dir.y * opening.width_mm,
    };
    // Quarter-circle arc representing the swing.
    const arcEnd = {
      x: hinge.x + swing.x * opening.width_mm,
      y: hinge.y + swing.y * opening.width_mm,
    };
    return (
      <g stroke={LAYER_STYLE["A-DOOR"].stroke} strokeWidth={LAYER_STYLE["A-DOOR"].strokeWidth} fill="none">
        {/* wall break: clear the door span with a white line behind */}
        <line x1={X(a.x)} y1={Y(a.y)} x2={X(b.x)} y2={Y(b.y)} stroke="#fafaf7" strokeWidth={3} />
        {/* door leaf */}
        <line x1={X(hinge.x)} y1={Y(hinge.y)} x2={X(tip.x)} y2={Y(tip.y)} />
        {/* swing arc */}
        <path
          d={`M ${X(tip.x).toFixed(1)} ${Y(tip.y).toFixed(1)} A ${(opening.width_mm * (X(1) - X(0))).toFixed(1)} ${(opening.width_mm * (Y(1) - Y(0))).toFixed(1)} 0 0 1 ${X(arcEnd.x).toFixed(1)} ${Y(arcEnd.y).toFixed(1)}`}
          strokeDasharray="2 2"
        />
      </g>
    );
  }

  // window: wall gap with two parallel lines across the opening
  const n = wallNormal(wall);
  const inset = 80; // mm
  const top1 = { x: a.x + n.x * inset, y: a.y + n.y * inset };
  const top2 = { x: b.x + n.x * inset, y: b.y + n.y * inset };
  const bot1 = { x: a.x - n.x * inset, y: a.y - n.y * inset };
  const bot2 = { x: b.x - n.x * inset, y: b.y - n.y * inset };
  return (
    <g stroke={LAYER_STYLE["A-GLAZ"].stroke} strokeWidth={LAYER_STYLE["A-GLAZ"].strokeWidth} fill="none">
      <line x1={X(a.x)} y1={Y(a.y)} x2={X(b.x)} y2={Y(b.y)} stroke="#fafaf7" strokeWidth={3} />
      <line x1={X(top1.x)} y1={Y(top1.y)} x2={X(top2.x)} y2={Y(top2.y)} />
      <line x1={X(bot1.x)} y1={Y(bot1.y)} x2={X(bot2.x)} y2={Y(bot2.y)} />
    </g>
  );
}

function FixtureGlyph({
  fixture,
  X,
  Y,
}: {
  fixture: Fixture;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  if (fixture.polygon.length < 3) return null;
  const xs = fixture.polygon.map((p) => p[0]);
  const ys = fixture.polygon.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const y0 = Math.min(...ys);
  const x1 = Math.max(...xs);
  const y1 = Math.max(...ys);
  const w = x1 - x0;
  const h = y1 - y0;
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  const px = X(1) - X(0); // pixels per mm
  const stroke = "#7a5a3a";
  const fill = "#fdf6e7";

  const outline = (
    <rect
      x={X(x0)}
      y={Y(y0)}
      width={w * px}
      height={h * px}
      fill={fill}
      stroke={stroke}
      strokeWidth={0.7}
      vectorEffect="non-scaling-stroke"
    />
  );

  let glyph: JSX.Element | null = null;
  switch (fixture.kind) {
    case "bed":
    case "crib":
      // Pillow band along the shorter side (head of bed)
      glyph = (
        <rect
          x={X(x0)}
          y={Y(y0)}
          width={Math.min(w, h) * 0.25 * px}
          height={h * px}
          fill="none"
          stroke={stroke}
          strokeWidth={0.6}
        />
      );
      break;
    case "sofa": {
      const armR = Math.min(w, h) * 0.15;
      glyph = (
        <g stroke={stroke} strokeWidth={0.6} fill="none">
          {/* arms */}
          <rect x={X(x0)} y={Y(y0)} width={armR * px} height={h * px} />
          <rect x={X(x1 - armR)} y={Y(y0)} width={armR * px} height={h * px} />
          {/* back */}
          <rect x={X(x0)} y={Y(y0)} width={w * px} height={Math.min(h * 0.3, 180) * px} />
        </g>
      );
      break;
    }
    case "toilet":
      glyph = (
        <g stroke={stroke} strokeWidth={0.6} fill="none">
          <rect x={X(x0)} y={Y(y0)} width={w * px} height={h * 0.3 * px} />
          <ellipse
            cx={X(cx)}
            cy={Y(y0 + h * 0.65)}
            rx={w * 0.4 * px}
            ry={h * 0.32 * px}
          />
        </g>
      );
      break;
    case "sink":
      glyph = (
        <ellipse
          cx={X(cx)}
          cy={Y(cy)}
          rx={w * 0.4 * px}
          ry={h * 0.4 * px}
          fill="none"
          stroke={stroke}
          strokeWidth={0.6}
        />
      );
      break;
    case "tub":
      glyph = (
        <rect
          x={X(x0 + w * 0.08)}
          y={Y(y0 + h * 0.08)}
          width={w * 0.84 * px}
          height={h * 0.84 * px}
          rx={Math.min(w, h) * 0.1 * px}
          fill="none"
          stroke={stroke}
          strokeWidth={0.6}
        />
      );
      break;
    case "table":
    case "coffee_table":
      glyph = null; // outline is enough
      break;
    case "counter":
      glyph = (
        <g stroke={stroke} strokeWidth={0.4} fill="none">
          {/* sink + stove indicators along the run */}
          <rect x={X(x0 + w * 0.3)} y={Y(y0 + h * 0.2)} width={w * 0.15 * px} height={h * 0.6 * px} />
          <circle cx={X(x0 + w * 0.65)} cy={Y(y0 + h * 0.35)} r={Math.min(w, h) * 0.06 * px} />
          <circle cx={X(x0 + w * 0.8)} cy={Y(y0 + h * 0.35)} r={Math.min(w, h) * 0.06 * px} />
          <circle cx={X(x0 + w * 0.65)} cy={Y(y0 + h * 0.65)} r={Math.min(w, h) * 0.06 * px} />
          <circle cx={X(x0 + w * 0.8)} cy={Y(y0 + h * 0.65)} r={Math.min(w, h) * 0.06 * px} />
        </g>
      );
      break;
    case "fridge":
      glyph = (
        <line
          x1={X(x0)}
          y1={Y(y0 + h * 0.55)}
          x2={X(x1)}
          y2={Y(y0 + h * 0.55)}
          stroke={stroke}
          strokeWidth={0.5}
        />
      );
      break;
    case "wardrobe":
    case "bookshelf":
    case "shelving":
      // Door split lines
      glyph = (
        <g stroke={stroke} strokeWidth={0.4}>
          <line x1={X(x0 + w / 2)} y1={Y(y0)} x2={X(x0 + w / 2)} y2={Y(y1)} />
        </g>
      );
      break;
    case "desk":
      glyph = (
        <circle
          cx={X(cx)}
          cy={Y(y0 + h * 0.85)}
          r={Math.min(w, h) * 0.13 * px}
          fill="none"
          stroke={stroke}
          strokeWidth={0.5}
        />
      );
      break;
    case "car":
      glyph = (
        <g stroke={stroke} strokeWidth={0.5} fill="none">
          <rect x={X(x0 + w * 0.1)} y={Y(y0 + h * 0.15)} width={w * 0.8 * px} height={h * 0.7 * px} rx={6} />
          <rect x={X(x0 + w * 0.25)} y={Y(y0 + h * 0.25)} width={w * 0.5 * px} height={h * 0.3 * px} rx={4} />
        </g>
      );
      break;
    case "console":
    case "bench":
    case "washer":
    case "dryer":
    case "equipment":
    default:
      glyph = null;
  }

  return (
    <g>
      {outline}
      {glyph}
    </g>
  );
}

function RoomLabel({
  room,
  X,
  Y,
}: {
  room: Room;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  if (!room.polygon.length) return null;
  const cx = room.polygon.reduce((s, p) => s + p[0], 0) / room.polygon.length;
  const cy = room.polygon.reduce((s, p) => s + p[1], 0) / room.polygon.length;
  const areaM2 = room.area_mm2 / 1_000_000;
  // Scale font with room size (smaller rooms get smaller text).
  const minDim = Math.min(
    Math.max(...room.polygon.map((p) => p[0])) - Math.min(...room.polygon.map((p) => p[0])),
    Math.max(...room.polygon.map((p) => p[1])) - Math.min(...room.polygon.map((p) => p[1])),
  );
  const px = X(1) - X(0); // pixels per mm
  const fontSize = Math.max(8, Math.min(14, minDim * px * 0.06));
  return (
    <g transform={`translate(${X(cx).toFixed(1)},${Y(cy).toFixed(1)})`}>
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily="ui-sans-serif,system-ui"
        fill="#1a1a1a"
      >
        <tspan x={0} dy="-0.5em" fontSize={fontSize} fontWeight={600} letterSpacing={0.3}>
          {room.label.toUpperCase()}
        </tspan>
        <tspan x={0} dy="1.4em" fontSize={fontSize * 0.85} fill="#444">
          {areaM2.toFixed(1)} m²
        </tspan>
      </text>
    </g>
  );
}

function RoomDims({
  room,
  X,
  Y,
}: {
  room: Room;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  if (!room.polygon.length) return null;
  const xs = room.polygon.map((p) => p[0]);
  const ys = room.polygon.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const y0 = Math.min(...ys);
  const y1 = Math.max(...ys);
  const w = x1 - x0;
  const h = y1 - y0;
  if (w < 1500 || h < 1500) return null; // skip tiny rooms

  const style = LAYER_STYLE["A-ANNO-DIMS"];
  const offset = 8;
  return (
    <g stroke={style.stroke} strokeWidth={style.strokeWidth} fill="#444">
      {/* horizontal dim along top */}
      <line
        x1={X(x0)}
        y1={Y(y0) - offset}
        x2={X(x1)}
        y2={Y(y0) - offset}
      />
      <text
        x={(X(x0) + X(x1)) / 2}
        y={Y(y0) - offset - 3}
        textAnchor="middle"
        fontSize={9}
        fontFamily="ui-sans-serif,system-ui"
        stroke="none"
      >
        {(w / 1000).toFixed(2)}
      </text>
    </g>
  );
}

function OverallDims({
  plan,
  X,
  Y,
}: {
  plan: FloorPlan;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  const bw = plan.boundary.width_mm;
  const bh = plan.boundary.depth_mm;
  const off = 32;
  return (
    <g stroke="#1a1a1a" strokeWidth={0.8} fill="#1a1a1a">
      {/* overall width */}
      <line x1={X(0)} y1={Y(0) - off} x2={X(bw)} y2={Y(0) - off} />
      <line x1={X(0)} y1={Y(0) - off - 4} x2={X(0)} y2={Y(0) - off + 4} />
      <line x1={X(bw)} y1={Y(0) - off - 4} x2={X(bw)} y2={Y(0) - off + 4} />
      <text
        x={(X(0) + X(bw)) / 2}
        y={Y(0) - off - 6}
        textAnchor="middle"
        fontSize={11}
        stroke="none"
        fontFamily="ui-sans-serif,system-ui"
      >
        {(bw / 1000).toFixed(2)} m
      </text>
      {/* overall depth */}
      <line x1={X(bw) + off} y1={Y(0)} x2={X(bw) + off} y2={Y(bh)} />
      <line x1={X(bw) + off - 4} y1={Y(0)} x2={X(bw) + off + 4} y2={Y(0)} />
      <line x1={X(bw) + off - 4} y1={Y(bh)} x2={X(bw) + off + 4} y2={Y(bh)} />
      <text
        x={X(bw) + off + 8}
        y={(Y(0) + Y(bh)) / 2}
        dominantBaseline="central"
        fontSize={11}
        stroke="none"
        fontFamily="ui-sans-serif,system-ui"
      >
        {(bh / 1000).toFixed(2)} m
      </text>
    </g>
  );
}

function TitleBlock({
  plan,
  viewH,
  X,
  Y,
  scalePxPerMm,
}: {
  plan: FloorPlan;
  viewH: number;
  X: (m: number) => number;
  Y: (m: number) => number;
  scalePxPerMm: number;
}) {
  const tx = X(0);
  const ty = Math.min(viewH - 80, Y(plan.boundary.depth_mm) + 60);
  // scale bar length = 5 m in drawing units, mapped to pixels
  const fiveM = 5000 * scalePxPerMm;
  return (
    <g>
      <text
        x={tx}
        y={ty}
        fontSize={11}
        fontFamily="ui-sans-serif,system-ui"
        fill="#1a1a1a"
        letterSpacing={0.6}
      >
        {plan.meta.title.toUpperCase()} · SCALE {plan.meta.scale}
      </text>
      {/* scale bar */}
      <g transform={`translate(${tx},${ty + 10})`}>
        <line x1={0} y1={4} x2={fiveM} y2={4} stroke="#1a1a1a" strokeWidth={1} />
        <line x1={0} y1={0} x2={0} y2={8} stroke="#1a1a1a" strokeWidth={1} />
        <line x1={fiveM} y1={0} x2={fiveM} y2={8} stroke="#1a1a1a" strokeWidth={1} />
        <line x1={fiveM / 2} y1={2} x2={fiveM / 2} y2={6} stroke="#1a1a1a" strokeWidth={1} />
        <text x={0} y={20} fontSize={9} fontFamily="ui-sans-serif,system-ui" fill="#444">
          0
        </text>
        <text x={fiveM} y={20} fontSize={9} textAnchor="middle" fontFamily="ui-sans-serif,system-ui" fill="#444">
          5 m
        </text>
      </g>
      {/* north arrow */}
      <g transform={`translate(${X(plan.boundary.width_mm) - 30},${ty + 4})`}>
        <circle cx={0} cy={0} r={14} fill="#fafaf7" stroke="#1a1a1a" strokeWidth={0.8} />
        <polygon points="0,-10 4,4 0,1 -4,4" fill="#1a1a1a" />
        <text x={0} y={20} textAnchor="middle" fontSize={9} fontFamily="ui-sans-serif,system-ui" fill="#444">
          N
        </text>
      </g>
    </g>
  );
}
