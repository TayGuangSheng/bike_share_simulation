from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...api import deps
from ...db import get_db
from ...models import Bike, BikeStatus
from ...schemas import BikeOut, BikePatch

router = APIRouter(prefix="/bikes", tags=["bikes"])


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


@router.get("", response_model=list[BikeOut])
def list_bikes(
    *,
    db: Session = Depends(get_db),
    _user=Depends(deps.get_current_user),
    near_lat: float | None = Query(default=None, alias="near_lat"),
    near_lon: float | None = Query(default=None, alias="near_lon"),
    radius_m: float | None = Query(default=None, gt=0.0),
) -> list[BikeOut]:
    query = db.query(Bike)
    bikes = query.all()
    # TODO: implement distance filtering; MVP returns all bikes.
    return [_serialize_bike(b) for b in bikes]


@router.get("/{bike_id}", response_model=BikeOut)
def get_bike(
    *,
    bike_id: int,
    db: Session = Depends(get_db),
    _user=Depends(deps.get_current_user),
) -> BikeOut:
    bike = db.get(Bike, bike_id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")
    return _serialize_bike(bike)


@router.patch("/{bike_id}", response_model=BikeOut)
def patch_bike(
    *,
    bike_id: int,
    payload: BikePatch,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
) -> BikeOut:
    bike = db.get(Bike, bike_id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    if payload.lat is not None:
        bike.lat = payload.lat
    if payload.lon is not None:
        bike.lon = payload.lon
    if payload.status is not None:
        try:
            bike.status = BikeStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bike status")
    if payload.battery_pct is not None:
        bike.battery_pct = payload.battery_pct

    db.add(bike)
    db.commit()
    db.refresh(bike)
    return _serialize_bike(bike)

