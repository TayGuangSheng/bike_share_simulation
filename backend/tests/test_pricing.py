from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.db import SessionLocal
from app.models import EventLog, PricingPlan

from .helpers import auth_header, login_token


def _expected_multiplier(
    *,
    base_multiplier: float,
    weather: str,
    demand_slope: float,
    demand_threshold: int,
    min_multiplier: float,
    max_multiplier: float,
    active_rides: int,
) -> float:
    weather_factor = {"clear": 1.0, "rain": 0.9, "storm": 0.8}.get(weather, 1.0)
    demand_excess = max(0, active_rides - demand_threshold)
    demand_factor = 1.0 + demand_slope * demand_excess
    multiplier = base_multiplier * weather_factor * demand_factor
    return max(min_multiplier, min(max_multiplier, multiplier))


@pytest.mark.usefixtures("reset_db")
def test_dynamic_pricing_flow(client: TestClient) -> None:
    admin_token = login_token(client)
    headers = auth_header(admin_token)

    update_payload = {
        "weather": "storm",
        "base_multiplier": 1.2,
        "demand_slope": 0.1,
        "demand_threshold": 0,
        "min_multiplier": 0.5,
        "max_multiplier": 2.0,
    }
    put_resp = client.put("/api/v1/pricing/config", headers=headers, json=update_payload)
    assert put_resp.status_code == 200, put_resp.text
    config_out = put_resp.json()

    expected_idle_multiplier = _expected_multiplier(
        active_rides=0,
        **update_payload,
    )
    assert config_out["current_multiplier"] == pytest.approx(expected_idle_multiplier, rel=1e-6)
    assert config_out["last_updated_at"] is not None

    current = client.get("/api/v1/pricing/current", headers=headers)
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["multiplier"] == pytest.approx(expected_idle_multiplier, rel=1e-6)
    assert current_payload["active_rides"] == 0

    bikes = client.get("/api/v1/bikes", headers=headers).json()
    bike = bikes[0]

    unlock_headers = {**headers, "Idempotency-Key": "dp-ride-1"}
    unlock_payload = {"qr_public_id": bike["qr_public_id"]}
    unlock = client.post("/api/v1/unlock", headers=unlock_headers, json=unlock_payload)
    assert unlock.status_code == 200, unlock.text
    unlock_body = unlock.json()
    ride_id = unlock_body["ride"]["id"]

    assert unlock_body["ride"]["dynamic_multiplier_start"] == pytest.approx(expected_idle_multiplier, rel=1e-6)

    expected_active_multiplier = _expected_multiplier(
        active_rides=1,
        **update_payload,
    )

    current_after_unlock = client.get("/api/v1/pricing/current", headers=headers)
    assert current_after_unlock.status_code == 200
    current_after_payload = current_after_unlock.json()
    assert current_after_payload["active_rides"] == 1
    assert current_after_payload["multiplier"] == pytest.approx(expected_active_multiplier, rel=1e-6)

    telemetry_points = [
        {"lat": bike["lat"] + 0.0002, "lon": bike["lon"] + 0.0002, "speed_mps": 3.5, "ts": 100.0},
        {"lat": bike["lat"] + 0.0004, "lon": bike["lon"] + 0.0004, "speed_mps": 3.5, "ts": 110.0},
        {"lat": bike["lat"] + 0.0006, "lon": bike["lon"] + 0.0006, "speed_mps": 3.5, "ts": 130.0},
    ]
    for point in telemetry_points:
        telemetry = client.post(f"/api/v1/rides/{ride_id}/telemetry", headers=headers, json=point)
        assert telemetry.status_code == 200, telemetry.text

    lock_headers = {**headers, "Idempotency-Key": "dp-lock-1"}
    lock_payload = {"ride_id": ride_id, "lat": bike["lat"] + 0.0006, "lon": bike["lon"] + 0.0006}
    lock = client.post("/api/v1/lock", headers=lock_headers, json=lock_payload)
    assert lock.status_code == 200, lock.text
    lock_body = lock.json()

    ride_out = lock_body["ride"]
    metrics = ride_out["metrics"]
    assert ride_out["dynamic_multiplier_end"] == pytest.approx(expected_active_multiplier, rel=1e-6)

    with SessionLocal() as session:
        plan: PricingPlan = (
            session.query(PricingPlan).filter(PricingPlan.is_active.is_(True)).order_by(PricingPlan.version.desc()).first()
        )
        assert plan is not None
        base_fare = (
            plan.base_cents
            + plan.per_min_cents * (metrics["seconds"] / 60.0)
            + plan.per_km_cents * (metrics["meters"] / 1000.0)
        )
        expected_fare = base_fare * plan.surge_multiplier * expected_active_multiplier
        assert metrics["fare_cents"] == int(round(expected_fare))

        pricing_events = session.query(EventLog).filter(EventLog.component == "pricing").all()
        assert pricing_events, "expected pricing config change to be logged"
        assert any("base_multiplier" in (event.payload_json or {}).get("changes", {}) for event in pricing_events)
