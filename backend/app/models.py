from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, Enum, Text, UniqueConstraint, DateTime, Boolean
from sqlalchemy.types import JSON
from datetime import datetime
import enum
from typing import List

from .db import Base

class RoleEnum(enum.Enum):
    admin = "admin"
    user = "user"

class BikeLockState(enum.Enum):
    locked = "locked"
    unlocking = "unlocking"
    in_use = "in_use"
    locking = "locking"

class BikeStatus(enum.Enum):
    ok = "ok"
    maintenance = "maintenance"
    offline = "offline"

class RideState(enum.Enum):
    pending = "pending"
    active = "active"
    ended = "ended"
    billed = "billed"
    refunded = "refunded"

class PaymentStatus(enum.Enum):
    authorized = "authorized"
    captured = "captured"
    refunded = "refunded"

class MaintenanceStatus(enum.Enum):
    todo = "todo"
    doing = "doing"
    done = "done"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.admin)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rides: Mapped[List["Ride"]] = relationship(back_populates="user")

class Bike(Base):
    __tablename__ = "bikes"
    __table_args__ = (UniqueConstraint("qr_public_id", name="uq_bikes_qr"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qr_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_state: Mapped[BikeLockState] = mapped_column(Enum(BikeLockState), default=BikeLockState.locked, nullable=False)
    status: Mapped[BikeStatus] = mapped_column(Enum(BikeStatus), default=BikeStatus.ok, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    battery_pct: Mapped[int] = mapped_column(Integer, default=100)
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rides: Mapped[List["Ride"]] = relationship(back_populates="bike")
    maintenance_tasks: Mapped[List["MaintenanceTask"]] = relationship(back_populates="bike", cascade="all, delete-orphan")

class Ride(Base):
    __tablename__ = "rides"
    __table_args__ = (
        UniqueConstraint("unlock_token", name="uq_rides_unlock_token"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    bike_id: Mapped[int] = mapped_column(ForeignKey("bikes.id"), nullable=False)
    state: Mapped[RideState] = mapped_column(Enum(RideState), default=RideState.pending, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meters: Mapped[float] = mapped_column(Float, default=0.0)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    calories_kcal: Mapped[float] = mapped_column(Float, default=0.0)
    fare_cents: Mapped[int] = mapped_column(Integer, default=0)
    polyline_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pricing_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unlock_token: Mapped[str] = mapped_column(String(128), nullable=False)
    unlock_issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    smoothing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User | None"] = relationship(back_populates="rides")
    bike: Mapped["Bike"] = relationship(back_populates="rides")
    payment: Mapped["Payment | None"] = relationship(back_populates="ride", uselist=False)

class PricingPlan(Base):
    __tablename__ = "pricing_plans"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    base_cents: Mapped[int] = mapped_column(Integer, default=0)
    per_min_cents: Mapped[int] = mapped_column(Integer, default=0)
    per_km_cents: Mapped[int] = mapped_column(Integer, default=0)
    surge_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payments_idem_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ride_id: Mapped[int] = mapped_column(ForeignKey("rides.id"), nullable=False, unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.authorized, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    ride: Mapped["Ride"] = relationship(back_populates="payment")

class GeoZoneKind(enum.Enum):
    parking = "parking"
    no_park = "no_park"
    slow_zone = "slow_zone"

class GeoZone(Base):
    __tablename__ = "geozones"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    polygon_geojson: Mapped[dict] = mapped_column(JSON, nullable=False)
    kind: Mapped[GeoZoneKind] = mapped_column(Enum(GeoZoneKind), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bike_id: Mapped[int] = mapped_column(ForeignKey("bikes.id"), nullable=False, index=True)
    status: Mapped[MaintenanceStatus] = mapped_column(Enum(MaintenanceStatus), default=MaintenanceStatus.todo, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    bike: Mapped["Bike"] = relationship(back_populates="maintenance_tasks")

class EventLog(Base):
    __tablename__ = "event_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    component: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(255))
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (UniqueConstraint("from_node", "to_node", name="uq_graph_edges_pair"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_node: Mapped[str] = mapped_column(String(64), index=True)
    to_node: Mapped[str] = mapped_column(String(64), index=True)
    distance_m: Mapped[float] = mapped_column(Float)
    turn_penalty_s: Mapped[float] = mapped_column(Float, default=0.0)
    safe_score: Mapped[float] = mapped_column(Float, default=1.0)

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    endpoint: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(128))
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
