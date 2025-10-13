import math
from typing import Iterable

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def polyline_distance_m(points: Iterable[tuple[float, float]]) -> float:
    total = 0.0
    prev = None
    for p in points:
        if prev is not None:
            total += haversine_m(prev[0], prev[1], p[0], p[1])
        prev = p
    return total

def calories_kcal(meters: float, seconds: int, weight_kg: float | None = None, met: float = 8.0) -> float:
    # Simple MET model with fallback weight 70 kg
    hours = max(seconds, 1) / 3600.0
    w = weight_kg or 70.0
    return met * w * hours
