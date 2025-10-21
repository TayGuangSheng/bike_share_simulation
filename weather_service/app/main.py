from __future__ import annotations

import math
import time
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Weather Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
