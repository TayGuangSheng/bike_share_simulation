from fastapi.testclient import TestClient


def test_login_success(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@demo", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@demo", "password": "wrong"})
    assert resp.status_code == 401
