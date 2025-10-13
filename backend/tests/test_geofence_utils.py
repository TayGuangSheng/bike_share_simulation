from app.geofence import classify_parking_position, nearest_zone_centroid
from app.utils import calories_kcal, haversine_m, polyline_distance_m


def test_geofence_classification_and_centroid() -> None:
    zones = [
        {
            "kind": "parking",
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.0000, 1.0000],
                        [103.0000, 1.0010],
                        [103.0010, 1.0010],
                        [103.0010, 1.0000],
                        [103.0000, 1.0000],
                    ]
                ],
            },
        },
        {
            "kind": "no_park",
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [103.0020, 1.0020],
                        [103.0020, 1.0025],
                        [103.0025, 1.0025],
                        [103.0025, 1.0020],
                        [103.0020, 1.0020],
                    ]
                ],
            },
        },
    ]

    assert classify_parking_position(1.0005, 103.0005, zones, parking_buffer_m=5.0) == "parking"
    # just outside boundary but within buffer
    assert classify_parking_position(1.00102, 103.0005, zones, parking_buffer_m=5.0) == "boundary"
    assert classify_parking_position(1.0030, 103.0005, zones, parking_buffer_m=5.0) == "outside"
    assert classify_parking_position(1.0022, 103.0022, zones, parking_buffer_m=5.0) == "no_park"

    centroid = nearest_zone_centroid(1.0022, 103.0022, zones, kind="parking")
    assert centroid is not None
    lat, lon = centroid
    assert 1.0000 < lat < 1.0010
    assert 103.0000 < lon < 103.0010


def test_utils_distance_and_calories() -> None:
    meters = haversine_m(1.0, 103.0, 1.0, 103.001)
    assert meters > 0

    path = [(1.0, 103.0), (1.0005, 103.0005), (1.0010, 103.0010)]
    poly_dist = polyline_distance_m(path)
    assert poly_dist > meters / 2

    calories = calories_kcal(meters=poly_dist, seconds=300, weight_kg=70.0)
    assert calories > 0

