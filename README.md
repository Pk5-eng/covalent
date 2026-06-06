# Covalent

AI-assisted floor plan generator. Architect agent (Claude) emits a program + adjacency graph; a deterministic slicing-tree + simulated annealing engine packs the geometry; DXF export.

Read [`CLAUDE.md`](./CLAUDE.md) before changing anything. Full spec lives in [`docs/covalent-build-spec.md`](./docs/covalent-build-spec.md).

## Run locally

### Backend (Python 3.11+)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # required from Step 3 onward
uvicorn app.main:app --reload --port 8000
```

Backend listens on `http://localhost:8000`. Sanity-check:

```bash
curl http://localhost:8000/api/health
curl 'http://localhost:8000/api/echo?message=hi'
```

### Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev
```

Frontend listens on `http://localhost:5173`. Vite proxies `/api/*` to the backend on `:8000` (override with `VITE_API_TARGET`).

### Tests

```bash
cd backend && pytest -q
cd frontend && npm run typecheck
```

## Project layout

```
covalent/
  CLAUDE.md                 # session preamble — locked constraints + plan
  docs/covalent-build-spec.md
  frontend/                 # Vite + React + TS, raw SVG canvas
  backend/                  # FastAPI, agent + engine + DXF exporter
```

See `CLAUDE.md` for the build sequence (Steps 1–7) and `docs/covalent-build-spec.md` for full design.

## Deploy

Backend on **Railway**, frontend on **Vercel**. The frontend keeps using
relative `/api/*` URLs in prod and Vercel rewrites them to the Railway URL,
so no `VITE_*` env vars are needed at build time.

### Backend → Railway

1. New project from this repo, set **root directory** to `backend/`.
2. Railway will pick up `backend/Procfile` + `backend/nixpacks.toml` and run
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Add environment variables in the Railway dashboard:
   - `ANTHROPIC_API_KEY` — your Anthropic API key (required for the architect agent; without it the deterministic fallback kicks in).
   - `COVALENT_CORS_ORIGINS` — comma-separated origins allowed to call the API; set to your Vercel URL after the frontend is up (e.g. `https://covalent.vercel.app`).
   - `COVALENT_AGENT_MODEL` *(optional)* — defaults to `claude-opus-4-7`. Use `claude-sonnet-4-6` for cheaper/faster runs.
   - `COVALENT_LOG` *(optional)* — defaults to `INFO`.
4. Deploy. Copy the generated URL (e.g. `covalent-backend.up.railway.app`).
5. Sanity-check: `curl https://YOUR-RAILWAY-URL/api/health` returns ok.

### Frontend → Vercel

1. Import this repo, set **root directory** to `frontend/`. Framework auto-detects as Vite (build `npm run build`, output `dist`).
2. Edit `frontend/vercel.json` and replace `REPLACE-WITH-RAILWAY-URL` with your Railway host, e.g.:
   ```json
   "destination": "https://covalent-backend.up.railway.app/api/:path*"
   ```
3. Commit + push. Vercel auto-deploys.
4. Once the Vercel URL is live, go back to Railway and update `COVALENT_CORS_ORIGINS` to the Vercel URL, then redeploy the backend.

### Notes

- Annealing runs synchronously inside the request (10–30 s with default 4×4000 iterations). Railway's default request timeout is 60 s; lower the iteration count via a custom `AnnealConfig` if you hit it.
- The agent's prompt and the DXF layer names are locked across SVG + DXF in `frontend/src/lib/render/layers.ts` and `backend/app/export/dxf_export.py`; keep them in sync if you ever rename a layer.

## Scope reminders

- DXF only. No DWG.
- Rectangular boundary only.
- Editing: regenerate + resize one room. Nothing else.
- No auth. Anonymous session id.
- LLM never outputs geometry. Slicing-tree + simulated annealing is the fixed layout method.
