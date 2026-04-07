from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


def test_expired_auth_cookie_is_rejected() -> None:
    client = TestClient(app)
    expired_token = create_access_token(
        "1",
        is_guest=False,
        expires_delta=timedelta(seconds=-1),
    )

    client.cookies.set("access_token", expired_token)
    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "Invalid or expired token"


def test_session_endpoint_requires_cookie_even_with_valid_bearer() -> None:
    client = TestClient(app)
    valid_token = create_access_token(
        "1",
        is_guest=False,
    )

    response = client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {valid_token}"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"