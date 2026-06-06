import { useEffect, useMemo, useRef, useState } from "react";
import { usePlanStore } from "../state/planStore";

const GRID_MM = 100;
const MIN_MM = 3000;
const MAX_MM = 30000;

function clampSnap(value: number): number {
  const snapped = Math.round(value / GRID_MM) * GRID_MM;
  return Math.max(MIN_MM, Math.min(MAX_MM, snapped));
}

export function BoundaryEditor() {
  const boundary = usePlanStore((s) => s.boundary);
  const setBoundary = usePlanStore((s) => s.setBoundary);
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragHandle, setDragHandle] = useState<null | "e" | "s" | "se">(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    if (!svgRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: r.width, h: r.height });
    });
    observer.observe(svgRef.current);
    return () => observer.disconnect();
  }, []);

  const padding = 32;
  const drawableW = Math.max(50, size.w - padding * 2);
  const drawableH = Math.max(50, size.h - padding * 2);

  // mm per pixel scale that fits the rectangle in the viewport with margin
  const scale = useMemo(() => {
    if (drawableW <= 0 || drawableH <= 0) return 1;
    return Math.min(drawableW / Math.max(MAX_MM * 0.7, boundary.width_mm),
                    drawableH / Math.max(MAX_MM * 0.7, boundary.depth_mm));
  }, [drawableW, drawableH, boundary.width_mm, boundary.depth_mm]);

  const rectW = boundary.width_mm * scale;
  const rectH = boundary.depth_mm * scale;
  const x0 = (size.w - rectW) / 2;
  const y0 = (size.h - rectH) / 2;

  useEffect(() => {
    if (!dragHandle) return;
    const onMove = (e: MouseEvent) => {
      if (!svgRef.current) return;
      const r = svgRef.current.getBoundingClientRect();
      const localX = e.clientX - r.left;
      const localY = e.clientY - r.top;
      const newWmm = (localX - x0) / scale;
      const newHmm = (localY - y0) / scale;
      if (dragHandle === "e" || dragHandle === "se") {
        setBoundary({ width_mm: clampSnap(newWmm) });
      }
      if (dragHandle === "s" || dragHandle === "se") {
        setBoundary({ depth_mm: clampSnap(newHmm) });
      }
    };
    const onUp = () => setDragHandle(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragHandle, x0, y0, scale, setBoundary]);

  // Major grid every 1m, minor every 100mm
  const minorEvery = GRID_MM * scale;
  const majorEvery = 1000 * scale;
  const showMinor = minorEvery >= 5;

  const areaM2 = ((boundary.width_mm * boundary.depth_mm) / 1_000_000).toFixed(1);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <svg
        ref={svgRef}
        style={{ width: "100%", height: "100%", display: "block", cursor: dragHandle ? "nwse-resize" : "default" }}
      >
        <defs>
          {showMinor && (
            <pattern id="minor-grid" width={minorEvery} height={minorEvery} patternUnits="userSpaceOnUse">
              <path d={`M ${minorEvery} 0 L 0 0 0 ${minorEvery}`} fill="none" stroke="#ece9e0" strokeWidth="1" />
            </pattern>
          )}
          <pattern id="major-grid" width={majorEvery} height={majorEvery} patternUnits="userSpaceOnUse">
            {showMinor && <rect width={majorEvery} height={majorEvery} fill="url(#minor-grid)" />}
            <path d={`M ${majorEvery} 0 L 0 0 0 ${majorEvery}`} fill="none" stroke="#d2cebd" strokeWidth="1" />
          </pattern>
        </defs>

        <rect width="100%" height="100%" fill="url(#major-grid)" />

        {rectW > 0 && (
          <g>
            <rect
              x={x0}
              y={y0}
              width={rectW}
              height={rectH}
              fill="rgba(42, 77, 58, 0.06)"
              stroke="#2a4d3a"
              strokeWidth={2}
            />
            {/* dimension lines */}
            <DimensionLine
              x1={x0}
              y1={y0 - 14}
              x2={x0 + rectW}
              y2={y0 - 14}
              label={`${(boundary.width_mm / 1000).toFixed(2)} m`}
            />
            <DimensionLine
              x1={x0 + rectW + 14}
              y1={y0}
              x2={x0 + rectW + 14}
              y2={y0 + rectH}
              vertical
              label={`${(boundary.depth_mm / 1000).toFixed(2)} m`}
            />
            {/* drag handles */}
            <Handle cx={x0 + rectW} cy={y0 + rectH / 2} cursor="ew-resize" onDown={() => setDragHandle("e")} />
            <Handle cx={x0 + rectW / 2} cy={y0 + rectH} cursor="ns-resize" onDown={() => setDragHandle("s")} />
            <Handle cx={x0 + rectW} cy={y0 + rectH} cursor="nwse-resize" onDown={() => setDragHandle("se")} />
            {/* center label */}
            <text
              x={x0 + rectW / 2}
              y={y0 + rectH / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#2a4d3a"
              fontSize={14}
              fontWeight={500}
            >
              {areaM2} m²
            </text>
          </g>
        )}

        <text x={12} y={size.h - 12} fill="#6b6b6b" fontSize={11}>
          Snap 100 mm · drag the edges or use the panel inputs
        </text>
      </svg>
    </div>
  );
}

function DimensionLine(props: {
  x1: number; y1: number; x2: number; y2: number;
  label: string; vertical?: boolean;
}) {
  const { x1, y1, x2, y2, label, vertical } = props;
  return (
    <g stroke="#6b6b6b" strokeWidth={1} fill="#1a1a1a">
      <line x1={x1} y1={y1} x2={x2} y2={y2} />
      <line x1={x1} y1={y1 - (vertical ? 0 : 4)} x2={x1} y2={y1 + (vertical ? 4 : 4)} />
      <line x1={x2} y1={y2 - (vertical ? 0 : 4)} x2={x2} y2={y2 + (vertical ? 4 : 4)} />
      <text
        x={(x1 + x2) / 2 + (vertical ? 6 : 0)}
        y={(y1 + y2) / 2 - (vertical ? 0 : 4)}
        textAnchor={vertical ? "start" : "middle"}
        dominantBaseline={vertical ? "central" : "auto"}
        fontSize={11}
        stroke="none"
      >
        {label}
      </text>
    </g>
  );
}

function Handle({ cx, cy, cursor, onDown }: { cx: number; cy: number; cursor: string; onDown: () => void }) {
  return (
    <g>
      {/* large invisible hit target so the handle is easy to grab */}
      <rect
        x={cx - 14}
        y={cy - 14}
        width={28}
        height={28}
        fill="transparent"
        style={{ cursor }}
        onMouseDown={(e) => {
          e.preventDefault();
          onDown();
        }}
      />
      <rect
        x={cx - 7}
        y={cy - 7}
        width={14}
        height={14}
        fill="#2a4d3a"
        stroke="#fff"
        strokeWidth={1.5}
        rx={2}
        style={{ cursor, pointerEvents: "none" }}
      />
    </g>
  );
}
