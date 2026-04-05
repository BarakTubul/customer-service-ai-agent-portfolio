from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "secure-pass-123"})
    assert response.status_code == 201
    return response.json()["access_token"]


def _guest_token(client: TestClient) -> str:
    response = client.post("/api/v1/auth/guest")
    assert response.status_code == 201
    return response.json()["access_token"]


def test_refund_eligibility_and_create_request(client: TestClient, db_session: Session) -> None:
    token = _register_and_get_token(client, "refund-owner@example.com")
    user_repo = UserRepository(db_session)
    owner = user_repo.get_by_email("refund-owner@example.com")
    assert owner is not None

    order_repo = OrderRepository(db_session)
    order_repo.create(order_id="ord-ref-1", user_id=owner.id)

    eligibility = client.post(
        "/api/v1/refunds/eligibility/check",
        json={
            "order_id": "ord-ref-1",
            "reason_code": "missing_item",
            "simulation_scenario_id": "default",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eligibility.status_code == 200
    assert "eligible" in eligibility.json()

    created = client.post(
        "/api/v1/refunds/requests",
        json={
            "order_id": "ord-ref-1",
            "reason_code": "missing_item",
            "simulation_scenario_id": "default",
        },
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-ref-1"},
    )
    assert created.status_code == 201
    request_id = created.json()["refund_request_id"]

    fetched = client.get(
        f"/api/v1/refunds/requests/{request_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["refund_request_id"] == request_id


def test_refund_create_idempotent_replay_returns_200(client: TestClient, db_session: Session) -> None:
    token = _register_and_get_token(client, "refund-idem@example.com")
    user_repo = UserRepository(db_session)
    owner = user_repo.get_by_email("refund-idem@example.com")
    assert owner is not None
    OrderRepository(db_session).create(order_id="ord-ref-2", user_id=owner.id)

    payload = {
        "order_id": "ord-ref-2",
        "reason_code": "missing_item",
        "simulation_scenario_id": "default",
    }

    first = client.post(
        "/api/v1/refunds/requests",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-ref-2"},
    )
    second = client.post(
        "/api/v1/refunds/requests",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-ref-2"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["refund_request_id"] == second.json()["refund_request_id"]
    assert second.json()["idempotent_replay"] is True


def test_guest_refund_actions_forbidden(client: TestClient, db_session: Session) -> None:
    owner_token = _register_and_get_token(client, "owner-for-guest-test@example.com")
    owner = UserRepository(db_session).get_by_email("owner-for-guest-test@example.com")
    assert owner is not None
    OrderRepository(db_session).create(order_id="ord-ref-3", user_id=owner.id)

    guest_token = _guest_token(client)
    response = client.post(
        "/api/v1/refunds/eligibility/check",
        json={
            "order_id": "ord-ref-3",
            "reason_code": "missing_item",
            "simulation_scenario_id": "default",
        },
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert response.status_code == 403

    state_sim = client.get(
        "/api/v1/orders/ord-ref-3/state-sim?scenario_id=default",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert state_sim.status_code == 200
    assert "fulfillment_state" in state_sim.json()
