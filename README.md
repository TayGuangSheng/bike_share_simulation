# ELEN90061 Dockless Bike-Share

Teaching-realistic simulator demonstrating REST design, routing, queueing, and transport reliability concepts. Backend runs on FastAPI + SQLite; frontend (WIP) targets React 19 + Vite.

## Getting Started

```bash
# Backend
cd backend
python -m venv .venv && .\.venv\Scripts\activate      # use source .../bin/activate on macOS/Linux
pip install -r requirements.txt
python -m app.seed
make dev

# Frontend (placeholder scaffolding)
cd ../frontend
npm install
npm run dev
```

Useful commands (`backend/Makefile`):

| Command | Description |
| --- | --- |
| `make dev` | Start FastAPI dev server (http://localhost:8000/docs) |
| `make seed` | Seed SQLite with demo users, bikes, zones, pricing, graph edges |
| `make test` | Run pytest suite with coverage (expected >=92%) |
| `make lint` | Run Ruff + Black checks |

## Key Backend Features (MVP)

- JWT auth, role-aware dependencies (user vs admin).
- Bike & Ride FSM enforcement with idempotent unlock/lock flows (`Idempotency-Key` required).
- Telemetry ingestion with Haversine distance, MET calories, fare calculation (banker's rounding).
- Geofencing: parking/no-park zones with 5 m buffer and nearest parking routing hints.
- Payments simulator (authorize/capture/refund) with idempotent gateway semantics.
- Routing service exposing shortest vs safest Dijkstra variants (toy + civic graphs).
- Analytics endpoints (fleet KPIs, M/M/1 and M/M/m queueing) and Reliability Lab (lossy channel + stop-and-wait ACK).

## Tests

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

See `docs/API.md` for endpoint details and `docs/REPORT.md` for the evolving design report.
