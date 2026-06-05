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
