# ELEN90061 Dockless Bike-Share

Teaching-realistic simulator for dockless bike-share operations. The stack combines a FastAPI + SQLite core API, three auxiliary microservices (pricing, battery, weather), and a React 19 + Vite dashboard that emulates the rider experience.

## Get Started
- Install Python 3.11+ and Node.js 20+ (with npm) on your machine.
- Create a virtual environment once, install backend requirements, then install frontend dependencies.

```bash
# from the repository root
python -m venv .venv
.venv\Scripts\activate                  # use: source .venv/bin/activate on macOS/Linux
pip install -r backend/requirements.txt
cd frontend
npm install
```

Configure `frontend/.env.local` (or export the variables) so the dashboard can access every service:

```bash
VITE_API_MAIN=http://localhost:8000
VITE_API_PRICE=http://localhost:8101
VITE_API_WEATHER=http://localhost:8102
VITE_API_BATTERY=http://localhost:8103
```

All services share the same bearer token (`SERVICE_TOKEN=dev-service-token` by default). Override it in your shell when you want to exercise stricter auth.

## Launch the Emulator

The quickest way to bring the stack online is the orchestration script:

```bash
# activate your venv first if you created one
python scripts/dev_runner.py
```

The runner seeds the SQLite database, then starts the FastAPI backend plus pricing, weather, and battery services before booting the Vite dev server. Logs from every process are multiplexed with prefixes; press `Ctrl+C` once to stop the entire simulator.

Prefer manual control? You can launch each service individually (still from the repo root):

```bash
uvicorn app.main:app --reload --port 8000                 # backend
uvicorn pricing_service.app.main:app --reload --port 8101 # pricing + payments
uvicorn weather_service.app.main:app --reload --port 8102 # weather
uvicorn battery_service.app.main:app --reload --port 8103 # battery
cd frontend && npm run dev                                # dashboard
```

Once the UI compiles, open the printed Vite URL (default http://localhost:5173) and log in with one of the seeded accounts:

| Email | Password | Role |
| --- | --- | --- |
| `admin@demo` | `admin123` | Admin |
| `user@demo` | `user123` | Rider |

## Use the Rider Dashboard
- Open the URL printed by Vite (default http://localhost:5173) in your browser.
- Authenticate first—the app redirects to the login screen on first load.
- Select a simulated rider, choose a bike, and use the `Scan & Unlock`, `Ride`, `Lock`, and `Charge` controls to walk through a full trip.
- Watch the service timeline cards: every UI action streams the exact HTTP requests logged by the backend, pricing, weather, and battery services so you can connect client behaviour to server processing.
- The Quote panel shows the live fare calculation. The pricing service polls the backend for ride metrics, calls the weather service for surge conditions, and surfaces the computed fare back to the dashboard.
- Battery telemetry uploads run in the background during a ride. Locking the bike finalises the fare, and the charge flow posts to the payment endpoint to simulate capture.

### What Happens Per Action?
- `Scan & Unlock`: the frontend requests the bike catalogue, posts an unlock command, and the backend opens ride state while waiting for telemetry.
- `Ride`: telemetry samples hit `/api/v1/rides/{ride_id}/telemetry`; the pricing service keeps polling `/api/v1/price/ride/{ride_id}/current`, and weather lookups inform the multiplier.
- `Lock`: the backend finalises the ride, freezes the fare, and reports that payment is ready.
- `Charge`: the frontend triggers `POST /api/v1/payments/charge`; the pricing service records the capture, and the dashboard confirms payment success.

## Service Architecture Overview

| Service | Purpose | Default Port |
| --- | --- | --- |
| Backend API (`backend/`) | Auth, ride state machine, bike catalogue, telemetry ingestion, orchestrates downstream calls | 8000 |
| Pricing Service (`pricing_service/`) | Fare engine, payment capture simulator, weather-aware multipliers | 8101 |
| Weather Service (`weather_service/`) | Supplies weather data used by pricing for surge modelling | 8102 |
| Battery Service (`battery_service/`) | Tracks battery telemetry, raises low-charge alerts | 8103 |
| Frontend dashboard (`frontend/`) | Vite + React rider emulator and live log visualiser | 5173 (default) |

Services communicate over REST with shared bearer-token auth. The backend emits signed callbacks to pricing for ride updates; pricing and battery push telemetry back to the backend; weather is queried on demand.

## Developer Shortcuts
- `make dev` (inside `backend/`) starts the FastAPI server at http://localhost:8000/docs.
- `make seed` reseeds SQLite with demo riders, bikes, zones, pricing rules, and routing graphs.
- `make test` runs the pytest suite with coverage (target >=92%).
- `make lint` executes Ruff and Black for linting and formatting.

Further reference material lives in `docs/API.md` (endpoint catalogue) and `docs/REPORT.md` (design notes, transport and queueing experiments).
