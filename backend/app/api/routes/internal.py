from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ...models import (
    Bike,
    BikeLockState,
    BikeStatus,
    MaintenanceStatus,
    MaintenanceTask,
    Ride,
    RideState,
)
from ...schemas import BatteryLowNotification, PaymentNotification


router = APIRouter(prefix="/internal", tags=["internal"])


def _require_service_token(token: str | None) -> None:
    expected = settings.service_token.get_secret_value()
    if expected and token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid service token")


@router.post("/payment/notify", status_code=status.HTTP_202_ACCEPTED)
def payment_notify(
    payload: PaymentNotification,
    *,
    service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
) -> dict:
    _require_service_token(service_token)

    ride: Ride | None = db.get(Ride, payload.ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ride not found")

    ride.fare_cents = payload.amount_cents
    if payload.status == "captured":
        ride.state = RideState.billed
        ride.ended_at = ride.ended_at or datetime.utcnow()
        bike = ride.bike
        if bike is not None:
            if bike.status != BikeStatus.maintenance:
                bike.status = BikeStatus.ok
            bike.lock_state = BikeLockState.locked
    elif payload.status == "refunded":
        ride.state = RideState.refunded
    else:
        ride.state = RideState.ended

    db.add(ride)
    db.commit()
    return {"ok": True}


@router.post("/battery/low-battery", status_code=status.HTTP_202_ACCEPTED)
def battery_low_battery(
    payload: BatteryLowNotification,
    *,
    service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
) -> dict:
    _require_service_token(service_token)

    bike: Bike | None = db.get(Bike, payload.bike_id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bike not found")

    bike.battery_pct = payload.battery_pct
    bike.status = BikeStatus.maintenance

    maintenance = MaintenanceTask(
        bike_id=bike.id,
        status=MaintenanceStatus.todo,
        note=f"Battery below {payload.threshold}% (reported {payload.battery_pct}%)",
    )
    db.add(maintenance)
    db.add(bike)
    db.commit()
    return {"ok": True}
