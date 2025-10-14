from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import DynamicPricingConfig, Ride, RideState
from ..services.eventlog import log_event


@dataclass
class DynamicPricingSnapshot:
    multiplier: float
    weather: str
    demand_factor: float
    weather_factor: float
    active_rides: int


class PricingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_config(self) -> DynamicPricingConfig:
        config = self.db.query(DynamicPricingConfig).order_by(DynamicPricingConfig.id.asc()).first()
        if config is None:
            config = DynamicPricingConfig()
            self.db.add(config)
            self.db.flush()
        return config

    def update_config(self, **fields: Optional[object]) -> DynamicPricingConfig:
        config = self.get_config()
        applied: dict[str, object] = {}
        for key, value in fields.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
                applied[key] = value
        self.db.add(config)
        self.db.flush()
        if applied:
            log_event(
                self.db,
                component="pricing",
                level="info",
                message="Dynamic pricing config updated",
                payload={"changes": applied},
            )
        return config

    def compute_snapshot(
        self,
        config: DynamicPricingConfig | None = None,
    ) -> DynamicPricingSnapshot:
        if config is None:
            config = self.get_config()
        active_rides = (
            self.db.query(func.count(Ride.id))
            .filter(Ride.state.in_([RideState.pending, RideState.active]))
            .scalar()
            or 0
        )
        demand_excess = max(0, active_rides - config.demand_threshold)
        demand_factor = 1.0 + config.demand_slope * demand_excess

        weather_map = {
            "clear": 1.0,
            "rain": 0.9,
            "storm": 0.8,
        }
        weather_factor = weather_map.get(config.weather, 1.0)

        multiplier = config.base_multiplier * weather_factor * demand_factor
        multiplier = max(config.min_multiplier, min(config.max_multiplier, multiplier))

        return DynamicPricingSnapshot(
            multiplier=multiplier,
            weather=config.weather,
            demand_factor=demand_factor,
            weather_factor=weather_factor,
            active_rides=int(active_rides),
        )
