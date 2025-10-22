from __future__ import annotations

import json
import os
import time
from urllib import request

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chaos import ChaosFlavor, ChaosMiddleware, ChaosMode, get_status as get_chaos_status, set_profile as set_chaos_profile


app = FastAPI(title="Battery Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Chaos-Effect", "X-Chaos-Delay", "X-Chaos-Stale", "X-Chaos-State"],
)
app.add_middleware(
    ChaosMiddleware,
    service_name="battery",
    exclude_paths=("/api/v1/dev/chaos", "/docs", "/openapi.json"),
)


SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token")
MAIN_BASE_URL = os.getenv("MAIN_BASE_URL", "http://localhost:8000")
LOW_BATTERY_THRESHOLD = float(os.getenv("LOW_BATTERY_THRESHOLD", "25"))
TELEMETRY_DRAIN_PER_SECOND = float(os.getenv("BATTERY_DRAIN_PER_SECOND", "0.08"))
TELEMETRY_DRAIN_PER_SPEED = float(os.getenv("BATTERY_DRAIN_PER_SPEED", "0.6"))


class TelemetryPayload(BaseModel):
    ride_id: int
    lat: float
    lon: float
    speed_mps: float = Field(ge=0)
    ts: float = Field(description="epoch seconds")


class BatteryState(BaseModel):
    bike_id: int
    battery_pct: float
    last_updated_at: float
    notified: bool = False


class ChaosProfileIn(BaseModel):
    mode: str
    flavor: str = "mixed"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class ChaosStatusOut(BaseModel):
    profile: dict
    events: list[dict]
    failure_streak: int
    circuit_open_until: float


BATTERY_STATE: dict[int, BatteryState] = {}


def _now() -> float:
    return time.time()


def _notify_low_battery(bike_id: int, battery_pct: float) -> None:
    url = f"{MAIN_BASE_URL}/api/v1/internal/battery/low-battery"
    payload = json.dumps(
        {
            "bike_id": bike_id,
            "battery_pct": int(round(battery_pct)),
            "threshold": int(round(LOW_BATTERY_THRESHOLD)),
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Service-Token": SERVICE_TOKEN}
    req = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=3) as resp:
            resp.read()
    except Exception as exc:  # pragma: no cover - best effort notify
        print(f"battery notify failed: {exc}")


@app.post("/api/v1/battery/rides/{ride_id}/start", status_code=status.HTTP_202_ACCEPTED)
def ride_start(ride_id: int) -> dict:
    return {"ok": True, "ride_id": ride_id}


@app.post("/api/v1/battery/rides/{ride_id}/end", status_code=status.HTTP_202_ACCEPTED)
def ride_end(ride_id: int) -> dict:
    return {"ok": True, "ride_id": ride_id}


@app.post("/api/v1/battery/bikes/{bike_id}/telemetry")
def battery_telemetry(bike_id: int, payload: TelemetryPayload) -> dict:
    if payload.ts <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid timestamp")

    state = BATTERY_STATE.get(bike_id)
    if state is None:
        state = BatteryState(bike_id=bike_id, battery_pct=100.0, last_updated_at=payload.ts, notified=False)
        BATTERY_STATE[bike_id] = state

    elapsed = max(payload.ts - state.last_updated_at, 0.0)
    drain = elapsed * TELEMETRY_DRAIN_PER_SECOND + payload.speed_mps * TELEMETRY_DRAIN_PER_SPEED * 0.01
    new_pct = max(0.0, state.battery_pct - drain)

    state.battery_pct = new_pct
    state.last_updated_at = payload.ts

    if new_pct <= LOW_BATTERY_THRESHOLD and not state.notified:
        state.notified = True
        _notify_low_battery(bike_id, new_pct)
    elif new_pct > LOW_BATTERY_THRESHOLD:
        state.notified = False

    return {"bike_id": bike_id, "battery_pct": round(state.battery_pct, 1), "notified": state.notified}


def _validate_token(token: str | None) -> None:
    if not token or token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


@app.post("/api/v1/dev/chaos", response_model=ChaosStatusOut)
def configure_chaos(
    payload: ChaosProfileIn,
    service_token: str | None = Header(default=None, alias="X-Service-Token"),
) -> ChaosStatusOut:
    _validate_token(service_token)
    set_chaos_profile(ChaosMode(payload.mode), ChaosFlavor(payload.flavor), payload.intensity, updated_by="backend")
    snapshot = get_chaos_status()
    return ChaosStatusOut(**snapshot)


@app.get("/api/v1/dev/chaos", response_model=ChaosStatusOut)
def chaos_status(
    service_token: str | None = Header(default=None, alias="X-Service-Token"),
) -> ChaosStatusOut:
    _validate_token(service_token)
    snapshot = get_chaos_status()
    return ChaosStatusOut(**snapshot)
