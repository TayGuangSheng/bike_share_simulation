from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    id: int
    email: str
    role: str


class BikeOut(BaseModel):
    id: int
    qr_public_id: str
    lock_state: str
    status: str
    lat: float
    lon: float
    battery_pct: int
    last_reported_at: Optional[str] = None


class BikePatch(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    status: Optional[str] = None
    battery_pct: Optional[int] = Field(None, ge=0, le=100)


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class UnlockRequest(BaseModel):
    qr_public_id: str
    simulated_user_email: Optional[str] = None


class RideMetrics(BaseModel):
    meters: float
    seconds: int
    calories_kcal: float
    fare_cents: int
    pricing_version: Optional[int] = None


class RideOut(BaseModel):
    id: int
    state: str
    started_at: Optional[str]
    ended_at: Optional[str]
    bike_id: int
    unlock_token: str
    polyline_geojson: dict
    metrics: RideMetrics


class UnlockResponse(BaseModel):
    unlock_token: str
    ride: RideOut
    bike: BikeOut


class TelemetryPoint(BaseModel):
    lat: float
    lon: float
    speed_mps: float = Field(..., ge=0)
    ts: float = Field(..., description="epoch seconds")


class LockRequest(BaseModel):
    ride_id: int
    lat: float
    lon: float


class LockResponse(BaseModel):
    ok: bool
    parking_status: Literal["parking", "boundary", "outside", "cached"]
    ride: RideOut
    nearest_parking_route: Optional[dict] = None


class RouteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_location: Coordinate = Field(..., alias="from")
    to_location: Coordinate = Field(..., alias="to")
    variant: Literal["shortest", "safest"] = "shortest"
    graph: Optional[str] = None


class RouteResponse(BaseModel):
    polyline_geojson: dict
    total_distance_m: float
    est_time_s: float
    nodes: list[str]
    start_node: str
    end_node: str


class PricingPlanOut(BaseModel):
    id: int
    name: str
    base_cents: int
    per_min_cents: int
    per_km_cents: int
    surge_multiplier: float
    version: int
    is_active: bool


class PaymentAuthorizeRequest(BaseModel):
    ride_id: int
    amount_cents: int = Field(..., ge=0)


class PaymentCaptureRequest(BaseModel):
    payment_id: int


class PaymentRefundRequest(BaseModel):
    payment_id: int


class PaymentOut(BaseModel):
    id: int
    ride_id: int
    amount_cents: int
    status: str
    idempotency_key: str


class KpiResponse(BaseModel):
    rides_per_hour: float
    avg_fare_cents: float
    avg_length_m: float
    unlock_failures: int
    stockouts: int
    violations: int


class QueueingRequest(BaseModel):
    lam: float = Field(..., alias="lambda", gt=0)
    mu: float = Field(..., gt=0)
    m: int = Field(..., ge=1)


class QueueingMetrics(BaseModel):
    rho: float
    wq: float
    w: float
    lq: float
    l: float


class ReliabilityConfig(BaseModel):
    drop_prob: float = Field(..., ge=0.0, le=1.0)
    dup_prob: float = Field(..., ge=0.0, le=1.0)
    corrupt_prob: float = Field(..., ge=0.0, le=1.0)


class ReliabilityPayload(BaseModel):
    seq: int
    checksum: Optional[int] = None
    data: str


class AckRequest(BaseModel):
    seq: int


class AckResponse(BaseModel):
    ack: bool
    seq: int
