from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secure-pass-123",
            "full_name": "Test User",
            "date_of_birth": "1990-01-01",
            "address": "123 Test Street",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_auth_session_endpoint_returns_current_state(client: TestClient) -> None:
    token = _register_and_get_token(client, "session-user@example.com")

    response = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["is_guest"] is False


def test_account_me_returns_profile_details(client: TestClient) -> None:
    token = _register_and_get_token(client, "profile-details@example.com")

    response = client.get("/api/v1/account/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "Test User"
    assert payload["date_of_birth"] == "1990-01-01"
    assert payload["address"] == "123 Test Street"


def test_account_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/account/me")
    assert response.status_code == 401


def test_order_requires_ownership(client: TestClient, db_session: Session) -> None:
    user_one_token = _register_and_get_token(client, "owner@example.com")
    user_two_token = _register_and_get_token(client, "other@example.com")

    user_repo = UserRepository(db_session)
    owner = user_repo.get_by_email("owner@example.com")
    assert owner is not None

    order_repo = OrderRepository(db_session)
    order_repo.create(order_id="ord-001", user_id=owner.id)

    owner_response = client.get("/api/v1/orders/ord-001", headers={"Authorization": f"Bearer {user_one_token}"})
    assert owner_response.status_code == 200

    forbidden_response = client.get(
        "/api/v1/orders/ord-001",
        headers={"Authorization": f"Bearer {user_two_token}"},
    )
    assert forbidden_response.status_code == 403


def test_order_timeline_sim_returns_events(client: TestClient, db_session: Session) -> None:
    token = _register_and_get_token(client, "timeline@example.com")

    user_repo = UserRepository(db_session)
    user = user_repo.get_by_email("timeline@example.com")
    assert user is not None

    order_repo = OrderRepository(db_session)
    order_repo.create(order_id="ord-002", user_id=user.id)

    response = client.get(
        "/api/v1/orders/ord-002/timeline-sim?scenario_id=slow-driver",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == "slow-driver"
    assert len(payload["events"]) >= 4
