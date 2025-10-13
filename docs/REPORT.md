# ELEN90061 Dockless Bike-Share - Report Skeleton

## 1. Introduction
- Motivation: dockless operations, admin-first analytics, alignment with ELEN90061 topics.
- Scope: MVP feature flag (`FEATURE_ADVANCED=false`) delivered; advanced roadmap noted for future work.

## 2. Design Snapshot
- Stateless REST API (FastAPI) with JWT auth and per-endpoint idempotency keys.
- Domain model: Bike and Ride FSMs, payments, geofences, telemetry, seeded civic graph.
- Routing: Dijkstra variants (shortest vs safest) with toy and civic graphs for demonstrations.
- Telemetry pipeline: Haversine distance, MET-based calories, banker-style rounding for fares.

## 3. Theory Mapping
- Application/REST: stateless interactions, structured errors, idempotent POST semantics.
- Routing: edge cost modelling using distance, turn penalties, safe scores.
- Transport reliability: lossy channel plus stop-and-wait ACK demo.
- Queueing: M/M/1 and M/M/m metrics exposed via `/analytics/queue`.

## 4. Results & Evidence (to expand)
- Backend automated tests: `pytest --cov` currently reports coverage >=92%.
- Sample ride flow: unlock -> telemetry -> lock -> idempotent payments (see backend tests).
- Comparative study placeholders:
  - Shortest vs safest route (distance, time, zone violations).
  - Flat vs surge pricing (revenue, rider cost distribution).

## 5. Conclusion & Next Steps
- Remaining gaps: frontend parity with design spec, smoothing toggle, full advanced feature set.
- Planned enhancements: async telemetry smoothing, maintenance Kanban UI, richer analytics dashboards.
