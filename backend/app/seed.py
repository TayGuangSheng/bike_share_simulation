from __future__ import annotations

import json
from pathlib import Path
from random import randint, random, choice

from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine
from .models import (
    Bike,
    BikeLockState,
    BikeStatus,
    GeoZone,
    GeoZoneKind,
    GraphEdge,
    MaintenanceStatus,
    MaintenanceTask,
    PricingPlan,
    RoleEnum,
    User,
)
from .security import hash_password


def _seed_users(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    users = [
        User(
            email="admin@demo",
            password_hash=hash_password("admin123"),
            role=RoleEnum.admin,
            weight_kg=70.0,
        ),
        User(
            email="user@demo",
            password_hash=hash_password("user123"),
            role=RoleEnum.user,
            weight_kg=65.0,
        ),
    ]
    db.add_all(users)


def _seed_pricing_plans(db: Session) -> None:
    if db.query(PricingPlan).count() > 0:
        return
    flat_plan = PricingPlan(
        name="Flat",
        base_cents=100,
        per_min_cents=20,
        per_km_cents=60,
        surge_multiplier=1.0,
        version=1,
        is_active=True,
    )
    surge_plan = PricingPlan(
        name="Surge",
        base_cents=80,
        per_min_cents=30,
        per_km_cents=90,
        surge_multiplier=1.4,
        version=2,
        is_active=False,
    )
    db.add_all([flat_plan, surge_plan])


def _seed_bikes(db: Session) -> None:
    if db.query(Bike).count() >= 60:
        return
    bikes = []
    anchors = [
        (1.305, 103.831),  # Orchard
        (1.352, 103.943),  # Changi
        (1.280, 103.850),  # CBD / Marina
        (1.340, 103.697),  # Jurong
        (1.404, 103.902),  # Punggol
        (1.312, 103.763),  # Bukit Timah
        (1.296, 103.790),  # Botanic Gardens
        (1.367, 103.848),  # Bishan
        (1.318, 103.892),  # Geylang
        (1.443, 103.785),  # Woodlands
    ]
    def jitter(deg: float = 0.01) -> float:
        return (random() - 0.5) * deg

    for idx in range(60):
        base_lat, base_lon = choice(anchors)
        offset_lat = base_lat + jitter(0.015)
        offset_lon = base_lon + jitter(0.02)
        bikes.append(
            Bike(
                qr_public_id=f"SG-BIKE-{idx:03d}",
                lock_state=BikeLockState.locked,
                status=BikeStatus.ok,
                lat=round(offset_lat, 6),
                lon=round(offset_lon, 6),
                battery_pct=randint(40, 100),
            )
        )
    db.add_all(bikes)


def _seed_geozones(db: Session) -> None:
    if db.query(GeoZone).count() > 0:
        return
    zones = [
        GeoZone(
            name="Raffles Place Parking",
            kind=GeoZoneKind.parking,
            polygon_geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.845, 1.296],
                        [103.848, 1.296],
                        [103.848, 1.299],
                        [103.845, 1.299],
                        [103.845, 1.296],
                    ]
                ],
            },
        ),
        GeoZone(
            name="Marina Bay Parking",
            kind=GeoZoneKind.parking,
            polygon_geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.856, 1.286],
                        [103.859, 1.286],
                        [103.859, 1.289],
                        [103.856, 1.289],
                        [103.856, 1.286],
                    ]
                ],
            },
        ),
        GeoZone(
            name="Merlion No-Park",
            kind=GeoZoneKind.no_park,
            polygon_geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.852, 1.286],
                        [103.853, 1.286],
                        [103.853, 1.2875],
                        [103.852, 1.2875],
                        [103.852, 1.286],
                    ]
                ],
            },
        ),
        GeoZone(
            name="Boat Quay Slow Zone",
            kind=GeoZoneKind.slow_zone,
            polygon_geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.848, 1.287],
                        [103.851, 1.287],
                        [103.851, 1.290],
                        [103.848, 1.290],
                        [103.848, 1.287],
                    ]
                ],
            },
        ),
    ]
    db.add_all(zones)


def _seed_graph_edges(db: Session) -> None:
    if db.query(GraphEdge).count() > 0:
        return
    graphs_dir = Path(settings.graphs_dir)
    graph_path = graphs_dir / "civic.json"
    if graph_path.exists():
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        edges = []
        for edge in data.get("edges", []):
            edges.append(
                GraphEdge(
                    from_node=edge["from"],
                    to_node=edge["to"],
                    distance_m=edge["distance_m"],
                    turn_penalty_s=edge.get("turn_penalty_s", 0.0),
                    safe_score=edge.get("safe_score", 1.0),
                )
            )
        db.add_all(edges)


def _seed_maintenance(db: Session) -> None:
    if db.query(MaintenanceTask).count() > 0:
        return
    bike = db.query(Bike).first()
    if not bike:
        return
    task = MaintenanceTask(
        bike_id=bike.id,
        status=MaintenanceStatus.todo,
        note="Demo task: inspect brake cables",
    )
    db.add(task)


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_users(db)
        _seed_pricing_plans(db)
        _seed_bikes(db)
        _seed_geozones(db)
        _seed_graph_edges(db)
        _seed_maintenance(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
