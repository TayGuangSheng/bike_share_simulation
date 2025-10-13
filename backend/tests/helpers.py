from __future__ import annotations

from fastapi.testclient import TestClient


def login_token(client: TestClient, email: str = "admin@demo", password: str = "admin123") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

