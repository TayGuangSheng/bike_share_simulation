from __future__ import annotations

from fastapi.testclient import TestClient

from .helpers import auth_header, login_token


def test_unlock_lock_and_payments_flow(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)

    bikes_resp = client.get("/api/v1/bikes", headers=headers)
    assert bikes_resp.status_code == 200
    bike = bikes_resp.json()[0]

    unlock_headers = {**headers, "Idempotency-Key": "ride-001"}
    unlock = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": bike["qr_public_id"]})
    assert unlock.status_code == 200
    unlock_data = unlock.json()
    ride_id = unlock_data["ride"]["id"]

    # Idempotent replay returns exact same response
    replay = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": bike["qr_public_id"]})
    assert replay.status_code == 200
    assert replay.json() == unlock_data

    # Telemetry samples along small path
    telemetry_headers = headers
    points = [
        {"lat": bike["lat"] + 0.0003, "lon": bike["lon"] + 0.0003, "speed_mps": 3.5, "ts": 100.0},
        {"lat": bike["lat"] + 0.0006, "lon": bike["lon"] + 0.0006, "speed_mps": 4.0, "ts": 104.0},
        {"lat": bike["lat"] + 0.0009, "lon": bike["lon"] + 0.0009, "speed_mps": 4.2, "ts": 108.0},
    ]
    for point in points:
        tele = client.post(f"/api/v1/rides/{ride_id}/telemetry", headers=telemetry_headers, json=point)
        assert tele.status_code == 200

    lock_headers = {**headers, "Idempotency-Key": "lock-001"}
    lock_resp = client.post(
        "/api/v1/lock",
        headers=lock_headers,
        json={"ride_id": ride_id, "lat": 1.2970, "lon": 103.8460},
    )
    assert lock_resp.status_code == 200, lock_resp.text
    lock_data = lock_resp.json()
    assert lock_data["parking_status"] in {"parking", "boundary"}
    fare = lock_data["ride"]["metrics"]["fare_cents"]

    lock_replay = client.post(
        "/api/v1/lock",
        headers=lock_headers,
        json={"ride_id": ride_id, "lat": 1.2970, "lon": 103.8460},
    )
    assert lock_replay.status_code == 200
    assert lock_replay.json() == lock_data

    # Payments flow
    pay_headers = {**headers, "Idempotency-Key": "pay-auth-001"}
    auth_resp = client.post(
        "/api/v1/payments/authorize",
        headers=pay_headers,
        json={"ride_id": ride_id, "amount_cents": fare},
    )
    assert auth_resp.status_code == 200, auth_resp.text
    payment = auth_resp.json()
    payment_id = payment["id"]

    capture_headers = {**headers, "Idempotency-Key": "pay-capture-001"}
    capture = client.post(
        "/api/v1/payments/capture",
        headers=capture_headers,
        json={"payment_id": payment_id},
    )
    assert capture.status_code == 200
    assert capture.json()["status"] == "captured"

    # Replay capture idempotently
    capture_again = client.post(
        "/api/v1/payments/capture",
        headers=capture_headers,
        json={"payment_id": payment_id},
    )
    assert capture_again.status_code == 200

    refund_headers = {**headers, "Idempotency-Key": "pay-refund-001"}
    refund = client.post(
        "/api/v1/payments/refund",
        headers=refund_headers,
        json={"payment_id": payment_id},
    )
    assert refund.status_code == 200
    assert refund.json()["status"] == "refunded"



def test_user_can_request_refund(client: TestClient) -> None:
    user_token = login_token(client, email="user@demo", password="user123")
    user_headers = auth_header(user_token)

    bike = client.get("/api/v1/bikes", headers=user_headers).json()[0]
    unlock_headers = {**user_headers, "Idempotency-Key": "user-refund-unlock"}
    unlock = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": bike["qr_public_id"]})
    assert unlock.status_code == 200, unlock.text
    ride_id = unlock.json()["ride"]["id"]

    tele_point = {"lat": bike["lat"] + 0.0003, "lon": bike["lon"] + 0.0003, "speed_mps": 3.2, "ts": 200.0}
    tele = client.post(f"/api/v1/rides/{ride_id}/telemetry", headers=user_headers, json=tele_point)
    assert tele.status_code == 200

    lock_headers = {**user_headers, "Idempotency-Key": "user-refund-lock"}
    lock = client.post(
        "/api/v1/lock",
        headers=lock_headers,
        json={"ride_id": ride_id, "lat": bike["lat"] + 0.0003, "lon": bike["lon"] + 0.0003},
    )
    assert lock.status_code == 200
    fare = lock.json()["ride"]["metrics"]["fare_cents"]

    admin_token = login_token(client)
    admin_headers = auth_header(admin_token)

    auth_headers = {**admin_headers, "Idempotency-Key": "user-refund-auth"}
    auth_resp = client.post(
        "/api/v1/payments/authorize",
        headers=auth_headers,
        json={"ride_id": ride_id, "amount_cents": fare},
    )
    assert auth_resp.status_code == 200, auth_resp.text
    payment_id = auth_resp.json()["id"]

    cap_headers = {**admin_headers, "Idempotency-Key": "user-refund-cap"}
    capture = client.post(
        "/api/v1/payments/capture",
        headers=cap_headers,
        json={"payment_id": payment_id},
    )
    assert capture.status_code == 200
    assert capture.json()["status"] == "captured"

    request_headers = {**user_headers, "Idempotency-Key": "user-refund-request"}
    request = client.post(
        f"/api/v1/payments/{payment_id}/refund-request",
        headers=request_headers,
        json={"reason": "Ride issue"},
    )
    assert request.status_code == 200, request.text
    assert request.json()["status"] == "refund_pending"

    request_again = client.post(
        f"/api/v1/payments/{payment_id}/refund-request",
        headers=request_headers,
        json={"reason": "Ride issue"},
    )
    assert request_again.status_code == 200

    refund_headers = {**admin_headers, "Idempotency-Key": "user-refund-complete"}
    final_refund = client.post(
        "/api/v1/payments/refund",
        headers=refund_headers,
        json={"payment_id": payment_id},
    )
    assert final_refund.status_code == 200
    assert final_refund.json()["status"] == "refunded"


def test_unlock_idempotency_conflict(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)
    bikes = client.get("/api/v1/bikes", headers=headers).json()
    first_bike = bikes[0]
    second_bike = bikes[1]

    unlock_headers = {**headers, "Idempotency-Key": "conflict-key"}
    resp1 = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": first_bike["qr_public_id"]})
    assert resp1.status_code == 200

    conflict = client.post(
        "/api/v1/unlock",
        headers=unlock_headers,
        json={"qr_public_id": second_bike["qr_public_id"]},
    )
    assert conflict.status_code == 409


def test_lock_no_park_zone_requires_relocation(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)
    bike = client.get("/api/v1/bikes", headers=headers).json()[0]
    unlock_headers = {**headers, "Idempotency-Key": "ride-no-park"}
    unlock = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": bike["qr_public_id"]})
    assert unlock.status_code == 200
    ride_id = unlock.json()["ride"]["id"]

    # Move bike to Merlion no-park zone
    tele_point = {"lat": 1.2865, "lon": 103.8525, "speed_mps": 3.0, "ts": 200.0}
    tele = client.post(f"/api/v1/rides/{ride_id}/telemetry", headers=headers, json=tele_point)
    assert tele.status_code == 200

    lock_headers = {**headers, "Idempotency-Key": "lock-no-park"}
    failure = client.post(
        "/api/v1/lock",
        headers=lock_headers,
        json={"ride_id": ride_id, "lat": 1.2865, "lon": 103.8525},
    )
    assert failure.status_code == 409
    detail = failure.json()["detail"]
    assert detail["nearest_parking_route"] is not None

    # Lock successfully inside parking zone
    success_headers = {**headers, "Idempotency-Key": "lock-success"}
    success = client.post(
        "/api/v1/lock",
        headers=success_headers,
        json={"ride_id": ride_id, "lat": 1.2975, "lon": 103.8465},
    )
    assert success.status_code == 200


def test_concurrent_unlock_same_bike_rejected(client: TestClient) -> None:
    token = login_token(client, email="user@demo", password="user123")
    headers = auth_header(token)
    bike = client.get("/api/v1/bikes", headers=headers).json()[0]

    first = client.post(
        "/api/v1/unlock",
        headers={**headers, "Idempotency-Key": "unlock-1"},
        json={"qr_public_id": bike["qr_public_id"]},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/unlock",
        headers={**headers, "Idempotency-Key": "unlock-2"},
        json={"qr_public_id": bike["qr_public_id"]},
    )
    assert second.status_code == 409
