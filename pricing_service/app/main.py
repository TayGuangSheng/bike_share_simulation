from __future__ import annotations

import itertools
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib import error, request

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Pricing and Payment Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


LOGGER = logging.getLogger("pricing_service")


SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token")
MAIN_BASE_URL = os.getenv("MAIN_BASE_URL", "http://localhost:8000")
WEATHER_BASE_URL = os.getenv("WEATHER_BASE_URL", "http://localhost:8102")


class DynamicPricingConfigOut(BaseModel):
    weather: str = "clear"
    base_multiplier: float = 1.0
    demand_slope: float = 0.02
    demand_threshold: int = 10
    min_multiplier: float = 0.7
    max_multiplier: float = 2.0
    last_updated_at: Optional[str] = None


class DynamicPricingUpdate(BaseModel):
    weather: Optional[str] = None
    base_multiplier: Optional[float] = Field(None, ge=0.1)
    demand_slope: Optional[float] = Field(None, ge=0.0)
    demand_threshold: Optional[int] = Field(None, ge=0)
    min_multiplier: Optional[float] = Field(None, ge=0.1)
    max_multiplier: Optional[float] = Field(None, ge=0.1)


class PricingCurrentOut(BaseModel):
    multiplier: float
    weather: str
    active_rides: int
    demand_factor: float
    weather_factor: float


class QuoteOut(BaseModel):
    bike_id: Optional[int] = None
    base_cents: int
    per_min_cents: int
    per_km_cents: int
    surge_multiplier: float
    weather: str
    demand_factor: float


class RunningFareOut(BaseModel):
    ride_id: int
    seconds: int
    meters: float
    fare_cents: int
    multiplier: float
    pricing_version: int


class PaymentChargeRequest(BaseModel):
    ride_id: int
    amount_cents: Optional[int] = Field(default=None, ge=0)
    meters: Optional[float] = Field(default=None, ge=0)
    seconds: Optional[int] = Field(default=None, ge=0)
    bike_id: Optional[int] = None
    bike_qr: Optional[str] = None
    user_email: Optional[str] = None
    ride_started_at: Optional[str] = None
    ride_ended_at: Optional[str] = None


class PaymentRefundRequest(BaseModel):
    payment_id: int
    reason: Optional[str] = None


class PaymentRecordOut(BaseModel):
    payment_id: int
    ride_id: int
    amount_cents: int
    status: str
    bike_id: Optional[int] = None
    bike_qr: Optional[str] = None
    user_email: Optional[str] = None
    ride_started_at: Optional[str] = None
    ride_ended_at: Optional[str] = None
    meters: Optional[float] = None
    seconds: Optional[int] = None
    captured_at: Optional[str] = None
    refunded_at: Optional[str] = None
    refund_reason: Optional[str] = None


class PaymentSummary(BaseModel):
    captured_cents: int
    captured_count: int


@dataclass
class PaymentRecord:
    payment_id: int
    ride_id: int
    amount_cents: int
    status: str
    created_at: float
    captured_at: Optional[float]
    refunded_at: Optional[float]
    refund_reason: Optional[str]
    bike_id: Optional[int] = None
    bike_qr: Optional[str] = None
    user_email: Optional[str] = None
    ride_started_at: Optional[str] = None
    ride_ended_at: Optional[str] = None
    meters: Optional[float] = None
    seconds: Optional[int] = None


CONFIG = DynamicPricingConfigOut()
PRICING_VERSION_COUNTER = itertools.count(1)
CURRENT_PRICING_VERSION = 1
BASE_CENTS = 100
PER_MIN_CENTS = 20
PER_KM_CENTS = 50
ACTIVE_RIDES: Dict[int, float] = {}
LAST_RUNNING_FARE: Dict[int, int] = {}

PAYMENT_COUNTER = itertools.count(1)
PAYMENTS_BY_ID: Dict[int, PaymentRecord] = {}
PAYMENTS_BY_RIDE: Dict[int, int] = {}
IDEMPOTENCY_CACHE: Dict[str, dict] = {}


def _now_ts() -> float:
    return time.time()


def _isoformat(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _fetch_weather(lat: Optional[float], lon: Optional[float]) -> dict:
    query_lat = lat if lat is not None else 1.3521
    query_lon = lon if lon is not None else 103.8198
    url = f"{WEATHER_BASE_URL}/api/v1/weather/current?lat={query_lat}&lon={query_lon}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=2.5) as resp:
            payload = resp.read()
            return json.loads(payload.decode("utf-8"))
    except error.URLError as exc:
        LOGGER.warning("weather lookup failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("unexpected error fetching weather")
    return {
        "condition": CONFIG.weather,
        "temperature_c": 30.0,
        "precip_mm": 0.0,
        "wind_kph": 5.0,
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _compute_weather_factor(condition: str) -> float:
    mapping = {
        "clear": 1.0,
        "cloudy": 1.0,
        "rain": 1.1,
        "storm": 1.3,
        "wind": 1.05,
        "snow": 1.25,
    }
    normalized = condition.lower() if condition else "clear"
    return mapping.get(normalized, 1.0)


def _compute_multiplier(weather_condition: str, active_rides: int) -> tuple[float, float, float]:
    weather_factor = _compute_weather_factor(weather_condition)
    demand_gap = max(active_rides - CONFIG.demand_threshold, 0)
    demand_factor = 1.0 + demand_gap * CONFIG.demand_slope
    raw_multiplier = CONFIG.base_multiplier * weather_factor * demand_factor
    clamped = max(CONFIG.min_multiplier, min(CONFIG.max_multiplier, raw_multiplier))
    return clamped, demand_factor, weather_factor


def _estimate_from_metrics(meters: Optional[float], seconds: Optional[int], multiplier: float) -> int:
    if meters is None or seconds is None:
        return 0
    minutes = seconds / 60.0
    km = meters / 1000.0
    raw = BASE_CENTS + PER_MIN_CENTS * minutes + PER_KM_CENTS * km
    fare = raw * multiplier
    return max(0, int(round(fare)))


def _notify_main_payment(record: PaymentRecord) -> None:
    url = f"{MAIN_BASE_URL}/api/v1/internal/payment/notify"
    payload = json.dumps(
        {
            "ride_id": record.ride_id,
            "payment_id": record.payment_id,
            "status": record.status,
            "amount_cents": record.amount_cents,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Service-Token": SERVICE_TOKEN,
    }
    req = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=3) as resp:
            resp.read()
    except Exception as exc:  # pragma: no cover - best effort notification
        LOGGER.warning("failed to notify main service about payment %s: %s", record.payment_id, exc)


def _record_payment(record: PaymentRecord) -> None:
    PAYMENTS_BY_ID[record.payment_id] = record
    PAYMENTS_BY_RIDE[record.ride_id] = record.payment_id


def _payment_to_out(record: PaymentRecord) -> PaymentRecordOut:
    return PaymentRecordOut(
        payment_id=record.payment_id,
        ride_id=record.ride_id,
        amount_cents=record.amount_cents,
        status=record.status,
        bike_id=record.bike_id,
        bike_qr=record.bike_qr,
        user_email=record.user_email,
        ride_started_at=record.ride_started_at,
        ride_ended_at=record.ride_ended_at,
        meters=record.meters,
        seconds=record.seconds,
        captured_at=_isoformat(record.captured_at),
        refunded_at=_isoformat(record.refunded_at),
        refund_reason=record.refund_reason,
    )


def _resolved_weather_condition() -> str:
    # Treat admin-configured weather as the canonical condition for pricing.
    return (CONFIG.weather or "clear").lower()


@app.get("/api/v1/pricing/config", response_model=DynamicPricingConfigOut)
def get_pricing_config() -> DynamicPricingConfigOut:
    return CONFIG


@app.put("/api/v1/pricing/config", response_model=DynamicPricingConfigOut)
def update_pricing_config(payload: DynamicPricingUpdate) -> DynamicPricingConfigOut:
    global CONFIG
    update_data = payload.model_dump(exclude_unset=True)
    if "weather" in update_data and isinstance(update_data["weather"], str):
        update_data["weather"] = update_data["weather"].lower()
    CONFIG = CONFIG.model_copy(update=update_data | {"last_updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return CONFIG


@app.get("/api/v1/pricing/current", response_model=PricingCurrentOut)
def current_pricing() -> PricingCurrentOut:
    active_rides = len(ACTIVE_RIDES)
    condition = _resolved_weather_condition()
    multiplier, demand_factor, weather_factor = _compute_multiplier(condition, active_rides)
    return PricingCurrentOut(
        multiplier=multiplier,
        weather=condition,
        active_rides=active_rides,
        demand_factor=demand_factor,
        weather_factor=weather_factor,
    )


@app.get("/api/v1/price/quote", response_model=QuoteOut)
def price_quote(
    bike_id: Optional[int] = Query(default=None),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
) -> QuoteOut:
    _fetch_weather(lat, lon)  # still call to exercise dependency (result not used for now)
    condition = _resolved_weather_condition()
    multiplier, demand_factor, weather_factor = _compute_multiplier(condition, len(ACTIVE_RIDES))
    return QuoteOut(
        bike_id=bike_id,
        base_cents=BASE_CENTS,
        per_min_cents=PER_MIN_CENTS,
        per_km_cents=PER_KM_CENTS,
        surge_multiplier=multiplier,
        weather=condition,
        demand_factor=demand_factor * weather_factor,
    )


@app.get("/api/v1/price/ride/{ride_id}/current", response_model=RunningFareOut)
def running_fare(
    ride_id: int,
    meters: Optional[float] = Query(default=None, ge=0),
    seconds: Optional[int] = Query(default=None, ge=0),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
) -> RunningFareOut:
    _fetch_weather(lat, lon)
    ACTIVE_RIDES[ride_id] = _now_ts()
    condition = _resolved_weather_condition()
    multiplier, demand_factor, weather_factor = _compute_multiplier(condition, len(ACTIVE_RIDES))
    fare_cents = _estimate_from_metrics(meters, seconds, multiplier)
    previous = LAST_RUNNING_FARE.get(ride_id, 0)
    fare_cents = max(fare_cents, previous)
    LAST_RUNNING_FARE[ride_id] = fare_cents
    pricing_version = next(PRICING_VERSION_COUNTER)
    global CURRENT_PRICING_VERSION
    CURRENT_PRICING_VERSION = pricing_version
    return RunningFareOut(
        ride_id=ride_id,
        seconds=int(seconds or 0),
        meters=float(meters or 0.0),
        fare_cents=fare_cents,
        multiplier=multiplier,
        pricing_version=pricing_version,
    )


@app.post("/api/v1/payments/charge", response_model=PaymentRecordOut, status_code=status.HTTP_201_CREATED)
def charge_payment(
    payload: PaymentChargeRequest,
    idempotency_key: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
) -> PaymentRecordOut:
    if idempotency_key:
        cached = IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            return PaymentRecordOut(**cached)

    amount_cents = payload.amount_cents
    if amount_cents is None:
        weather_data = _fetch_weather(None, None)
        multiplier, _, _ = _compute_multiplier(weather_data.get("condition", CONFIG.weather), len(ACTIVE_RIDES))
        estimate = _estimate_from_metrics(payload.meters, payload.seconds, multiplier)
        if estimate <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount_cents required when metrics missing")
        amount_cents = estimate

    payment_id = next(PAYMENT_COUNTER)
    record = PaymentRecord(
        payment_id=payment_id,
        ride_id=payload.ride_id,
        amount_cents=amount_cents,
        status="captured",
        created_at=_now_ts(),
        captured_at=_now_ts(),
        refunded_at=None,
        refund_reason=None,
        bike_id=payload.bike_id,
        bike_qr=payload.bike_qr,
        user_email=payload.user_email,
        ride_started_at=payload.ride_started_at,
        ride_ended_at=payload.ride_ended_at,
        meters=payload.meters,
        seconds=payload.seconds,
    )
    _record_payment(record)
    ACTIVE_RIDES.pop(payload.ride_id, None)
    LAST_RUNNING_FARE.pop(payload.ride_id, None)
    _notify_main_payment(record)
    response = _payment_to_out(record).model_dump()
    if idempotency_key:
        IDEMPOTENCY_CACHE[idempotency_key] = response
    return PaymentRecordOut(**response)


@app.post("/api/v1/payments/refund", response_model=PaymentRecordOut)
def refund_payment(payload: PaymentRefundRequest) -> PaymentRecordOut:
    record = PAYMENTS_BY_ID.get(payload.payment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    record.status = "refunded"
    record.refunded_at = _now_ts()
    record.refund_reason = payload.reason
    _notify_main_payment(record)
    return _payment_to_out(record)


@app.get("/api/v1/payments/summary", response_model=PaymentSummary)
def payment_summary() -> PaymentSummary:
    captured = [record for record in PAYMENTS_BY_ID.values() if record.status == "captured"]
    total_cents = sum(record.amount_cents for record in captured)
    return PaymentSummary(captured_cents=total_cents, captured_count=len(captured))


@app.get("/api/v1/payments/records")
def payment_records() -> dict:
    records = sorted(PAYMENTS_BY_ID.values(), key=lambda r: r.created_at, reverse=True)
    return {"records": [_payment_to_out(record).model_dump() for record in records]}


@app.get("/api/v1/payments/{payment_id}", response_model=PaymentRecordOut)
def payment_by_id(payment_id: int) -> PaymentRecordOut:
    record = PAYMENTS_BY_ID.get(payment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return _payment_to_out(record)


@app.on_event("startup")
def startup_cleanup_timer() -> None:
    def _cleanup_expired() -> None:
        now = _now_ts()
        to_remove = [ride_id for ride_id, ts in ACTIVE_RIDES.items() if now - ts > 600]
        for ride_id in to_remove:
            ACTIVE_RIDES.pop(ride_id, None)

    # Schedule lazy cleanup via background thread if running under uvicorn with reload disabled.
    try:
        import threading

        def _loop() -> None:
            while True:
                time.sleep(120)
                _cleanup_expired()

        threading.Thread(target=_loop, daemon=True).start()
    except Exception:  # pragma: no cover - background thread optional
        pass
