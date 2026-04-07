from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.core.errors import ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.services.refund_policy_engine import RefundPolicyEngine
from app.schemas.refund import (
    ManualReviewHandoff,
    MoneyAmount,
    OrderStateSimResponse,
    RefundCreateRequest,
    RefundEligibilityCheckRequest,
    RefundEligibilityCheckResponse,
    RefundResolutionAction,
    RefundRequestResponse,
)


class RefundService:
    MANUAL_REVIEW_QUEUE_NAME = "refund-risk-review"
    MANUAL_REVIEW_SLA_HOURS = 24

    def __init__(self, order_repository: OrderRepository, refund_repository: RefundRepository) -> None:
        self.order_repository = order_repository
        self.refund_repository = refund_repository
        self.policy_engine = RefundPolicyEngine()

    def check_eligibility(self, *, user: User, payload: RefundEligibilityCheckRequest) -> RefundEligibilityCheckResponse:
        order = self._get_owned_order(user=user, order_id=payload.order_id)
        simulated_state = self._simulate_order_state(order_id=order.order_id, scenario_id=payload.simulation_scenario_id)

        decision = self.policy_engine.evaluate(
            reason_code=payload.reason_code,
            simulation_scenario_id=payload.simulation_scenario_id,
            fulfillment_state=simulated_state["fulfillment_state"],
            payment_state=simulated_state["payment_state"],
        )

        return RefundEligibilityCheckResponse(
            eligible=decision.eligible,
            resolution_action=decision.resolution_action,
            decision_reason_codes=decision.decision_reason_codes,
            explanation_template_key=decision.explanation_template_key,
            explanation_params=decision.explanation_params,
            policy_version=decision.policy_version,
            policy_reference=decision.policy_reference,
            refundable_amount=MoneyAmount(currency="USD", value=decision.refundable_amount_value),
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
                manual_review_handoff=self._build_manual_review_handoff_from_row(existing),
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
        manual_review_handoff = self._build_manual_review_handoff(
            user_id=user.id,
            order_id=order.order_id,
            reason_code=payload.reason_code,
            simulation_scenario_id=payload.simulation_scenario_id,
            eligibility=eligibility,
        )

        status = "submitted" if eligibility.eligible else "denied"
        if manual_review_handoff is not None:
            status = "pending_manual_review"
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
            policy_version=eligibility.policy_version,
            policy_reference=eligibility.policy_reference,
            resolution_action=eligibility.resolution_action,
            decision_reason_codes=",".join(eligibility.decision_reason_codes),
            refundable_amount_currency=eligibility.refundable_amount.currency,
            refundable_amount_value=eligibility.refundable_amount.value,
            explanation_template_key=eligibility.explanation_template_key,
            explanation_params_json=json.dumps(
                self._serialize_explanation_params(eligibility.explanation_params),
                separators=(",", ":"),
                sort_keys=True,
            ),
            escalation_status=manual_review_handoff.escalation_status if manual_review_handoff else None,
            escalation_queue_name=manual_review_handoff.queue_name if manual_review_handoff else None,
            escalation_sla_deadline_at=manual_review_handoff.sla_deadline_at if manual_review_handoff else None,
            escalation_payload_json=(
                json.dumps(manual_review_handoff.payload, separators=(",", ":"), sort_keys=True)
                if manual_review_handoff
                else None
            ),
        )

        return RefundRequestResponse(
            refund_request_id=created.refund_request_id,
            order_id=created.order_id,
            status=created.status,
            status_reason=created.status_reason,
            manual_review_handoff=manual_review_handoff,
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
            manual_review_handoff=self._build_manual_review_handoff_from_row(row),
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
        if scenario_id == "delivered-happy":
            return {"fulfillment_state": "delivered", "payment_state": "captured"}
        if scenario_id == "payment-pending":
            return {"fulfillment_state": "delivered", "payment_state": "pending"}
        if scenario_id == "expired-window":
            return {"fulfillment_state": "delivered", "payment_state": "captured"}
        if bucket == 0:
            return {"fulfillment_state": "delivered", "payment_state": "captured"}
        if bucket == 1:
            return {"fulfillment_state": "in_transit", "payment_state": "captured"}
        return {"fulfillment_state": "preparing", "payment_state": "authorized"}

    @staticmethod
    def _serialize_explanation_params(params: dict[str, str | int | float | bool]) -> dict[str, str | int | float | bool]:
        serialized: dict[str, str | int | float | bool] = {}
        for key, value in params.items():
            if isinstance(value, Enum):
                serialized[key] = str(value.value)
            else:
                serialized[key] = value
        return serialized

    def _build_manual_review_handoff(
        self,
        *,
        user_id: int,
        order_id: str,
        reason_code: str,
        simulation_scenario_id: str,
        eligibility: RefundEligibilityCheckResponse,
    ) -> ManualReviewHandoff | None:
        if eligibility.resolution_action != RefundResolutionAction.MANUAL_REVIEW:
            return None

        created_at = datetime.now(UTC)
        return ManualReviewHandoff(
            escalation_status="queued",
            queue_name=self.MANUAL_REVIEW_QUEUE_NAME,
            sla_deadline_at=created_at + timedelta(hours=self.MANUAL_REVIEW_SLA_HOURS),
            payload={
                "user_id": user_id,
                "order_id": order_id,
                "reason_code": self._serialize_scalar(reason_code),
                "simulation_scenario_id": simulation_scenario_id,
                "decision_reason_codes": ",".join(eligibility.decision_reason_codes),
                "policy_version": self._serialize_scalar(eligibility.policy_version),
                "policy_reference": eligibility.policy_reference,
                "resolution_action": self._serialize_scalar(eligibility.resolution_action),
                "refundable_amount": eligibility.refundable_amount.value,
                "currency": eligibility.refundable_amount.currency,
                "explanation_template_key": eligibility.explanation_template_key,
            },
        )

    @staticmethod
    def _build_manual_review_handoff_from_row(row) -> ManualReviewHandoff | None:
        if row.escalation_status is None:
            return None
        payload_raw = row.escalation_payload_json or "{}"
        payload = json.loads(payload_raw)
        return ManualReviewHandoff(
            escalation_status=row.escalation_status,
            queue_name=row.escalation_queue_name,
            sla_deadline_at=row.escalation_sla_deadline_at,
            payload=payload,
        )

    @staticmethod
    def _serialize_scalar(value: str | int | float | bool | Enum) -> str | int | float | bool:
        if isinstance(value, Enum):
            return str(value.value)
        return value
