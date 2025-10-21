# ELEN90061 Dockless Bike-Share – Project Report

## 1. Introduction

This project delivers a teaching-focused dockless bike-share simulator built for the ELEN90061 curriculum. The objective is to illustrate REST design, routing optimisation, transport reliability, and queueing theory using a cohesive, hands-on system. The release tagged for production includes the fully functional rider emulator, multi-service backend, and supporting documentation.

## 2. System Design

- **Service Topology**: Four FastAPI services (main API, pricing & payments, weather, battery) plus a React/Vite dashboard. Each service owns a bounded context and communicates over REST with shared service tokens.
- **Authentication & Security**: JWT bearer tokens for users, `X-Service-Token` for service-to-service calls, and idempotency headers on critical write operations (unlock, lock, charge, refund).
- **Domain Models**: Bike and ride finite state machines, pricing revisions and payment records, telemetry ingestion with distance and calorie calculations, and geofence enforcement with nearest-parking hints.
- **Routing**: Dijkstra variants (shortest and safest) built on seeded civic and toy graphs to demonstrate graph theory concepts.
- **Pricing Engine**: Dynamic pricing reacts to weather multipliers and live ride metrics. Payments are simulated end-to-end with charge and refund flows.
- **Battery Modelling**: Telemetry-driven drain with alert thresholds that trigger maintenance workflows.

## 3. Learning Outcomes Alignment

- **REST & Web Engineering**: Stateless APIs, structured error responses, and idempotent POST semantics surfaced through the rider emulator timeline.
- **Routing Theory**: Interactive comparison of route variants alongside the reliability lab that models lossy channels and acknowledgements.
- **Queueing Theory**: `/analytics/queue` endpoint and dashboard visuals expose M/M/1 and M/M/m metrics for lecture tie-ins.
- **Distributed Systems Practices**: Clear separation of services, explicit contracts, webhooks, and observability through the dashboard’s service activity feeds.

## 4. Validation

- **Automated Testing**: `pytest --cov=app --cov-report=term-missing` achieves ≥92% coverage across the main API.
- **Manual Walkthrough**: Rider emulator exercises the full unlock → telemetry → lock → charge cycle with synchronized logs from every service.
- **Performance**: Live map and bike inventory poll every two seconds while remaining under local resource limits. Poll intervals are configurable for different environments.

## 5. Deployment & Operations

- Start all services with `python scripts/dev_runner.py` or launch each individually as documented in the root README.
- Environment variables are captured in per-service `.env` samples; the default `SERVICE_TOKEN` is `dev-service-token`.
- Observability is provided via prefixed process logs, the dashboard timeline, and FastAPI docs at `/docs` for each service.

## 6. Roadmap

Future iterations may include:

- Migrating weather to a real data provider and enriching surge calculations with historical demand.
- Introducing WebSocket or SSE streams for telemetry to reduce polling overhead.
- Adding maintenance tooling such as battery replacement workflows and spare bike logistics.
- Expanding analytics with cohort analysis, revenue forecasting, and incident tracking dashboards.
