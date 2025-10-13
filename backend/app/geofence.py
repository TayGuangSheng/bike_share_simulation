from __future__ import annotations

from typing import Iterable, Optional

from shapely.geometry import Point, shape
from shapely.ops import nearest_points


def _buffer_polygon(geojson: dict, buffer_m: float) -> object:
    geom = shape(geojson)
    if buffer_m <= 0:
        return geom
    deg = buffer_m / 111_000.0
    return geom.buffer(deg)


def is_inside_any_zone(
    point_lat: float,
    point_lon: float,
    zones: Iterable[dict],
    kind: str,
    buffer_m: float = 5.0,
) -> bool:
    pt = Point(point_lon, point_lat)  # GeoJSON order lon,lat
    for z in zones:
        if z["kind"] != kind:
            continue
        poly = _buffer_polygon(z["polygon_geojson"], buffer_m)
        if poly.contains(pt) or poly.touches(pt):
            return True
    return False


def nearest_zone_centroid(
    point_lat: float,
    point_lon: float,
    zones: Iterable[dict],
    kind: str,
) -> Optional[tuple[float, float]]:
    pt = Point(point_lon, point_lat)
    best: tuple[float, float] | None = None
    min_dist = float("inf")
    for z in zones:
        if z["kind"] != kind:
            continue
        geom = shape(z["polygon_geojson"])
        centroid = geom.centroid
        dist = pt.distance(centroid)
        if dist < min_dist:
            min_dist = dist
            best = (centroid.y, centroid.x)
    return best


def classify_parking_position(
    point_lat: float,
    point_lon: float,
    zones: Iterable[dict],
    parking_buffer_m: float,
) -> str:
    """Return classification: 'parking', 'boundary', 'outside', 'no_park'."""
    pt = Point(point_lon, point_lat)
    is_parking = False
    is_boundary = False
    for z in zones:
        geom = shape(z["polygon_geojson"])
        buffered = _buffer_polygon(z["polygon_geojson"], parking_buffer_m)
        if z["kind"] == "no_park" and geom.contains(pt):
            return "no_park"
        if z["kind"] != "parking":
            continue
        if geom.contains(pt):
            is_parking = True
        elif buffered.contains(pt):
            is_boundary = True
    if is_parking:
        return "parking"
    if is_boundary:
        return "boundary"
    return "outside"
