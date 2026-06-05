import type {
  Boundary,
  CatalogRoom,
  ProgramCheckResponse,
  RoomRequest,
} from "./model";

const BASE = "";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${path} ${r.status}: ${text || r.statusText}`);
  }
  return r.json() as Promise<T>;
}

export async function getHealth(): Promise<{ ok: boolean; service: string; version: string }> {
  return jsonFetch("/api/health");
}

export async function getEcho(message: string): Promise<{ echo: string }> {
  const params = new URLSearchParams({ message });
  return jsonFetch(`/api/echo?${params}`);
}

export async function getCatalog(): Promise<{ rooms: CatalogRoom[] }> {
  return jsonFetch("/api/catalog");
}

export async function checkProgram(
  boundary: Boundary,
  rooms: RoomRequest[],
): Promise<ProgramCheckResponse> {
  return jsonFetch("/api/program/check", {
    method: "POST",
    body: JSON.stringify({ boundary, rooms }),
  });
}

// Program (no geometry) emitted by the architect agent. The full Program type
// will live alongside the engine's FloorPlan once Step 4 lands.
export type AgentProgram = {
  units: "mm";
  global: {
    circulation_target_pct: number;
    group_wet_rooms: boolean;
    primary_entry_side: "north" | "south" | "east" | "west";
  };
  rooms: {
    id: string;
    type: string;
    label: string;
    zone: "public" | "private" | "service" | "exterior";
    target_area_m2: number;
    min_width_m: number;
    priority: number;
    needs_exterior_wall: boolean;
    needs_window: boolean;
    needs_egress: boolean;
    adjacent_to: string[];
    not_adjacent_to: string[];
  }[];
  circulation: { entry_room_id: string; notes: string };
};

export async function generateProgram(
  boundary: Boundary,
  rooms: RoomRequest[],
): Promise<{ program: AgentProgram; summary: { boundary_area_m2: number; usable_area_m2: number } }> {
  return jsonFetch("/api/program/generate", {
    method: "POST",
    body: JSON.stringify({ boundary, rooms }),
  });
}
