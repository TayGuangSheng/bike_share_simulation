from fastapi.testclient import TestClient

from .helpers import auth_header, login_token


def test_route_variants(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)
    base_payload = {
        "from": {"lat": 1.2960, "lon": 103.8450},
        "to": {"lat": 1.2995, "lon": 103.8455},
        "graph": "toy",
    }
    shortest = client.post("/api/v1/routes", headers=headers, json={**base_payload, "variant": "shortest"})
    assert shortest.status_code == 200
    safest = client.post("/api/v1/routes", headers=headers, json={**base_payload, "variant": "safest"})
    assert safest.status_code == 200
    shortest_time = shortest.json()["est_time_s"]
    safest_time = safest.json()["est_time_s"]
    assert safest_time >= shortest_time


def test_analytics_queue_and_reliability(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)

    kpis = client.get("/api/v1/analytics/kpis", headers=headers)
    assert kpis.status_code == 200
    data = kpis.json()
    assert set(data.keys()) == {"rides_per_hour", "avg_fare_cents", "avg_length_m", "unlock_failures", "stockouts", "violations"}

    queue_multi = client.get("/api/v1/analytics/queue", headers=headers, params={"lambda": 1.0, "mu": 3.0, "m": 2})
    assert queue_multi.status_code == 200

    queue_single = client.get("/api/v1/analytics/queue", headers=headers, params={"lambda": 0.3, "mu": 1.2, "m": 1})
    assert queue_single.status_code == 200

    unstable = client.get("/api/v1/analytics/queue", headers=headers, params={"lambda": 10.0, "mu": 1.0, "m": 1})
    assert unstable.status_code == 400

    # Reliability lab
    config = client.post(
        "/api/v1/lab/config",
        headers=headers,
        json={"drop_prob": 0.0, "dup_prob": 0.5, "corrupt_prob": 0.0},
    )
    assert config.status_code == 200

    unreliable = client.post(
        "/api/v1/lab/unreliable",
        headers=headers,
        json={"seq": 1, "checksum": 123, "data": "hello"},
    )
    assert unreliable.status_code == 200
    assert "events" in unreliable.json()

    ack = client.post(
        "/api/v1/lab/ack",
        headers=headers,
        json={"seq": 1},
    )
    assert ack.status_code == 200
    assert ack.json()["ack"] is True
