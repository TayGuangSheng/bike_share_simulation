# API Reference

The simulator exposes four FastAPI services under `/api/v1`. Unless stated otherwise, requests require a JWT bearer token in the `Authorization` header (`Bearer <access_token>`). Mutating endpoints that may be retried accept an `Idempotency-Key` header.

- Main API: http://localhost:8000/api/v1
- Pricing & Payments Service: http://localhost:8101/api/v1
- Weather Service: http://localhost:8102/api/v1
- Battery Service: http://localhost:8103/api/v1

Seed logins issued by the main API:

| Email | Password | Role |
| --- | --- | --- |
| `admin@demo` | `admin123` | Admin |
| `user@demo` | `user123` | Rider |

## Authentication (Main API)

| Method | Path | Description | Notes |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | Accepts `{email, password}` and returns `{access_token, token_type}`. | Use credentials above for local development. |

## Bikes & Ride Lifecycle (Main API)

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/bikes` | List bikes; optional filters `near_lat`, `near_lon`, `radius_m`. | User |
| `GET` | `/bikes/{bike_id}` | Retrieve a single bike. | User |
| `PATCH` | `/bikes/{bike_id}` | Update `lat`, `lon`, `status`, or `battery_pct`. | Admin |
| `POST` | `/unlock` | Unlock by `{qr_public_id}`. Response includes `ride` and `bike`. Idempotent. | User |
| `POST` | `/rides/{ride_id}/telemetry` | Append telemetry sample `{lat, lon, speed_mps, ts}`. | User |
| `POST` | `/lock` | Finalise ride `{ride_id, lat, lon}`. Validates parking geofences. | User |

Successful locks return latest ride metrics (`meters`, `seconds`, `calories_kcal`, `fare_cents`, `pricing_version`). On failure the API responds with HTTP 409 and supplies the nearest legal parking location.

## Routing & Analytics (Main API)

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `POST` | `/routes` | Compute Dijkstra route for `{from, to, variant}`. | User |
| `GET` | `/analytics/kpis` | Fleet KPIs (rides per hour, unlock failures, etc.). | Admin |
| `GET` | `/analytics/queue` | Queueing metrics for `{lambda, mu, m}`. | Admin |
| `POST` | `/lab/config` | Configure lossy transport demo `{drop_prob, dup_prob, corrupt_prob}`. | Admin |
| `POST` | `/lab/unreliable` | Submit unreliable message `{seq, checksum?, data}`. | User |
| `POST` | `/lab/ack` | Send stop-and-wait ACK `{seq}`. | User |
| `GET` | `/lab/history` | Inspect recent unreliable channel events. | Admin |

## Pricing & Payments Service

| Method | Path | Description | Headers |
| --- | --- | --- | --- |
| `GET` | `/price/quote?bike_id=&lat=&lon=` | Return surge multiplier, base fare, and weather context for a candidate bike. | `Authorization`, `Idempotency-Key` optional |
| `GET` | `/price/ride/{ride_id}/current?meters=&seconds=` | Live fare estimate for an active ride. | `Authorization` |
| `POST` | `/payments/charge` | Charge a ride. Body `{ride_id, amount_cents?, meters?, seconds?}`. Amount defaults to main API fare. | `Authorization`, `Idempotency-Key` |
| `POST` | `/payments/refund` | Refund a captured payment `{payment_id}`. | `Authorization`, `Idempotency-Key` |
| `GET` | `/payments/records` | Paginated payment history. Filters: `ride_id`, `status`. | `Authorization` |

On successful charge or refund the service posts to the main API hook `/internal/payment/notify` using the shared service token.

## Weather Service

| Method | Path | Description | Headers |
| --- | --- | --- | --- |
| `GET` | `/weather/current?lat=&lon=` | Return `{condition, temperature_c, precip_mm, wind_kph, humidity_pct, as_of}`. | `X-Service-Token` for service-to-service calls; user requests may reuse JWT. |

## Battery Service

| Method | Path | Description | Headers |
| --- | --- | --- | --- |
| `POST` | `/battery/bikes/{bike_id}/telemetry` | Body `{ride_id, lat, lon, speed_mps, ts}`. Response `{battery_pct}`. | `Authorization` |
| `GET` | `/battery/bikes/{bike_id}` | Current battery state and alert flags. | `Authorization` |

Low-charge alerts trigger a POST to `/internal/battery/low-battery` on the main API with the shared service token (`SERVICE_TOKEN`).

## Error Responses

Errors follow FastAPI's default payload:

```json
{
  "detail": "message"
}
```

Validation issues respond with `detail` as an array of field errors. Idempotency conflicts and ride state violations use HTTP 409 with a descriptive message.
