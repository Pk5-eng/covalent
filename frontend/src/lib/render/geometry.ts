// Small geometry helpers for the canvas renderer.

import type { Wall } from "../model";

export type V2 = { x: number; y: number };

export function wallVector(w: Wall): V2 {
  return { x: w.b[0] - w.a[0], y: w.b[1] - w.a[1] };
}

export function wallLength(w: Wall): number {
  const v = wallVector(w);
  return Math.hypot(v.x, v.y);
}

export function wallNormal(w: Wall): V2 {
  const v = wallVector(w);
  const len = Math.hypot(v.x, v.y) || 1;
  return { x: -v.y / len, y: v.x / len };
}

export function midpoint(a: [number, number], b: [number, number]): V2 {
  return { x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2 };
}

export function lerp(a: [number, number], b: [number, number], t: number): V2 {
  return { x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t };
}

export function add(a: V2, b: V2): V2 {
  return { x: a.x + b.x, y: a.y + b.y };
}

export function scale(v: V2, s: number): V2 {
  return { x: v.x * s, y: v.y * s };
}
