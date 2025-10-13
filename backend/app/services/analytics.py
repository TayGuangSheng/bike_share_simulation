from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Ride, RideState


def compute_kpis(db: Session) -> dict:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    rides_last_hour = (
        db.query(func.count(Ride.id))
        .filter(Ride.started_at >= one_hour_ago, Ride.state.in_([RideState.active, RideState.ended, RideState.billed]))
        .scalar()
    )

    avg_fare = db.query(func.avg(Ride.fare_cents)).filter(Ride.fare_cents > 0).scalar() or 0.0
    avg_length = db.query(func.avg(Ride.meters)).filter(Ride.meters > 0).scalar() or 0.0

    unlock_failures = (
        db.query(func.count(Ride.id))
        .filter(Ride.state == RideState.pending)
        .scalar()
    )

    return {
        "rides_per_hour": float(rides_last_hour or 0) / 1.0,
        "avg_fare_cents": float(avg_fare),
        "avg_length_m": float(avg_length),
        "unlock_failures": int(unlock_failures or 0),
        "stockouts": 0,
        "violations": 0,
    }


def queue_metrics(lam: float, mu: float, m: int) -> Tuple[float, float, float, float, float]:
    rho = lam / (m * mu)
    if rho >= 1.0:
        raise ValueError("System is unstable (rho >= 1)")

    if m == 1:
        wq = lam / (mu * (mu - lam))
        w = wq + 1 / mu
        lq = lam * wq
        l = lam * w
        return rho, wq, w, lq, l

    sum_terms = sum((lam / mu) ** n / math.factorial(n) for n in range(m))
    m_term = ((lam / mu) ** m) / (math.factorial(m) * (1 - rho))
    p0 = 1 / (sum_terms + m_term)

    lq = (
        p0
        * ((lam / mu) ** m)
        * rho
        / (math.factorial(m) * (1 - rho) ** 2)
    )
    wq = lq / lam
    w = wq + 1 / mu
    l = lam * w
    return rho, wq, w, lq, l
