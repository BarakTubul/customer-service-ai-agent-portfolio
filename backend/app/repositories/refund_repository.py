from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refund_request import RefundRequest


class RefundRepository:
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
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
