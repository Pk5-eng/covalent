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

## Scope reminders

- DXF only. No DWG.
- Rectangular boundary only.
- Editing: regenerate + resize one room. Nothing else.
- No auth. Anonymous session id.
- LLM never outputs geometry. Slicing-tree + simulated annealing is the fixed layout method.
