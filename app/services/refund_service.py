from __future__ import annotations

import hashlib
from datetime import UTC, timedelta

from app.core.errors import ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.schemas.refund import (
    MoneyAmount,
    OrderStateSimResponse,
    RefundCreateRequest,
    RefundEligibilityCheckRequest,
    RefundEligibilityCheckResponse,
    RefundRequestResponse,
)


class RefundService:
    def __init__(self, order_repository: OrderRepository, refund_repository: RefundRepository) -> None:
        self.order_repository = order_repository
        self.refund_repository = refund_repository

    def check_eligibility(self, *, user: User, payload: RefundEligibilityCheckRequest) -> RefundEligibilityCheckResponse:
        order = self._get_owned_order(user=user, order_id=payload.order_id)
        simulated_state = self._simulate_order_state(order_id=order.order_id, scenario_id=payload.simulation_scenario_id)

        decision_reason_codes: list[str] = []
        eligible = True

        if payload.simulation_scenario_id in {"expired-window", "non-refundable"}:
            eligible = False
            decision_reason_codes.append("refund_window_expired")

        if payload.reason_code in {"fraud", "abuse"}:
            eligible = False
            decision_reason_codes.append("manual_review_required")

        if not decision_reason_codes:
            decision_reason_codes.append("eligible")

        amount = 0.0 if not eligible else 12.5
        if simulated_state["payment_state"] == "pending":
            amount = 0.0
            eligible = False
            if "payment_not_captured" not in decision_reason_codes:
                decision_reason_codes.append("payment_not_captured")

        return RefundEligibilityCheckResponse(
            eligible=eligible,
            decision_reason_codes=decision_reason_codes,
            policy_reference="refund-policy-v1",
            refundable_amount=MoneyAmount(currency="USD", value=amount),
            simulated_state=simulated_state["fulfillment_state"],
        )

    def create_request(
        self,
        *,
        user: User,
        payload: RefundCreateRequest,
        idempotency_key: str | None,
    ) -> RefundRequestResponse:
        order = self._get_owned_order(user=user, order_id=payload.order_id)
        stable_key = idempotency_key or self._build_idempotency_key(
            user_id=user.id,
            order_id=payload.order_id,
            reason_code=payload.reason_code,
            scenario_id=payload.simulation_scenario_id,
        )

        existing = self.refund_repository.get_by_idempotency_key(stable_key)
        if existing is not None:
            return RefundRequestResponse(
                refund_request_id=existing.refund_request_id,
                order_id=existing.order_id,
                status=existing.status,
                status_reason=existing.status_reason,
                created_at=existing.created_at,
                idempotent_replay=True,
            )

        eligibility = self.check_eligibility(
            user=user,
            payload=RefundEligibilityCheckRequest(
                order_id=payload.order_id,
                reason_code=payload.reason_code,
                item_selections=payload.item_selections,
                simulation_scenario_id=payload.simulation_scenario_id,
            ),
        )
        status = "submitted" if eligibility.eligible else "denied"
        status_reason = None if eligibility.eligible else ",".join(eligibility.decision_reason_codes)

        request_id = hashlib.sha256(
            f"{stable_key}:{order.order_id}:{payload.reason_code}".encode("utf-8")
        ).hexdigest()[:16]

        created = self.refund_repository.create(
            refund_request_id=request_id,
            idempotency_key=stable_key,
            user_id=user.id,
            order_id=order.order_id,
            reason_code=payload.reason_code,
            simulation_scenario_id=payload.simulation_scenario_id,
            status=status,
            status_reason=status_reason,
        )

        return RefundRequestResponse(
            refund_request_id=created.refund_request_id,
            order_id=created.order_id,
            status=created.status,
            status_reason=created.status_reason,
            created_at=created.created_at,
            idempotent_replay=False,
        )

    def get_request(self, *, user: User, refund_request_id: str) -> RefundRequestResponse:
        row = self.refund_repository.get_by_refund_request_id(refund_request_id)
        if row is None:
            raise NotFoundError("Refund request not found")
        if row.user_id != user.id:
            raise ForbiddenError("Refund request does not belong to current user")

        return RefundRequestResponse(
            refund_request_id=row.refund_request_id,
            order_id=row.order_id,
            status=row.status,
            status_reason=row.status_reason,
            created_at=row.created_at,
            idempotent_replay=False,
        )

    def get_order_state_sim(self, *, user: User, order_id: str, scenario_id: str) -> OrderStateSimResponse:
        order = self._get_owned_order(user=user, order_id=order_id)
        simulated = self._simulate_order_state(order_id=order.order_id, scenario_id=scenario_id)

        now = order.updated_at.astimezone(UTC)
        timeline = [
            {"state": "accepted", "timestamp": (now - timedelta(minutes=30)).isoformat()},
            {"state": "preparing", "timestamp": (now - timedelta(minutes=20)).isoformat()},
            {"state": simulated["fulfillment_state"], "timestamp": now.isoformat()},
        ]
        return OrderStateSimResponse(
            order_id=order.order_id,
            simulation_scenario_id=scenario_id,
            fulfillment_state=simulated["fulfillment_state"],
            payment_state=simulated["payment_state"],
            state_timeline=timeline,
        )

    def _get_owned_order(self, *, user: User, order_id: str):
        if user.is_guest:
            raise ForbiddenError("Guest users cannot submit refund actions")
        order = self.order_repository.get_by_order_id(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if order.user_id != user.id:
            raise ForbiddenError("Order does not belong to current user")
        return order

    @staticmethod
    def _build_idempotency_key(*, user_id: int, order_id: str, reason_code: str, scenario_id: str) -> str:
        raw = f"{user_id}:{order_id}:{reason_code}:{scenario_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _simulate_order_state(*, order_id: str, scenario_id: str) -> dict[str, str]:
        key = hashlib.sha256(f"{order_id}:{scenario_id}".encode("utf-8")).hexdigest()
        bucket = int(key[:2], 16) % 3
        if scenario_id == "payment-pending":
            return {"fulfillment_state": "delivered", "payment_state": "pending"}
        if scenario_id == "expired-window":
            return {"fulfillment_state": "delivered", "payment_state": "captured"}
        if bucket == 0:
            return {"fulfillment_state": "delivered", "payment_state": "captured"}
        if bucket == 1:
            return {"fulfillment_state": "in_transit", "payment_state": "captured"}
        return {"fulfillment_state": "preparing", "payment_state": "authorized"}
