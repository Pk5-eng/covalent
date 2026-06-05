// API helpers. In dev, Vite proxies /api to the FastAPI backend.

const BASE = ""; // requests go to relative /api/*, proxied by Vite in dev.

export async function getHealth(): Promise<{ ok: boolean; service: string; version: string }> {
  const r = await fetch(`${BASE}/api/health`);
  if (!r.ok) throw new Error(`health failed: ${r.status}`);
  return r.json();
}

export async function getEcho(message: string): Promise<{ echo: string }> {
  const params = new URLSearchParams({ message });
  const r = await fetch(`${BASE}/api/echo?${params}`);
  if (!r.ok) throw new Error(`echo failed: ${r.status}`);
  return r.json();
}
