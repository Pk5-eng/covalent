import { useEffect, useMemo, useRef, useState } from "react";
import type { FloorPlan, Fixture, Opening, Room, Wall } from "../lib/model";
import { ZONE_FILL } from "../lib/render/layers";
import { wallLength, wallNormal, wallVector } from "../lib/render/geometry";

type Props = {
  plan: FloorPlan | null;
  emptyMessage?: string;
};

const PADDING_MM = 1400;
const TARGET_WIDTH_PX = 1100;

// Palette for the drawing. Off-black walls, warm fixture tones, muted dimensions.
const INK = "#1f1f1d";
const INK_SOFT = "#3a3a36";
const FIXT_STROKE = "#5a4838";
const FIXT_FILL = "#fdf8ec";
const FIXT_DETAIL = "#7a6248";
const DIM_LINE = "#a9a298";
const DIM_TEXT = "#5a554d";
const GRID_LINE = "#ece6d8";
const DOOR_STROKE = "#7d3a32";
const WINDOW_STROKE = "#3c5a78";
const PAPER = "#fbfaf6";

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
  const byRoomId = new Map<string, Room>(plan.rooms.map((r) => [r.id, r]));

  return (
    <div ref={containerRef} style={{ position: "absolute", inset: 0 }}>
      <svg
        width={viewW}
        height={viewH}
        viewBox={`0 0 ${viewW} ${viewH}`}
        style={{ display: "block" }}
      >
        <defs>
          <pattern
            id="paperGrid"
            width={1000 * s}
            height={1000 * s}
            patternUnits="userSpaceOnUse"
            x={offsetX}
            y={offsetY}
          >
            <path
              d={`M ${1000 * s} 0 L 0 0 0 ${1000 * s}`}
              fill="none"
              stroke={GRID_LINE}
              strokeWidth={0.5}
            />
          </pattern>
          <filter id="paperShadow" x="-5%" y="-5%" width="110%" height="110%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="2" />
            <feOffset dx="0" dy="2" result="offsetblur" />
            <feComponentTransfer>
              <feFuncA type="linear" slope="0.08" />
            </feComponentTransfer>
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* paper background */}
        <rect width={viewW} height={viewH} fill={PAPER} />
        {/* subtle 1 m grid inside the plan area */}
        <rect
          x={offsetX}
          y={offsetY}
          width={plan.boundary.width_mm * s}
          height={plan.boundary.depth_mm * s}
          fill="url(#paperGrid)"
        />

        {/* room fills (zone tint) — drop subtle drop shadow under the whole footprint */}
        <g filter="url(#paperShadow)">
          {plan.rooms.map((room) => (
            <polygon
              key={`fill-${room.id}`}
              points={polygonPoints(room.polygon, X, Y)}
              fill={ZONE_FILL[room.zone] ?? "#f4f4f1"}
              stroke="none"
            />
          ))}
        </g>

        {/* fixtures — under the walls so wall lines crisp through */}
        <g>
          {plan.fixtures.map((fx) => (
            <FixtureGlyph
              key={fx.id}
              fixture={fx}
              room={byRoomId.get(fx.room_id)}
              X={X}
              Y={Y}
            />
          ))}
        </g>

        {/* walls (poche) */}
        <g>
          {plan.walls.map((w) => (
            <WallPoche key={w.id} wall={w} X={X} Y={Y} scalePxPerMm={s} />
          ))}
        </g>

        {/* openings: doors and windows drawn last so they punch through walls cleanly */}
        <g>
          {plan.openings.map((op) => (
            <OpeningGlyph
              key={op.id}
              opening={op}
              wall={byWallId.get(op.wall_id)}
              X={X}
              Y={Y}
              scalePxPerMm={s}
            />
          ))}
        </g>

        {/* labels last so they sit on top of everything */}
        <g>
          {plan.rooms.map((room) => (
            <RoomLabel key={`lbl-${room.id}`} room={room} X={X} Y={Y} />
          ))}
        </g>

        {/* dimensions */}
        <g>
          <OverallDims plan={plan} X={X} Y={Y} />
          {plan.rooms.map((room) => (
            <RoomDims key={`dim-${room.id}`} room={room} X={X} Y={Y} />
          ))}
        </g>

        <TitleBlock plan={plan} viewH={viewH} X={X} Y={Y} scalePxPerMm={s} />
      </svg>
    </div>
  );
}

// ---------- Rendering primitives ----------

function polygonPoints(
  polygon: [number, number][],
  X: (m: number) => number,
  Y: (m: number) => number,
): string {
  return polygon.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ");
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
  const fill = wall.type === "exterior" ? INK : INK_SOFT;
  return (
    <polygon
      points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
      fill={fill}
      stroke={fill}
      strokeWidth={0.5}
      strokeLinejoin="round"
    />
  );
}

function OpeningGlyph({
  opening,
  wall,
  X,
  Y,
  scalePxPerMm,
}: {
  opening: Opening;
  wall?: Wall;
  X: (m: number) => number;
  Y: (m: number) => number;
  scalePxPerMm: number;
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
  const thicknessPx = wall.thickness_mm * scalePxPerMm;

  if (opening.kind === "door") {
    const swing = wallNormal(wall);
    const hinge = a;
    // Door leaf endpoint (90° open into the room)
    const tip = {
      x: hinge.x + swing.x * opening.width_mm,
      y: hinge.y + swing.y * opening.width_mm,
    };
    const widthPx = opening.width_mm * scalePxPerMm;
    return (
      <g>
        {/* punch the wall: a paper-coloured rectangle the size of the opening + wall thickness */}
        <PunchedOpening a={a} b={b} normal={swing} thicknessPx={thicknessPx} X={X} Y={Y} />
        {/* door leaf */}
        <line
          x1={X(hinge.x)}
          y1={Y(hinge.y)}
          x2={X(tip.x)}
          y2={Y(tip.y)}
          stroke={DOOR_STROKE}
          strokeWidth={1.4}
          strokeLinecap="round"
        />
        {/* solid 90° swing arc */}
        <path
          d={`M ${X(tip.x).toFixed(1)} ${Y(tip.y).toFixed(1)}
              A ${widthPx.toFixed(1)} ${widthPx.toFixed(1)} 0 0 ${arcSweep(dir, swing)} ${X(b.x).toFixed(1)} ${Y(b.y).toFixed(1)}`}
          fill="none"
          stroke={DOOR_STROKE}
          strokeWidth={0.8}
        />
        {/* jamb tick marks at both sides */}
        <JambTick point={a} normal={swing} thicknessPx={thicknessPx} X={X} Y={Y} />
        <JambTick point={b} normal={swing} thicknessPx={thicknessPx} X={X} Y={Y} />
      </g>
    );
  }

  // window: punch the wall, draw three parallel lines (sill + center mullion + head)
  const n = wallNormal(wall);
  const innerOffsetPx = thicknessPx * 0.5 - 0.5;
  const outerInsetMm = wall.thickness_mm * 0.25;
  const top1 = { x: a.x + n.x * outerInsetMm, y: a.y + n.y * outerInsetMm };
  const top2 = { x: b.x + n.x * outerInsetMm, y: b.y + n.y * outerInsetMm };
  const bot1 = { x: a.x - n.x * outerInsetMm, y: a.y - n.y * outerInsetMm };
  const bot2 = { x: b.x - n.x * outerInsetMm, y: b.y - n.y * outerInsetMm };
  return (
    <g>
      <PunchedOpening a={a} b={b} normal={n} thicknessPx={thicknessPx} X={X} Y={Y} />
      <line x1={X(top1.x)} y1={Y(top1.y)} x2={X(top2.x)} y2={Y(top2.y)} stroke={WINDOW_STROKE} strokeWidth={0.8} />
      <line x1={X(a.x)} y1={Y(a.y)} x2={X(b.x)} y2={Y(b.y)} stroke={WINDOW_STROKE} strokeWidth={1.1} />
      <line x1={X(bot1.x)} y1={Y(bot1.y)} x2={X(bot2.x)} y2={Y(bot2.y)} stroke={WINDOW_STROKE} strokeWidth={0.8} />
      {/* end caps */}
      <line
        x1={X(a.x) + n.x * innerOffsetPx}
        y1={Y(a.y) + n.y * innerOffsetPx}
        x2={X(a.x) - n.x * innerOffsetPx}
        y2={Y(a.y) - n.y * innerOffsetPx}
        stroke={INK_SOFT}
        strokeWidth={0.8}
      />
      <line
        x1={X(b.x) + n.x * innerOffsetPx}
        y1={Y(b.y) + n.y * innerOffsetPx}
        x2={X(b.x) - n.x * innerOffsetPx}
        y2={Y(b.y) - n.y * innerOffsetPx}
        stroke={INK_SOFT}
        strokeWidth={0.8}
      />
    </g>
  );
}

function PunchedOpening({
  a,
  b,
  normal,
  thicknessPx,
  X,
  Y,
}: {
  a: { x: number; y: number };
  b: { x: number; y: number };
  normal: { x: number; y: number };
  thicknessPx: number;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  const half = thicknessPx / 2 + 0.5;
  const pts = [
    { x: X(a.x) + normal.x * half, y: Y(a.y) + normal.y * half },
    { x: X(b.x) + normal.x * half, y: Y(b.y) + normal.y * half },
    { x: X(b.x) - normal.x * half, y: Y(b.y) - normal.y * half },
    { x: X(a.x) - normal.x * half, y: Y(a.y) - normal.y * half },
  ];
  return (
    <polygon
      points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
      fill={PAPER}
      stroke="none"
    />
  );
}

function JambTick({
  point,
  normal,
  thicknessPx,
  X,
  Y,
}: {
  point: { x: number; y: number };
  normal: { x: number; y: number };
  thicknessPx: number;
  X: (m: number) => number;
  Y: (m: number) => number;
}) {
  const half = thicknessPx / 2;
  return (
    <line
      x1={X(point.x) + normal.x * half}
      y1={Y(point.y) + normal.y * half}
      x2={X(point.x) - normal.x * half}
      y2={Y(point.y) - normal.y * half}
      stroke={INK}
      strokeWidth={0.8}
    />
  );
}

// SVG arc sweep direction depends on the cross product of the door axis and swing direction.
function arcSweep(
  doorAxis: { x: number; y: number },
  swing: { x: number; y: number },
): 0 | 1 {
  const cross = doorAxis.x * swing.y - doorAxis.y * swing.x;
  return cross > 0 ? 1 : 0;
}

// ---------- Fixture symbols ----------

function FixtureGlyph({
  fixture,
  room,
  X,
  Y,
}: {
  fixture: Fixture;
  room?: Room;
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

  // Determine which short side is "facing" the room interior. For furniture
  // glyphs like beds and sofas, this matters for the pillow/cushion side.
  const facing = inferFacing(fixture, room);

  const outline = (
    <rect
      x={X(x0)}
      y={Y(y0)}
      width={w * px}
      height={h * px}
      fill={FIXT_FILL}
      stroke={FIXT_STROKE}
      strokeWidth={0.7}
      vectorEffect="non-scaling-stroke"
    />
  );

  let glyph: JSX.Element | null = null;
  switch (fixture.kind) {
    case "bed":
    case "crib": {
      // Pillows at the head; comforter line a third of the way down.
      const isHeadVertical = facing === "right" || facing === "left";
      const headW = (isHeadVertical ? w : h) * 0.22;
      const pillowGap = headW * 0.15;
      const pillows = [];
      if (isHeadVertical) {
        const px0 = facing === "left" ? x0 : x1 - headW;
        for (let i = 0; i < 2; i++) {
          const t = (i / 2) + 0.07;
          pillows.push(
            <rect
              key={i}
              x={X(px0 + headW * 0.15)}
              y={Y(y0 + h * (t + pillowGap / h))}
              width={(headW * 0.7) * px}
              height={(h * 0.36 - pillowGap) * px}
              rx={6}
              fill="none"
              stroke={FIXT_STROKE}
              strokeWidth={0.6}
            />,
          );
        }
        glyph = (
          <g stroke={FIXT_STROKE} strokeWidth={0.6} fill="none">
            {/* head line */}
            <line
              x1={X(facing === "left" ? x0 + headW : x1 - headW)}
              y1={Y(y0)}
              x2={X(facing === "left" ? x0 + headW : x1 - headW)}
              y2={Y(y1)}
              stroke={FIXT_DETAIL}
              strokeWidth={0.6}
            />
            {pillows}
          </g>
        );
      } else {
        const py0 = facing === "up" ? y0 : y1 - headW;
        for (let i = 0; i < 2; i++) {
          const t = (i / 2) + 0.07;
          pillows.push(
            <rect
              key={i}
              x={X(x0 + w * (t + pillowGap / w))}
              y={Y(py0 + headW * 0.15)}
              width={(w * 0.36 - pillowGap) * px}
              height={(headW * 0.7) * px}
              rx={6}
              fill="none"
              stroke={FIXT_STROKE}
              strokeWidth={0.6}
            />,
          );
        }
        glyph = (
          <g stroke={FIXT_STROKE} strokeWidth={0.6} fill="none">
            <line
              x1={X(x0)}
              y1={Y(facing === "up" ? y0 + headW : y1 - headW)}
              x2={X(x1)}
              y2={Y(facing === "up" ? y0 + headW : y1 - headW)}
              stroke={FIXT_DETAIL}
              strokeWidth={0.6}
            />
            {pillows}
          </g>
        );
      }
      break;
    }
    case "sofa": {
      // Cushions + arms + back.
      const armDepth = Math.min(w, h) * 0.13;
      const horizontal = w >= h;
      if (horizontal) {
        const backH = h * 0.28;
        const cushW = (w - armDepth * 2) / 3;
        glyph = (
          <g stroke={FIXT_STROKE} strokeWidth={0.7} fill="none">
            {/* back */}
            <rect
              x={X(x0)}
              y={Y(y0)}
              width={w * px}
              height={backH * px}
              fill="#f7eedb"
            />
            {/* arms */}
            <rect x={X(x0)} y={Y(y0)} width={armDepth * px} height={h * px} fill="#f7eedb" />
            <rect x={X(x1 - armDepth)} y={Y(y0)} width={armDepth * px} height={h * px} fill="#f7eedb" />
            {/* cushion lines */}
            <line x1={X(x0 + armDepth + cushW)} y1={Y(y0 + backH)} x2={X(x0 + armDepth + cushW)} y2={Y(y1)} />
            <line x1={X(x0 + armDepth + 2 * cushW)} y1={Y(y0 + backH)} x2={X(x0 + armDepth + 2 * cushW)} y2={Y(y1)} />
          </g>
        );
      } else {
        const backW = w * 0.28;
        const cushH = (h - armDepth * 2) / 3;
        glyph = (
          <g stroke={FIXT_STROKE} strokeWidth={0.7} fill="none">
            <rect x={X(x0)} y={Y(y0)} width={backW * px} height={h * px} fill="#f7eedb" />
            <rect x={X(x0)} y={Y(y0)} width={w * px} height={armDepth * px} fill="#f7eedb" />
            <rect x={X(x0)} y={Y(y1 - armDepth)} width={w * px} height={armDepth * px} fill="#f7eedb" />
            <line x1={X(x0 + backW)} y1={Y(y0 + armDepth + cushH)} x2={X(x1)} y2={Y(y0 + armDepth + cushH)} />
            <line x1={X(x0 + backW)} y1={Y(y0 + armDepth + 2 * cushH)} x2={X(x1)} y2={Y(y0 + armDepth + 2 * cushH)} />
          </g>
        );
      }
      break;
    }
    case "toilet": {
      // Tank + rounded bowl, oriented so the tank is against the closest wall.
      const tankSide = facing; // up/down/left/right of where the wall is
      const tankH = Math.min(w, h) * 0.32;
      const bowlInset = Math.min(w, h) * 0.06;
      let tank = null;
      let bowl = null;
      if (tankSide === "up" || w >= h) {
        tank = <rect x={X(x0 + bowlInset)} y={Y(y0)} width={(w - 2 * bowlInset) * px} height={tankH * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} rx={2} />;
        bowl = <ellipse cx={X(cx)} cy={Y(y0 + tankH + (h - tankH) * 0.55)} rx={(w * 0.42) * px} ry={((h - tankH) * 0.45) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} />;
      } else if (tankSide === "down") {
        tank = <rect x={X(x0 + bowlInset)} y={Y(y1 - tankH)} width={(w - 2 * bowlInset) * px} height={tankH * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} rx={2} />;
        bowl = <ellipse cx={X(cx)} cy={Y(y0 + (h - tankH) * 0.45)} rx={(w * 0.42) * px} ry={((h - tankH) * 0.45) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} />;
      } else if (tankSide === "left") {
        tank = <rect x={X(x0)} y={Y(y0 + bowlInset)} width={tankH * px} height={(h - 2 * bowlInset) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} rx={2} />;
        bowl = <ellipse cx={X(x0 + tankH + (w - tankH) * 0.55)} cy={Y(cy)} rx={((w - tankH) * 0.45) * px} ry={(h * 0.42) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} />;
      } else {
        tank = <rect x={X(x1 - tankH)} y={Y(y0 + bowlInset)} width={tankH * px} height={(h - 2 * bowlInset) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} rx={2} />;
        bowl = <ellipse cx={X(x0 + (w - tankH) * 0.45)} cy={Y(cy)} rx={((w - tankH) * 0.45) * px} ry={(h * 0.42) * px} fill="#f7eedb" stroke={FIXT_STROKE} strokeWidth={0.7} />;
      }
      return (
        <g>
          {tank}
          {bowl}
        </g>
      );
    }
    case "sink": {
      const rim = 0.08;
      glyph = (
        <g>
          {/* basin */}
          <ellipse
            cx={X(cx)}
            cy={Y(cy)}
            rx={(w * (0.5 - rim)) * px}
            ry={(h * (0.5 - rim)) * px}
            fill="#f7eedb"
            stroke={FIXT_STROKE}
            strokeWidth={0.6}
          />
          {/* faucet tab on facing wall */}
          {(facing === "up" || facing === "down") ? (
            <rect
              x={X(cx - w * 0.06)}
              y={facing === "up" ? Y(y0 + 1) : Y(y1 - h * 0.12 - 1)}
              width={w * 0.12 * px}
              height={h * 0.12 * px}
              fill={FIXT_FILL}
              stroke={FIXT_STROKE}
              strokeWidth={0.5}
            />
          ) : (
            <rect
              x={facing === "left" ? X(x0 + 1) : X(x1 - w * 0.12 - 1)}
              y={Y(cy - h * 0.06)}
              width={w * 0.12 * px}
              height={h * 0.12 * px}
              fill={FIXT_FILL}
              stroke={FIXT_STROKE}
              strokeWidth={0.5}
            />
          )}
        </g>
      );
      break;
    }
    case "tub": {
      const inset = 0.07;
      glyph = (
        <g>
          <rect
            x={X(x0 + w * inset)}
            y={Y(y0 + h * inset)}
            width={(w * (1 - 2 * inset)) * px}
            height={(h * (1 - 2 * inset)) * px}
            rx={Math.min(w, h) * 0.12 * px}
            fill="#f7eedb"
            stroke={FIXT_STROKE}
            strokeWidth={0.7}
          />
          {/* drain */}
          <circle
            cx={X(cx)}
            cy={Y(y0 + h * (w >= h ? 0.5 : 0.8))}
            r={Math.min(w, h) * 0.04 * px}
            fill="none"
            stroke={FIXT_DETAIL}
            strokeWidth={0.5}
          />
        </g>
      );
      break;
    }
    case "table":
    case "coffee_table": {
      // Dining: rectangle with chairs around it. Coffee: just the rectangle.
      if (fixture.kind === "table") {
        const chairR = Math.min(w, h) * 0.13;
        const horizontal = w >= h;
        const chairs: JSX.Element[] = [];
        const chairFill = "#f1e6cf";
        const longCount = horizontal ? 3 : 2;
        const shortCount = horizontal ? 2 : 3;
        if (horizontal) {
          for (let i = 0; i < longCount; i++) {
            const t = (i + 1) / (longCount + 1);
            chairs.push(
              <circle key={`top${i}`} cx={X(x0 + w * t)} cy={Y(y0 - chairR * 0.8)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
              <circle key={`bot${i}`} cx={X(x0 + w * t)} cy={Y(y1 + chairR * 0.8)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
            );
          }
          for (let i = 0; i < shortCount - 1; i++) {
            const t = (i + 1) / shortCount;
            chairs.push(
              <circle key={`lf${i}`} cx={X(x0 - chairR * 0.8)} cy={Y(y0 + h * t)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
              <circle key={`rt${i}`} cx={X(x1 + chairR * 0.8)} cy={Y(y0 + h * t)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
            );
          }
        } else {
          for (let i = 0; i < longCount; i++) {
            const t = (i + 1) / (longCount + 1);
            chairs.push(
              <circle key={`lf${i}`} cx={X(x0 - chairR * 0.8)} cy={Y(y0 + h * t)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
              <circle key={`rt${i}`} cx={X(x1 + chairR * 0.8)} cy={Y(y0 + h * t)} r={chairR * px}
                fill={chairFill} stroke={FIXT_STROKE} strokeWidth={0.5} />,
            );
          }
        }
        return (
          <g>
            {chairs}
            {outline}
          </g>
        );
      }
      glyph = null;
      break;
    }
    case "counter": {
      // Kitchen counter with sink + cooktop indicators
      const horizontal = w >= h;
      glyph = horizontal ? (
        <g stroke={FIXT_STROKE} strokeWidth={0.55} fill="none">
          {/* sink basin */}
          <rect
            x={X(x0 + w * 0.18)}
            y={Y(y0 + h * 0.2)}
            width={w * 0.16 * px}
            height={h * 0.6 * px}
            rx={4}
            fill="#f4ead2"
          />
          {/* cooktop */}
          <rect
            x={X(x0 + w * 0.5)}
            y={Y(y0 + h * 0.15)}
            width={w * 0.22 * px}
            height={h * 0.7 * px}
            rx={3}
            fill="#f1e3c5"
          />
          {[0.55, 0.7].map((cxR, i) =>
            [0.32, 0.68].map((cyR, j) => (
              <circle
                key={`b${i}${j}`}
                cx={X(x0 + w * cxR)}
                cy={Y(y0 + h * cyR)}
                r={Math.min(w, h) * 0.07 * px}
                fill="none"
                stroke={FIXT_DETAIL}
                strokeWidth={0.5}
              />
            )),
          )}
          {/* oven door line */}
          <line x1={X(x0 + w * 0.5)} y1={Y(y0 + h * 0.85)} x2={X(x0 + w * 0.72)} y2={Y(y0 + h * 0.85)} stroke={FIXT_DETAIL} />
        </g>
      ) : (
        <g stroke={FIXT_STROKE} strokeWidth={0.55} fill="none">
          <rect x={X(x0 + w * 0.2)} y={Y(y0 + h * 0.18)} width={w * 0.6 * px} height={h * 0.16 * px} rx={4} fill="#f4ead2" />
          <rect x={X(x0 + w * 0.15)} y={Y(y0 + h * 0.5)} width={w * 0.7 * px} height={h * 0.22 * px} rx={3} fill="#f1e3c5" />
          {[0.32, 0.68].map((cxR, i) =>
            [0.55, 0.7].map((cyR, j) => (
              <circle
                key={`b${i}${j}`}
                cx={X(x0 + w * cxR)}
                cy={Y(y0 + h * cyR)}
                r={Math.min(w, h) * 0.07 * px}
                fill="none"
                stroke={FIXT_DETAIL}
                strokeWidth={0.5}
              />
            )),
          )}
        </g>
      );
      break;
    }
    case "fridge": {
      glyph = (
        <g stroke={FIXT_STROKE} strokeWidth={0.6} fill="none">
          <line x1={X(x0)} y1={Y(y0 + h * 0.35)} x2={X(x1)} y2={Y(y0 + h * 0.35)} />
          {/* handle */}
          <line x1={X(x0 + w * 0.2)} y1={Y(y0 + h * 0.55)} x2={X(x0 + w * 0.2)} y2={Y(y0 + h * 0.85)} strokeWidth={1.2} />
        </g>
      );
      break;
    }
    case "wardrobe":
    case "bookshelf":
    case "shelving": {
      const horizontal = w >= h;
      const splits = horizontal ? Math.max(2, Math.round(w / 800)) : Math.max(2, Math.round(h / 800));
      const lines: JSX.Element[] = [];
      for (let i = 1; i < splits; i++) {
        const t = i / splits;
        if (horizontal) {
          lines.push(<line key={i} x1={X(x0 + w * t)} y1={Y(y0)} x2={X(x0 + w * t)} y2={Y(y1)} stroke={FIXT_STROKE} strokeWidth={0.45} />);
        } else {
          lines.push(<line key={i} x1={X(x0)} y1={Y(y0 + h * t)} x2={X(x1)} y2={Y(y0 + h * t)} stroke={FIXT_STROKE} strokeWidth={0.45} />);
        }
      }
      glyph = <g>{lines}</g>;
      break;
    }
    case "desk": {
      // chair indicator: half-circle in front of the desk
      const chairR = Math.min(w, h) * 0.32;
      const chairY = facing === "up" ? y0 - chairR * 0.4 : y1 + chairR * 0.4;
      glyph = (
        <g stroke={FIXT_STROKE} strokeWidth={0.55} fill="none">
          {/* tabletop edge */}
          <line x1={X(x0)} y1={Y(y0 + h * 0.7)} x2={X(x1)} y2={Y(y0 + h * 0.7)} stroke={FIXT_DETAIL} />
          {/* chair */}
          <ellipse
            cx={X(cx)}
            cy={Y(chairY)}
            rx={chairR * px}
            ry={chairR * 0.7 * px}
            fill="#f1e6cf"
          />
        </g>
      );
      break;
    }
    case "car": {
      glyph = (
        <g stroke={FIXT_STROKE} strokeWidth={0.6} fill="none">
          <rect x={X(x0 + w * 0.06)} y={Y(y0 + h * 0.12)} width={w * 0.88 * px} height={h * 0.76 * px} rx={Math.min(w, h) * 0.12 * px} fill="#f1e6cf" />
          <rect x={X(x0 + w * 0.22)} y={Y(y0 + h * 0.22)} width={w * 0.56 * px} height={h * 0.27 * px} rx={4} fill="#fbf6e7" />
          <rect x={X(x0 + w * 0.22)} y={Y(y0 + h * 0.55)} width={w * 0.56 * px} height={h * 0.23 * px} rx={4} fill="#fbf6e7" />
        </g>
      );
      break;
    }
    case "washer":
    case "dryer": {
      glyph = (
        <g stroke={FIXT_STROKE} strokeWidth={0.6} fill="none">
          <circle cx={X(cx)} cy={Y(cy + h * 0.05)} r={Math.min(w, h) * 0.3 * px} fill="#f4ead2" />
          <circle cx={X(cx)} cy={Y(cy + h * 0.05)} r={Math.min(w, h) * 0.18 * px} fill="none" />
          <rect x={X(x0 + w * 0.1)} y={Y(y0 + h * 0.05)} width={w * 0.25 * px} height={h * 0.1 * px} stroke={FIXT_DETAIL} strokeWidth={0.4} />
        </g>
      );
      break;
    }
    case "bench":
    case "console": {
      glyph = (
        <g stroke={FIXT_STROKE} strokeWidth={0.4}>
          <line x1={X(x0 + w * 0.5)} y1={Y(y0)} x2={X(x0 + w * 0.5)} y2={Y(y1)} />
        </g>
      );
      break;
    }
    case "equipment": {
      glyph = (
        <g stroke={FIXT_DETAIL} strokeWidth={0.5} fill="none">
          <rect x={X(x0 + w * 0.2)} y={Y(y0 + h * 0.3)} width={w * 0.6 * px} height={h * 0.4 * px} />
        </g>
      );
      break;
    }
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

function inferFacing(fixture: Fixture, room?: Room): "up" | "down" | "left" | "right" {
  if (!room || room.polygon.length === 0) return "down";
  const fxs = fixture.polygon.map((p) => p[0]);
  const fys = fixture.polygon.map((p) => p[1]);
  const fx0 = Math.min(...fxs), fx1 = Math.max(...fxs);
  const fy0 = Math.min(...fys), fy1 = Math.max(...fys);
  const rxs = room.polygon.map((p) => p[0]);
  const rys = room.polygon.map((p) => p[1]);
  const rx0 = Math.min(...rxs), rx1 = Math.max(...rxs);
  const ry0 = Math.min(...rys), ry1 = Math.max(...rys);
  const distLeft = fx0 - rx0;
  const distRight = rx1 - fx1;
  const distTop = fy0 - ry0;
  const distBot = ry1 - fy1;
  const min = Math.min(distLeft, distRight, distTop, distBot);
  if (min === distTop) return "down"; // head against top wall, foot pointing down into room
  if (min === distBot) return "up";   // head against bottom wall, foot pointing up
  if (min === distLeft) return "right";
  return "left";
}

// ---------- Labels & dims ----------

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
  const xs = room.polygon.map((p) => p[0]);
  const ys = room.polygon.map((p) => p[1]);
  const minDim = Math.min(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys),
  );
  const px = X(1) - X(0);
  const fontSize = Math.max(9, Math.min(15, minDim * px * 0.055));
  return (
    <g transform={`translate(${X(cx).toFixed(1)},${Y(cy).toFixed(1)})`}>
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily='"Fraunces", "Georgia", serif'
        fill={INK}
      >
        <tspan x={0} dy="-0.4em" fontSize={fontSize} fontWeight={500} letterSpacing={0.6} style={{ textTransform: "uppercase" }}>
          {room.label}
        </tspan>
        <tspan x={0} dy="1.6em" fontSize={fontSize * 0.7} fill={DIM_TEXT} fontFamily='"Inter", system-ui, sans-serif' fontVariant="tabular-nums">
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
  const w = x1 - x0;
  const h = ys[0] !== undefined ? Math.max(...ys) - y0 : 0;
  if (w < 1800 || h < 1500) return null;

  const offset = 6;
  return (
    <g stroke={DIM_LINE} strokeWidth={0.5} fill={DIM_TEXT}>
      <line x1={X(x0)} y1={Y(y0) - offset} x2={X(x1)} y2={Y(y0) - offset} />
      <line x1={X(x0)} y1={Y(y0) - offset - 3} x2={X(x0)} y2={Y(y0) - offset + 3} />
      <line x1={X(x1)} y1={Y(y0) - offset - 3} x2={X(x1)} y2={Y(y0) - offset + 3} />
      <text
        x={(X(x0) + X(x1)) / 2}
        y={Y(y0) - offset - 3}
        textAnchor="middle"
        fontSize={8.5}
        fontFamily="Inter, system-ui, sans-serif"
        fontVariant="tabular-nums"
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
  const off = 38;
  return (
    <g stroke={INK_SOFT} strokeWidth={0.7} fill={INK_SOFT}>
      {/* horizontal */}
      <line x1={X(0)} y1={Y(0) - off} x2={X(bw)} y2={Y(0) - off} />
      <line x1={X(0)} y1={Y(0) - off - 4} x2={X(0)} y2={Y(0) - off + 4} />
      <line x1={X(bw)} y1={Y(0) - off - 4} x2={X(bw)} y2={Y(0) - off + 4} />
      <line x1={X(0)} y1={Y(0) - off} x2={X(0)} y2={Y(0)} strokeWidth={0.4} strokeDasharray="2 2" />
      <line x1={X(bw)} y1={Y(0) - off} x2={X(bw)} y2={Y(0)} strokeWidth={0.4} strokeDasharray="2 2" />
      <text
        x={(X(0) + X(bw)) / 2}
        y={Y(0) - off - 6}
        textAnchor="middle"
        fontSize={11}
        stroke="none"
        fontFamily="Inter, system-ui, sans-serif"
        fontVariant="tabular-nums"
        fill={INK}
      >
        {(bw / 1000).toFixed(2)} m
      </text>
      {/* vertical */}
      <line x1={X(bw) + off} y1={Y(0)} x2={X(bw) + off} y2={Y(bh)} />
      <line x1={X(bw) + off - 4} y1={Y(0)} x2={X(bw) + off + 4} y2={Y(0)} />
      <line x1={X(bw) + off - 4} y1={Y(bh)} x2={X(bw) + off + 4} y2={Y(bh)} />
      <line x1={X(bw) + off} y1={Y(0)} x2={X(bw)} y2={Y(0)} strokeWidth={0.4} strokeDasharray="2 2" />
      <line x1={X(bw) + off} y1={Y(bh)} x2={X(bw)} y2={Y(bh)} strokeWidth={0.4} strokeDasharray="2 2" />
      <text
        x={X(bw) + off + 8}
        y={(Y(0) + Y(bh)) / 2}
        dominantBaseline="central"
        fontSize={11}
        stroke="none"
        fontFamily="Inter, system-ui, sans-serif"
        fontVariant="tabular-nums"
        fill={INK}
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
  const ty = Math.min(viewH - 80, Y(plan.boundary.depth_mm) + 70);
  const fiveM = 5000 * scalePxPerMm;
  return (
    <g>
      <text
        x={tx}
        y={ty}
        fontSize={11}
        fontFamily="Inter, system-ui, sans-serif"
        fill={INK}
        letterSpacing={1.5}
        style={{ textTransform: "uppercase" }}
      >
        {plan.meta.title}
      </text>
      <text
        x={tx}
        y={ty + 14}
        fontSize={10}
        fontFamily="Inter, system-ui, sans-serif"
        fill={DIM_TEXT}
        letterSpacing={0.4}
      >
        Scale {plan.meta.scale}  ·  Optimized schematic
      </text>
      <g transform={`translate(${tx},${ty + 30})`}>
        <line x1={0} y1={5} x2={fiveM} y2={5} stroke={INK} strokeWidth={1} />
        <line x1={0} y1={0} x2={0} y2={10} stroke={INK} strokeWidth={1} />
        <line x1={fiveM / 2} y1={2} x2={fiveM / 2} y2={8} stroke={INK} strokeWidth={1} />
        <line x1={fiveM} y1={0} x2={fiveM} y2={10} stroke={INK} strokeWidth={1} />
        <text x={0} y={22} fontSize={9} fontFamily="Inter, system-ui, sans-serif" fill={DIM_TEXT}>
          0
        </text>
        <text x={fiveM / 2} y={22} fontSize={9} textAnchor="middle" fontFamily="Inter, system-ui, sans-serif" fill={DIM_TEXT}>
          2.5 m
        </text>
        <text x={fiveM} y={22} fontSize={9} textAnchor="middle" fontFamily="Inter, system-ui, sans-serif" fill={DIM_TEXT}>
          5 m
        </text>
      </g>
      <g transform={`translate(${X(plan.boundary.width_mm) - 32},${ty + 4})`}>
        <circle cx={0} cy={0} r={16} fill={PAPER} stroke={INK_SOFT} strokeWidth={0.7} />
        <path d="M 0 -11 L 4 5 L 0 2 L -4 5 Z" fill={INK} />
        <text x={0} y={26} textAnchor="middle" fontSize={10} fontFamily="Inter, system-ui, sans-serif" fill={INK_SOFT} letterSpacing={1.5}>
          N
        </text>
      </g>
    </g>
  );
}
