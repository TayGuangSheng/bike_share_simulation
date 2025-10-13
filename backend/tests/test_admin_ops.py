
from fastapi.testclient import TestClient

from .helpers import auth_header, login_token


def test_bikes_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/bikes")
    assert resp.status_code == 401


def test_patch_bike_requires_admin(client: TestClient) -> None:
    admin_token = login_token(client)
    admin_headers = auth_header(admin_token)
    bikes = client.get("/api/v1/bikes", headers=admin_headers).json()
    bike_id = bikes[0]["id"]

    patch = client.patch(
        f"/api/v1/bikes/{bike_id}",
        headers=admin_headers,
        json={"status": "maintenance", "battery_pct": 55},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "maintenance"

    invalid = client.patch(
        f"/api/v1/bikes/{bike_id}",
        headers=admin_headers,
        json={"status": "invalid"},
    )
    assert invalid.status_code == 400

    user_token = login_token(client, email="user@demo", password="user123")
    user_headers = auth_header(user_token)
    forbidden = client.patch(
        f"/api/v1/bikes/{bike_id}",
        headers=user_headers,
        json={"battery_pct": 90},
    )
    assert forbidden.status_code == 403


def test_payment_authorize_amount_validation(client: TestClient) -> None:
    token = login_token(client)
    headers = auth_header(token)
    bike = client.get("/api/v1/bikes", headers=headers).json()[0]

    unlock_headers = {**headers, "Idempotency-Key": "auth-ride"}
    unlock = client.post("/api/v1/unlock", headers=unlock_headers, json={"qr_public_id": bike["qr_public_id"]})
    assert unlock.status_code == 200
    ride_id = unlock.json()["ride"]["id"]

    lock_headers = {**headers, "Idempotency-Key": "auth-lock"}
    lock = client.post(
        "/api/v1/lock",
        headers=lock_headers,
        json={"ride_id": ride_id, "lat": 1.2972, "lon": 103.8462},
    )
    assert lock.status_code == 200
    fare = lock.json()["ride"]["metrics"]["fare_cents"]

    wrong_amount = client.post(
        "/api/v1/payments/authorize",
        headers={**headers, "Idempotency-Key": "auth-wrong"},
        json={"ride_id": ride_id, "amount_cents": fare + 100},
    )
    assert wrong_amount.status_code == 400
