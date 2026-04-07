from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refund_request import RefundRequest


class RefundRepository:
    VALID_ESCALATION_TRANSITIONS: dict[str, set[str]] = {
        "queued": {"in_review"},
        "in_review": {"resolved", "rejected"},
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_refund_request_id(self, refund_request_id: str) -> RefundRequest | None:
        stmt = select(RefundRequest).where(RefundRequest.refund_request_id == refund_request_id)
        return self.db.scalar(stmt)

    def get_by_idempotency_key(self, idempotency_key: str) -> RefundRequest | None:
        stmt = select(RefundRequest).where(RefundRequest.idempotency_key == idempotency_key)
        return self.db.scalar(stmt)

    def create(
        self,
        *,
        refund_request_id: str,
        idempotency_key: str,
        user_id: int,
        order_id: str,
        reason_code: str,
        simulation_scenario_id: str,
        status: str,
        status_reason: str | None,
        policy_version: str | None = None,
        policy_reference: str | None = None,
        resolution_action: str | None = None,
        decision_reason_codes: str | None = None,
        refundable_amount_currency: str | None = None,
        refundable_amount_value: float | None = None,
        explanation_template_key: str | None = None,
        explanation_params_json: str | None = None,
        escalation_status: str | None = None,
        escalation_queue_name: str | None = None,
        escalation_sla_deadline_at: datetime | None = None,
        escalation_payload_json: str | None = None,
    ) -> RefundRequest:
        row = RefundRequest(
            refund_request_id=refund_request_id,
            idempotency_key=idempotency_key,
            user_id=user_id,
            order_id=order_id,
            reason_code=reason_code,
            simulation_scenario_id=simulation_scenario_id,
            status=status,
            status_reason=status_reason,
            policy_version=policy_version,
            policy_reference=policy_reference,
            resolution_action=resolution_action,
            decision_reason_codes=decision_reason_codes,
            refundable_amount_currency=refundable_amount_currency,
            refundable_amount_value=refundable_amount_value,
            explanation_template_key=explanation_template_key,
            explanation_params_json=explanation_params_json,
            escalation_status=escalation_status,
            escalation_queue_name=escalation_queue_name,
            escalation_sla_deadline_at=escalation_sla_deadline_at,
            escalation_payload_json=escalation_payload_json,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_pending_manual_review(
        self,
        *,
        limit: int = 50,
        before_sla: datetime | None = None,
    ) -> list[RefundRequest]:
        bounded_limit = max(1, min(limit, 500))
        stmt = select(RefundRequest).where(RefundRequest.escalation_status == "queued")
        if before_sla is not None:
            stmt = stmt.where(RefundRequest.escalation_sla_deadline_at <= before_sla)
        stmt = stmt.order_by(RefundRequest.escalation_sla_deadline_at.asc(), RefundRequest.created_at.asc()).limit(
            bounded_limit
        )
        return list(self.db.scalars(stmt).all())

    def transition_escalation_status(
        self,
        *,
        refund_request_id: str,
        to_status: str,
    ) -> RefundRequest | None:
        if to_status not in {"in_review", "resolved", "rejected"}:
            raise ValueError(f"Unsupported escalation status: {to_status}")

        row = self.get_by_refund_request_id(refund_request_id)
        if row is None or row.escalation_status is None:
            return None

        allowed_targets = self.VALID_ESCALATION_TRANSITIONS.get(row.escalation_status, set())
        if to_status not in allowed_targets:
            return None

        row.escalation_status = to_status
        if to_status == "resolved":
            row.status = "resolved"
            row.status_reason = "manual_review_resolved"
        if to_status == "rejected":
            row.status = "denied"
            row.status_reason = "manual_review_rejected"

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
