from __future__ import annotations

import math
import os
import time
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chaos import ChaosFlavor, ChaosMiddleware, ChaosMode, get_status as get_chaos_status, set_profile as set_chaos_profile


app = FastAPI(title="Weather Service", version="0.1.0")

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
    service_name="weather",
    exclude_paths=("/api/v1/dev/chaos", "/docs", "/openapi.json"),
)


SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token")


CONDITIONS: tuple[Literal["clear", "cloudy", "rain", "storm", "wind"], ...] = (
    "clear",
    "cloudy",
    "rain",
    "storm",
    "wind",
)


class WeatherResponse(BaseModel):
    condition: str
    temperature_c: float
    precip_mm: float
    wind_kph: float
    as_of: str


class ChaosProfileIn(BaseModel):
    mode: str
    flavor: str = "mixed"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class ChaosStatusOut(BaseModel):
    profile: dict
    events: list[dict]
    failure_streak: int
    circuit_open_until: float


def _pick_condition(lat: float, lon: float) -> str:
    seed = math.sin(lat * 3.1415) + math.cos(lon * 0.017) + math.sin(time.time() / 600.0)
    idx = int(abs(seed) * 1000) % len(CONDITIONS)
    return CONDITIONS[idx]


def _temperature(lat: float) -> float:
    base = 31.0 - abs(lat - 1.35) * 4.0
    seasonal = math.sin(time.time() / 3600.0) * 1.5
    return base + seasonal


def _precip(condition: str) -> float:
    return {
        "clear": 0.0,
        "cloudy": 0.2,
        "rain": 5.0,
        "storm": 12.0,
        "wind": 0.5,
    }.get(condition, 0.0)


def _wind(condition: str) -> float:
    return {
        "clear": 8.0,
        "cloudy": 10.0,
        "rain": 12.5,
        "storm": 22.0,
        "wind": 28.0,
    }.get(condition, 10.0)


@app.get("/api/v1/weather/current", response_model=WeatherResponse)
def weather_current(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
) -> WeatherResponse:
    condition = _pick_condition(lat, lon)
    return WeatherResponse(
        condition=condition,
        temperature_c=round(_temperature(lat), 1),
        precip_mm=round(_precip(condition), 2),
        wind_kph=round(_wind(condition), 1),
        as_of=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


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
