# REST API Overview

Base URL: `/api/v1`. All `POST` endpoints listed below require an `Idempotency-Key` header unless noted otherwise. Authentication uses JWT bearer tokens supplied via `Authorization: Bearer <token>`.

## Auth

| Method | Path | Description | Notes |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | Exchange `{email, password}` for `{access_token, token_type}` | Seed credentials: `admin@demo/admin123`, `user@demo/user123` |

## Bikes & Operations

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/bikes` | List bikes optionally filtered by `near_lat`, `near_lon`, `radius_m` | User |
| `GET` | `/bikes/{id}` | Retrieve bike details | User |
| `PATCH` | `/bikes/{id}` | Admin updates bike latitude, longitude, `status`, or `battery_pct` | Admin |

## Ride Lifecycle

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/unlock` | Unlock by `{qr_public_id}` -> `{unlock_token, ride, bike}` (enforces bike & ride FSM and idempotency) |
| `POST` | `/rides/{ride_id}/telemetry` | Append telemetry sample `{lat, lon, speed_mps, ts}`; updates meters, seconds, calories, polyline |
| `POST` | `/lock` | Attempt to lock with `{ride_id, lat, lon}`; validates geofences (parking buffer +/- 5 m, blocks no-park) |

Responses include ride metrics `{meters, seconds, calories_kcal, fare_cents, pricing_version}` and on lock failure provide `nearest_parking_route`.

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/routes` | Compute Dijkstra route between `{from:{lat,lon}, to:{lat,lon}, variant:'shortest'|'safest', graph?}` returning `{polyline_geojson, total_distance_m, est_time_s, nodes, start_node, end_node}` |

## Payments

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/payments/authorize` | Authorize `{ride_id, amount_cents}` exactly matching ride fare |
| `POST` | `/payments/capture` | Capture authorized payment `{payment_id}` and transition ride to `billed` |
| `POST` | `/payments/refund` | Refund captured payment `{payment_id}` and transition ride to `refunded` |

All payment mutations are idempotent via the `Idempotency-Key`.

## Analytics & Reliability

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/analytics/kpis` | Fleet KPIs: rides/hour, average fare/length, unlock failures, stockouts, violations | Admin |
| `GET` | `/analytics/queue` | Queueing metrics for lambda, mu, m -> `{rho, wq, w, lq, l}` | Admin |
| `POST` | `/lab/config` | Configure lossy transport probabilities `{drop_prob, dup_prob, corrupt_prob}` | Admin |
| `POST` | `/lab/unreliable` | Submit `{seq, checksum?, data}` through unreliable channel -> delivery timeline events | User |
| `POST` | `/lab/ack` | Send stop-and-wait ack `{seq}` | User |
| `GET` | `/lab/history` | Retrieve recent unreliability events | Admin |

## Error Formats

Errors follow FastAPI's default JSON structure:

```json
{
  "detail": "message" | { "error": "message", ... }
}
```

Concurrency violations, FSM errors, and idempotency conflicts use `409 Conflict` with descriptive messages and remediation hints (e.g., nearest parking route).
