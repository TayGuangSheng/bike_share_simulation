from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..geofence import classify_parking_position, nearest_zone_centroid
from ..models import (
    Bike,
    BikeLockState,
    BikeStatus,
    GeoZone,
    PricingPlan,
    Ride,
    RideState,
    RoleEnum,
    User,
)
from ..security import hash_password
from ..services.eventlog import log_event
from ..services.idempotency import IdempotencyService, IdempotencyRecord, IdempotencyConflict
from ..services.routing import RoutingService
from ..utils import haversine_m, calories_kcal


@dataclass
class UnlockResult:
    bike: Optional[Bike]
    ride: Optional[Ride]
    pricing_plan: Optional[PricingPlan]
    idempotent_record: Optional[IdempotencyRecord]


@dataclass
class TelemetryResult:
    ride: Ride
    bike: Bike


@dataclass
class LockResult:
    ride: Optional[Ride]
    bike: Optional[Bike]
    parking_status: str
    nearest_parking_route: Optional[dict]
    idempotent_record: Optional[IdempotencyRecord]


class RideService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.routing = RoutingService(graph_name=settings.default_graph_name)

    def _get_active_pricing_plan(self) -> PricingPlan:
        plan = (
            self.db.query(PricingPlan)
            .filter(PricingPlan.is_active.is_(True))
            .order_by(PricingPlan.version.desc())
            .first()
        )
        if plan is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No active pricing plan")
        return plan

    def _ensure_no_active_ride(self, user: Optional[User], bike: Bike) -> None:
        active_states = (RideState.pending, RideState.active)
        bike_active = (
            self.db.query(Ride)
            .filter(Ride.bike_id == bike.id, Ride.state.in_(active_states))
            .with_for_update()
            .first()
        )
        if bike_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bike already has an active ride")
        if user:
            user_active = (
                self.db.query(Ride)
                .filter(Ride.user_id == user.id, Ride.state.in_(active_states))
                .with_for_update()
                .first()
            )
            if user_active:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has an active ride")

    def unlock_bike(
        self,
        *,
        user: Optional[User],
        qr_public_id: str,
        idempotency: IdempotencyService,
        simulated_user_email: Optional[str] = None,
    ) -> UnlockResult:
        try:
            cached = idempotency.ensure()
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if cached:
            return UnlockResult(
                bike=None,  # type: ignore[arg-type]
                ride=None,  # type: ignore[arg-type]
                pricing_plan=None,  # type: ignore[arg-type]
                idempotent_record=cached,
            )

        bike = (
            self.db.query(Bike)
            .filter(Bike.qr_public_id == qr_public_id)
            .with_for_update()
            .first()
        )
        if bike is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")
        if bike.status != BikeStatus.ok:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bike not available")
        if bike.lock_state not in (BikeLockState.locked, BikeLockState.unlocking):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bike already in ride")

        ride_user = user
        if simulated_user_email:
            ride_user = self._get_or_create_simulated_user(simulated_user_email)

        self._ensure_no_active_ride(ride_user, bike)

        pricing_plan = self._get_active_pricing_plan()

        ride = Ride(
            user_id=ride_user.id if ride_user else None,
            bike_id=bike.id,
            state=RideState.active,
            started_at=datetime.utcnow(),
            polyline_geojson={"type": "LineString", "coordinates": []},
            pricing_version=pricing_plan.version,
            unlock_token=secrets.token_urlsafe(18),
        )
        bike.lock_state = BikeLockState.in_use
        bike.last_reported_at = datetime.utcnow()

        self.db.add(ride)
        self.db.add(bike)
        self.db.flush()

        log_event(
            self.db,
            component="ride",
            level="info",
            message="Bike unlocked",
            payload={
                "ride_id": ride.id,
                "bike_id": bike.id,
                "user_id": ride.user_id,
                "triggered_by": user.id if user else None,
            },
        )

        return UnlockResult(
            bike=bike,
            ride=ride,
            pricing_plan=pricing_plan,
            idempotent_record=None,
        )

    def _append_polyline(self, ride: Ride, lat: float, lon: float) -> float:
        coords = ride.polyline_geojson.get("coordinates", []) if ride.polyline_geojson else []
        prev_lat = prev_lon = None
        if coords:
            last = coords[-1]
            prev_lon, prev_lat = last[0], last[1]
        coords.append([lon, lat])
        ride.polyline_geojson = {"type": "LineString", "coordinates": coords}

        if prev_lat is None or prev_lon is None:
            return 0.0
        return haversine_m(prev_lat, prev_lon, lat, lon)

    def record_telemetry(
        self,
        *,
        ride_id: int,
        lat: float,
        lon: float,
        speed_mps: float,
        ts_seconds: float,
    ) -> TelemetryResult:
        ride = (
            self.db.query(Ride)
            .filter(Ride.id == ride_id)
            .with_for_update()
            .first()
        )
        if ride is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
        if ride.state != RideState.active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride not active")

        bike = (
            self.db.query(Bike)
            .filter(Bike.id == ride.bike_id)
            .with_for_update()
            .first()
        )
        if bike is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

        delta_m = self._append_polyline(ride, lat, lon)
        ride.meters += delta_m

        timestamp = datetime.utcfromtimestamp(ts_seconds)
        if ride.last_telemetry_at:
            elapsed = (timestamp - ride.last_telemetry_at).total_seconds()
            elapsed = max(int(elapsed), settings.telemetry_min_interval_s)
        else:
            elapsed = settings.telemetry_min_interval_s
        ride.seconds += int(elapsed)
        ride.last_telemetry_at = timestamp

        user = ride.user
        weight = user.weight_kg if user else None
        ride.calories_kcal = calories_kcal(ride.meters, ride.seconds, weight_kg=weight)

        bike.lat = lat
        bike.lon = lon
        bike.last_reported_at = datetime.utcnow()

        self.db.add(ride)
        self.db.add(bike)
        self.db.flush()

        return TelemetryResult(ride=ride, bike=bike)

    def _compute_fare(self, ride: Ride, plan: PricingPlan) -> int:
        minutes = ride.seconds / 60.0
        km = ride.meters / 1000.0
        raw_fare = (
            plan.base_cents + plan.per_min_cents * minutes + plan.per_km_cents * km
        ) * plan.surge_multiplier
        if settings.pricing_rounding == "bankers":
            cents = int(round(raw_fare))
        else:
            cents = math.ceil(raw_fare)
        return max(cents, 0)

    def lock_bike(
        self,
        *,
        ride_id: int,
        lat: float,
        lon: float,
        idempotency: IdempotencyService,
    ) -> LockResult:
        try:
            cached = idempotency.ensure()
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if cached:
            return LockResult(
                ride=None,  # type: ignore[arg-type]
                bike=None,  # type: ignore[arg-type]
                parking_status="cached",
                nearest_parking_route=None,
                idempotent_record=cached,
            )

        ride = (
            self.db.query(Ride)
            .filter(Ride.id == ride_id)
            .with_for_update()
            .first()
        )
        if ride is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
        if ride.state != RideState.active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride not active")

        bike = (
            self.db.query(Bike)
            .filter(Bike.id == ride.bike_id)
            .with_for_update()
            .first()
        )
        if bike is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

        zones_payload = [
            {"kind": zone.kind.value, "polygon_geojson": zone.polygon_geojson}
            for zone in self._load_zones()
        ]
        status_label = classify_parking_position(lat, lon, zones_payload, settings.geofence_buffer_m)

        nearest_route = None
        if status_label in ("outside", "no_park"):
            centroid = nearest_zone_centroid(lat, lon, zones_payload, kind="parking")
            if centroid:
                route = self.routing.compute_route(
                    start_lat=lat,
                    start_lon=lon,
                    end_lat=centroid[0],
                    end_lon=centroid[1],
                    variant="shortest",
                )
                nearest_route = {
                    "polyline_geojson": route.polyline_geojson,
                    "distance_m": route.total_distance_m,
                    "est_time_s": route.est_time_s,
                }

        if status_label == "no_park":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Cannot lock in no-park zone",
                    "nearest_parking_route": nearest_route,
                },
            )

        plan = self._get_active_pricing_plan()
        if ride.pricing_version != plan.version:
            plan = (
                self.db.query(PricingPlan)
                .filter(PricingPlan.version == ride.pricing_version)
                .first()
            ) or plan

        ride.state = RideState.ended
        ride.ended_at = datetime.utcnow()
        ride.fare_cents = self._compute_fare(ride, plan)
        bike.lock_state = BikeLockState.locked
        bike.lat = lat
        bike.lon = lon
        bike.last_reported_at = datetime.utcnow()

        self.db.add(ride)
        self.db.add(bike)
        self.db.flush()

        log_event(
            self.db,
            component="ride",
            level="info",
            message="Bike locked",
            payload={"ride_id": ride.id, "bike_id": bike.id, "parking_status": status_label},
        )

        return LockResult(
            ride=ride,
            bike=bike,
            parking_status=status_label,
            nearest_parking_route=nearest_route,
            idempotent_record=None,
        )

    def _load_zones(self) -> Iterable[GeoZone]:
        return self.db.execute(select(GeoZone)).scalars().all()

    def _get_or_create_simulated_user(self, email: str) -> User:
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(12)),
            role=RoleEnum.user,
            weight_kg=70.0,
        )
        self.db.add(user)
        self.db.flush()
        return user
