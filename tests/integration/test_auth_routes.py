from __future__ import annotations

from fastapi.testclient import TestClient


def test_guest_endpoint_returns_guest_token(client: TestClient) -> None:
    response = client.post("/api/v1/auth/guest")

    assert response.status_code == 201
    payload = response.json()
    assert payload["is_guest"] is True
    assert "access_token" in payload


def test_guest_convert_endpoint_upgrades_user(client: TestClient) -> None:
    guest_response = client.post("/api/v1/auth/guest")
    assert guest_response.status_code == 201
    token = guest_response.json()["access_token"]

    response = client.post(
        "/api/v1/auth/guest/convert",
        json={"email": "newuser@example.com", "password": "secure-pass-123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_guest"] is False
    assert payload["user_id"] > 0
