from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...api import deps
from ...db import get_db
from ...schemas import DynamicPricingConfigOut, DynamicPricingUpdate, PricingCurrentOut
from ...services.pricing import PricingService

router = APIRouter(prefix="/pricing", tags=["pricing"])


def _serialize_config(service: PricingService) -> DynamicPricingConfigOut:
    cfg = service.get_config()
    snapshot = service.compute_snapshot(cfg)
    return DynamicPricingConfigOut(
        weather=cfg.weather,
        base_multiplier=cfg.base_multiplier,
        demand_slope=cfg.demand_slope,
        demand_threshold=cfg.demand_threshold,
        min_multiplier=cfg.min_multiplier,
        max_multiplier=cfg.max_multiplier,
        last_updated_at=cfg.updated_at.isoformat() if cfg.updated_at else None,
        current_multiplier=snapshot.multiplier,
    )


@router.get("/config", response_model=DynamicPricingConfigOut)
def get_pricing_config(
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
) -> DynamicPricingConfigOut:
    service = PricingService(db)
    return _serialize_config(service)


@router.put("/config", response_model=DynamicPricingConfigOut)
def update_pricing_config(
    payload: DynamicPricingUpdate,
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
) -> DynamicPricingConfigOut:
    service = PricingService(db)
    config = service.update_config(**payload.model_dump())
    db.add(config)
    db.commit()
    return _serialize_config(service)


@router.get("/current", response_model=PricingCurrentOut)
def current_pricing(
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
) -> PricingCurrentOut:
    service = PricingService(db)
    snapshot = service.compute_snapshot()
    return PricingCurrentOut(
        multiplier=snapshot.multiplier,
        weather=snapshot.weather,
        active_rides=snapshot.active_rides,
        demand_factor=snapshot.demand_factor,
        weather_factor=snapshot.weather_factor,
    )
