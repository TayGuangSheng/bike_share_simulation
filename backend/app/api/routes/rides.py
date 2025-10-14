from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...api import deps
from ...db import get_db
from ...models import Ride, Bike, RoleEnum
from ...schemas import (
    BikeOut,
    LockRequest,
    LockResponse,
    RideMetrics,
    RideOut,
    TelemetryPoint,
    UnlockRequest,
    UnlockResponse,
)
from ...services.idempotency import IdempotencyService
from ...services.rides import RideService


def _serialize_bike(bike: Bike) -> BikeOut:
    return BikeOut(
        id=bike.id,
        qr_public_id=bike.qr_public_id,
        lock_state=bike.lock_state.value,
        status=bike.status.value,
        lat=bike.lat,
        lon=bike.lon,
        battery_pct=bike.battery_pct,
        last_reported_at=bike.last_reported_at.isoformat() if bike.last_reported_at else None,
    )

router = APIRouter(tags=["rides"])


def _serialize_ride(ride: Ride) -> RideOut:
    metrics = RideMetrics(
        meters=ride.meters,
        seconds=ride.seconds,
        calories_kcal=ride.calories_kcal,
        fare_cents=ride.fare_cents,
        pricing_version=ride.pricing_version,
    )
    return RideOut(
        id=ride.id,
        state=ride.state.value,
        started_at=ride.started_at.isoformat() if ride.started_at else None,
        ended_at=ride.ended_at.isoformat() if ride.ended_at else None,
        bike_id=ride.bike_id,
        unlock_token=ride.unlock_token,
        polyline_geojson=ride.polyline_geojson or {"type": "LineString", "coordinates": []},
        metrics=metrics,
        dynamic_multiplier_start=ride.dynamic_multiplier_start,
        dynamic_multiplier_end=ride.dynamic_multiplier_end,
    )


@router.post("/unlock", response_model=UnlockResponse)
def unlock_bike(
    payload: UnlockRequest,
    *,
    db: Session = Depends(get_db),
    user=Depends(deps.get_current_user),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    service = RideService(db)
    idem = IdempotencyService(db, endpoint="/unlock", key=idempotency_key, request_payload=payload.model_dump())
    if payload.simulated_user_email and user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can simulate other users")

    result = service.unlock_bike(
        user=user,
        qr_public_id=payload.qr_public_id,
        idempotency=idem,
        simulated_user_email=payload.simulated_user_email if user.role == RoleEnum.admin else None,
    )
    if result.idempotent_record:
        return JSONResponse(status_code=result.idempotent_record.response_status, content=result.idempotent_record.response_json)

    if not result.ride or not result.bike:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unlock failed")

    response_dict = {
        "unlock_token": result.ride.unlock_token,
        "ride": _serialize_ride(result.ride).model_dump(),
        "bike": _serialize_bike(result.bike).model_dump(),
    }
    idem.store_response(status.HTTP_200_OK, response_dict)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_dict)


@router.post("/rides/{ride_id}/telemetry")
def post_telemetry(
    ride_id: int,
    payload: TelemetryPoint,
    *,
    db: Session = Depends(get_db),
    _user=Depends(deps.get_current_user),
):
    service = RideService(db)
    result = service.record_telemetry(
        ride_id=ride_id,
        lat=payload.lat,
        lon=payload.lon,
        speed_mps=payload.speed_mps,
        ts_seconds=payload.ts,
    )
    db.commit()
    ride = result.ride
    return {
        "ok": True,
        "ride_id": ride.id,
        "meters": ride.meters,
        "seconds": ride.seconds,
        "calories_kcal": ride.calories_kcal,
    }


@router.post("/lock", response_model=LockResponse)
def lock_bike(
    payload: LockRequest,
    *,
    db: Session = Depends(get_db),
    _user=Depends(deps.get_current_user),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    service = RideService(db)
    idem = IdempotencyService(db, endpoint="/lock", key=idempotency_key, request_payload=payload.model_dump())
    result = service.lock_bike(ride_id=payload.ride_id, lat=payload.lat, lon=payload.lon, idempotency=idem)
    if result.idempotent_record:
        return JSONResponse(status_code=result.idempotent_record.response_status, content=result.idempotent_record.response_json)

    if not result.ride or not result.bike:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lock failed")

    response_dict = {
        "ok": True,
        "parking_status": result.parking_status,
        "ride": _serialize_ride(result.ride).model_dump(),
        "nearest_parking_route": result.nearest_parking_route,
    }
    idem.store_response(status.HTTP_200_OK, response_dict)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_dict)

