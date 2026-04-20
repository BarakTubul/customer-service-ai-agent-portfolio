from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.core.errors import ForbiddenError, NotFoundError
from app.core.errors import ConflictError
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.services.account_order_service import AccountOrderService
from app.services.refund_policy_engine import RefundPolicyEngine
from app.schemas.refund import (
    ManualReviewDecision,
    ManualReviewEscalationStatus,
    ManualReviewHandoff,
    ManualReviewQueueItem,
    ManualReviewQueueResponse,
    MoneyAmount,
    OrderStateSimResponse,
    RefundCreateRequest,
    RefundEligibilityCheckRequest,
    RefundEligibilityCheckResponse,
    RefundRequestStatus,
    RefundResolutionAction,
    RefundRequestResponse,
)


class RefundService:
    MANUAL_REVIEW_QUEUE_NAME = "refund-risk-review"
    MANUAL_REVIEW_SLA_HOURS = 24
    _REASON_SCENARIO_POOL: dict[str, tuple[str, ...]] = {
        "missing_item": ("missing-item", "delivered-happy"),
        "wrong_item": ("wrong-item", "delivered-happy"),
        "late_delivery": ("late-delivery", "delivered-happy"),
        "quality_issue": ("quality-issue", "delivered-happy"),
        "fraud": ("non-refundable", "payment-pending", "default"),
        "abuse": ("non-refundable", "payment-pending", "default"),
        "other": ("default", "payment-pending", "in-transit"),
    }
    _DEFAULT_SCENARIO_POOL: tuple[str, ...] = ("default", "in-transit", "payment-pending", "delivered-happy")

    def __init__(
        self,
        order_repository: OrderRepository,
        refund_repository: RefundRepository,
        account_order_service: AccountOrderService,
        refund_window_hours: int = 48,
    ) -> None:
        self.order_repository = order_repository
        self.refund_repository = refund_repository
        self.account_order_service = account_order_service
        self.policy_engine = RefundPolicyEngine()
        self.refund_window_hours = max(1, refund_window_hours)

    def check_eligibility(self, *, user: User, payload: RefundEligibilityCheckRequest) -> RefundEligibilityCheckResponse:
        order = self._get_owned_order(user=user, order_id=payload.order_id)
        order_state = self._build_order_state_snapshot(user=user, order=order)

        decision = self.policy_engine.evaluate(
            reason_code=payload.reason_code,
            simulation_scenario_id=order_state["fulfillment_state"],
            fulfillment_state=order_state["fulfillment_state"],
            payment_state=order_state["payment_state"],
            issue_code=order_state["issue_code"],
            is_delayed=bool(order_state["is_delayed"]),
            refund_window_hours=self.refund_window_hours,
            order_age_hours=self._calculate_order_age_hours(order),
        )
        refundable_amount_value = self._compute_refundable_amount(order_total_cents=order.total_cents, refund_ratio=decision.refundable_ratio)
        explanation_params = dict(decision.explanation_params)
        explanation_params["order_total_cents"] = order.total_cents or 0
        explanation_params["refundable_amount"] = refundable_amount_value

        return RefundEligibilityCheckResponse(
            eligible=decision.eligible,
            resolution_action=decision.resolution_action,
            decision_reason_codes=decision.decision_reason_codes,
            explanation_template_key=decision.explanation_template_key,
            explanation_params=explanation_params,
            policy_version=decision.policy_version,
            policy_reference=decision.policy_reference,
            refundable_amount=MoneyAmount(currency="USD", value=refundable_amount_value),
            simulated_state=order_state["fulfillment_state"],
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

        order_state = self._build_order_state_snapshot(user=user, order=order)
        decision = self.policy_engine.evaluate(
            reason_code=payload.reason_code,
            simulation_scenario_id=order_state["fulfillment_state"],
            fulfillment_state=order_state["fulfillment_state"],
            payment_state=order_state["payment_state"],
            issue_code=order_state["issue_code"],
            is_delayed=bool(order_state["is_delayed"]),
            refund_window_hours=self.refund_window_hours,
            order_age_hours=self._calculate_order_age_hours(order),
        )
        refundable_amount_value = self._compute_refundable_amount(
            order_total_cents=order.total_cents,
            refund_ratio=decision.refundable_ratio,
        )
        explanation_params = dict(decision.explanation_params)
        explanation_params["order_total_cents"] = order.total_cents or 0
        explanation_params["refundable_amount"] = refundable_amount_value

        eligibility = RefundEligibilityCheckResponse(
            eligible=decision.eligible,
            resolution_action=decision.resolution_action,
            decision_reason_codes=decision.decision_reason_codes,
            explanation_template_key=decision.explanation_template_key,
            explanation_params=explanation_params,
            policy_version=decision.policy_version,
            policy_reference=decision.policy_reference,
            refundable_amount=MoneyAmount(currency="USD", value=refundable_amount_value),
            simulated_state=order_state["fulfillment_state"],
        )
        manual_review_handoff = self._build_manual_review_handoff(
            user_id=user.id,
            order_id=order.order_id,
            reason_code=payload.reason_code,
            simulation_scenario_id=str(order_state["fulfillment_state"]),
            eligibility=eligibility,
        )

        status = RefundRequestStatus.SUBMITTED if eligibility.eligible else RefundRequestStatus.DENIED
        if manual_review_handoff is not None:
            status = RefundRequestStatus.PENDING_MANUAL_REVIEW
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
            simulation_scenario_id=str(order_state["fulfillment_state"]),
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

        return self._build_refund_response_from_row(row)

    def list_user_requests(self, *, user: User, limit: int = 100) -> list[RefundRequestResponse]:
        """List all refund requests for the current user."""
        rows = self.refund_repository.list_by_user_id(user_id=user.id, limit=limit)
        return [self._build_refund_response_from_row(row) for row in rows]

    def list_manual_review_queue(
        self,
        *,
        limit: int = 50,
        before_sla: datetime | None = None,
    ) -> ManualReviewQueueResponse:
        rows = self.refund_repository.list_pending_manual_review(limit=limit, before_sla=before_sla)
        items = [self._build_manual_review_queue_item(row) for row in rows if row.escalation_status is not None]
        return ManualReviewQueueResponse(items=items, total=len(items))

    def claim_manual_review_request(self, *, refund_request_id: str, admin_user_id: int) -> RefundRequestResponse:
        row = self.refund_repository.get_by_refund_request_id(refund_request_id)
        if row is None:
            raise NotFoundError("Refund request not found")
        transitioned = self.refund_repository.transition_escalation_status(
            refund_request_id=refund_request_id,
            to_status=ManualReviewEscalationStatus.IN_REVIEW,
            actor_admin_user_id=admin_user_id,
        )
        if transitioned is None:
            raise ConflictError("Refund request cannot be claimed in current state")
        return self._build_refund_response_from_row(transitioned)

    def decide_manual_review_request(
        self,
        *,
        refund_request_id: str,
        decision: ManualReviewDecision,
        reviewer_note: str | None,
        admin_user_id: int,
    ) -> RefundRequestResponse:
        row = self.refund_repository.get_by_refund_request_id(refund_request_id)
        if row is None:
            raise NotFoundError("Refund request not found")
        transitioned = self.refund_repository.transition_escalation_status(
            refund_request_id=refund_request_id,
            to_status=decision,
            actor_admin_user_id=admin_user_id,
            reviewer_note=reviewer_note,
        )
        if transitioned is None:
            raise ConflictError("Refund request cannot be decided in current state")
        return self._build_refund_response_from_row(transitioned)

    def get_order_state_sim(
        self,
        *,
        user: User,
        order_id: str,
        scenario_id: str | None = None,
        reason_code: str | None = None,
    ) -> OrderStateSimResponse:
        order = self._get_owned_order(user=user, order_id=order_id)
        order_state = self._build_order_state_snapshot(user=user, order=order)
        timeline = [
            {"state": event["state"], "timestamp": event["timestamp"]}
            for event in order_state["state_timeline"]
        ]
        return OrderStateSimResponse(
            order_id=order.order_id,
            simulation_scenario_id=str(order_state["fulfillment_state"]),
            fulfillment_state=str(order_state["fulfillment_state"]),
            payment_state=str(order_state["payment_state"]),
            ordered_items_summary=order_state["ordered_items_summary"],
            received_items_summary=order_state["received_items_summary"],
            is_delayed=bool(order_state["is_delayed"]),
            eta_to=order_state["eta_to"],
            delivered_at=order_state["delivered_at"],
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

    def _build_order_state_snapshot(self, *, user: User, order):
        timeline = self.account_order_service.get_order_timeline_sim(
            user=user,
            order_id=order.order_id,
            scenario_id=None,
        )
        current_status = timeline.events[-1].event if timeline.events else "unknown"
        delivered = current_status == "delivered"
        delivered_at = timeline.events[-1].timestamp if delivered and timeline.events else None
        received_items_summary = timeline.received_items_summary if delivered else None

        return {
            "fulfillment_state": current_status,
            "payment_state": "captured",
            "issue_code": timeline.issue_code,
            "ordered_items_summary": order.ordered_items_summary,
            "received_items_summary": received_items_summary,
            "is_delayed": bool(timeline.is_delayed) if delivered else False,
            "eta_to": timeline.eta_to,
            "delivered_at": delivered_at,
            "state_timeline": [
                {"state": event.event, "timestamp": event.timestamp.isoformat()}
                for event in timeline.events
            ],
        }

    @staticmethod
    def _build_idempotency_key(*, user_id: int, order_id: str, reason_code: str) -> str:
        raw = f"{user_id}:{order_id}:{reason_code}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _select_simulation_scenario(
        self,
        *,
        order_id: str,
        reason_code: str,
        forced_scenario_id: str | None,
    ) -> str:
        if forced_scenario_id:
            return forced_scenario_id

        pool = self._REASON_SCENARIO_POOL.get(str(reason_code), self._DEFAULT_SCENARIO_POOL)
        seed = f"{order_id}:{reason_code}:{datetime.now(UTC).isoformat()}"
        return random.Random(seed).choice(pool)

    def _simulate_order_state(
        self,
        *,
        order,
        reason_code: str,
        scenario_id: str,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        eta_to = order.eta_to.astimezone(UTC) if order.eta_to else order.created_at.astimezone(UTC) + timedelta(minutes=45)
        delivered_at: datetime | None = None
        ordered_summary = order.ordered_items_summary
        received_summary = ordered_summary
        fulfillment_state = "delivered"
        payment_state = "captured"

        if scenario_id == "payment-pending":
            payment_state = "pending"
        elif scenario_id == "in-transit":
            fulfillment_state = "in_transit"
            delivered_at = None
            received_summary = None
        elif scenario_id == "missing-item":
            delivered_at = max(now, eta_to + timedelta(minutes=2))
            received_summary = f"{ordered_summary or 'Order items'} (one item missing)"
        elif scenario_id == "wrong-item":
            delivered_at = max(now, eta_to)
            received_summary = f"{ordered_summary or 'Order items'} (included wrong item)"
        elif scenario_id == "late-delivery":
            delivered_at = max(now, eta_to + timedelta(minutes=15))
        elif scenario_id == "quality-issue":
            delivered_at = max(now, eta_to)
            received_summary = f"{ordered_summary or 'Order items'} (quality issue reported)"
        elif scenario_id == "non-refundable":
            delivered_at = max(now, eta_to)
        else:
            delivered_at = max(now, eta_to)

        is_delayed = bool(delivered_at and delivered_at > eta_to)

        return {
            "scenario_id": scenario_id,
            "fulfillment_state": fulfillment_state,
            "payment_state": payment_state,
            "ordered_items_summary": ordered_summary,
            "received_items_summary": received_summary,
            "is_delayed": is_delayed,
            "eta_to": eta_to,
            "delivered_at": delivered_at,
        }

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
            escalation_status=ManualReviewEscalationStatus.QUEUED,
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
            claimed_by_admin_user_id=row.claimed_by_admin_user_id,
            claimed_at=row.claimed_at,
            decided_by_admin_user_id=row.decided_by_admin_user_id,
            decided_at=row.decided_at,
            reviewer_note=row.reviewer_note,
        )

    def _build_manual_review_queue_item(self, row) -> ManualReviewQueueItem:
        handoff = self._build_manual_review_handoff_from_row(row)
        if handoff is None:
            raise ValueError("Expected manual-review handoff data")
        return ManualReviewQueueItem(
            refund_request_id=row.refund_request_id,
            order_id=row.order_id,
            status=row.status,
            created_at=row.created_at,
            handoff=handoff,
        )

    def _build_refund_response_from_row(self, row) -> RefundRequestResponse:
        return RefundRequestResponse(
            refund_request_id=row.refund_request_id,
            order_id=row.order_id,
            status=row.status,
            status_reason=row.status_reason,
            manual_review_handoff=self._build_manual_review_handoff_from_row(row),
            created_at=row.created_at,
            idempotent_replay=False,
        )

    @staticmethod
    def _serialize_scalar(value: str | int | float | bool | Enum) -> str | int | float | bool:
        if isinstance(value, Enum):
            return str(value.value)
        return value

    @staticmethod
    def _compute_refundable_amount(*, order_total_cents: int | None, refund_ratio: float) -> float:
        if not order_total_cents or order_total_cents <= 0:
            return 0.0
        computed_cents = round(order_total_cents * max(0.0, min(refund_ratio, 1.0)))
        return computed_cents / 100.0

    @staticmethod
    def _calculate_order_age_hours(order) -> float:
        updated_at = order.updated_at.astimezone(UTC)
        age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
        return max(0.0, age_seconds / 3600.0)
