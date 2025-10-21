# Multi-Service Architecture

The simulator is delivered as four FastAPI services plus a React dashboard. Each service owns a clearly scoped domain and communicates with the others over REST using shared service credentials.

## Services and Responsibilities

| Service | Port | Responsibilities | Backing Store |
| --- | --- | --- | --- |
| Main API (`backend/`) | 8000 | Users, auth, bikes, rides, routing, analytics, reliability lab. Exposes webhooks for downstream services. | SQLite (seeded via `python -m app.seed`) |
| Pricing & Payments (`pricing_service/`) | 8101 | Fare quotes, live ride pricing, payment charge/refund flows, pricing configuration. | SQLite |
| Weather (`weather_service/`) | 8102 | Deterministic weather feed used by pricing for surge multipliers. | In-memory stub (optional cache) |
| Battery (`battery_service/`) | 8103 | Battery telemetry ingestion, drain modelling, low-charge alerts. | SQLite |

The dashboard (`frontend/`) calls each service directly using the environment variables `VITE_API_MAIN`, `VITE_API_PRICE`, `VITE_API_WEATHER`, and `VITE_API_BATTERY`.

## Data Boundaries

- The main API owns canonical user, bike, and ride records. It does not read the other services' databases.
- Pricing stores pricing versions, surge multipliers, payment records, and idempotency keys.
- Battery stores per-bike charge levels and alert thresholds.
- Weather maintains ephemeral conditions; production deployments can switch to a real provider without impacting other services.

Cross-service data moves through HTTP JSON payloads only. No service reaches into another database.

## Core Request Flows

1. **Bike discovery**: dashboard calls `GET /api/v1/bikes` on the main API. Results populate map and tables.
2. **Quote**: dashboard calls pricing `/api/v1/price/quote`, which queries weather before returning fare and multiplier.
3. **Unlock**: dashboard posts to `/api/v1/unlock`. The main API transitions the bike and creates a ride record.
4. **Ride telemetry**: dashboard posts telemetry to `/api/v1/rides/{ride_id}/telemetry` (main) and `/api/v1/battery/bikes/{bike_id}/telemetry` (battery). Pricing polls `/price/ride/{ride_id}/current` for live fare.
5. **Lock**: dashboard calls `/api/v1/lock`. The main API validates parking boundaries and freezes the fare.
6. **Charge**: dashboard calls pricing `/api/v1/payments/charge`. On success pricing notifies the main API through `/api/v1/internal/payment/notify` so the ride finalises and the bike returns to the pool.

Low battery events trigger a POST from the battery service to `/api/v1/internal/battery/low-battery`, prompting the main API to flag the bike for maintenance.

## Security and Idempotency

- Users authenticate against the main API and reuse their JWT when calling other services.
- Services authenticate to each other by sending the `X-Service-Token` header. In development the shared secret is `dev-service-token`.
- Unlock, lock, charge, and refund accept `Idempotency-Key` headers so repeat submissions are handled safely.
- All services log request IDs and timestamps, making cross-service timelines easy to correlate in the dashboard.

## Operations Notes

- Start everything from the repository root with `python scripts/dev_runner.py`, or run each service manually using the commands listed in the root README.
- Environment configuration lives in `.env` files per service; copy `.env.example` from each directory when setting up new environments.
- The services listen on localhost only. For external deployments place them behind an API gateway or reverse proxy that terminates TLS and injects service tokens.

## Future Enhancements

The current architecture leaves room for:

- Moving weather to a real provider and caching responses per zone.
- Publishing pricing and battery events over a message bus instead of direct HTTP polling.
- Promoting the service token mechanism to short-lived signed JWTs for better rotation and auditing.
- Streaming ride telemetry via WebSockets if the polling cadence becomes a bottleneck.
