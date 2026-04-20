from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ForbiddenError
from app.db.base import Base
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.user_repository import UserRepository
from app.services.account_order_service import AccountOrderService
from app.services.refund_service import RefundService
from app.schemas.refund import (
    RefundCreateRequest,
    RefundDecisionReasonCode,
    RefundEligibilityCheckRequest,
    RefundPolicyVersion,
    RefundReasonCode,
    RefundResolutionAction,
)


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return local_session()


def _create_user(session: Session, *, is_guest: bool = False) -> User:
    user = User(email=None if is_guest else "u@example.com", password_hash=None, is_guest=is_guest, is_active=True, is_verified=not is_guest)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_delivered_order(order_repo: OrderRepository, *, order_id: str, user_id: int, total_cents: int) -> None:
    order = order_repo.create(order_id=order_id, user_id=user_id, total_cents=total_cents)
    order.created_at = datetime.now(UTC) - timedelta(hours=2)
    order.updated_at = order.created_at
    order_repo.db.add(order)
    order_repo.db.commit()
    order_repo.db.refresh(order)


def test_eligibility_ineligible_for_expired_window() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order = order_repo.create(order_id="ord-r-1", user_id=user.id, total_cents=2500)
        order.updated_at = datetime.now(UTC) - timedelta(hours=72)
        order.created_at = order.updated_at
        session.add(order)
        session.commit()

        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
            refund_window_hours=24,
        )
        response = service.check_eligibility(
            user=user,
            payload=RefundEligibilityCheckRequest(
                order_id="ord-r-1",
                reason_code=RefundReasonCode.LATE_DELIVERY,
                simulation_scenario_id="delivered-happy",
            ),
        )

        assert response.eligible is False
        assert response.resolution_action == RefundResolutionAction.DENY
        assert RefundDecisionReasonCode.REFUND_WINDOW_EXPIRED in response.decision_reason_codes
        assert response.explanation_template_key == "refund.refund_window_expired"
        assert response.explanation_params["refund_window_hours"] == 24
        assert response.policy_version == RefundPolicyVersion.V1
    finally:
        session.close()


def test_eligibility_partial_for_missing_item() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        _create_delivered_order(order_repo, order_id="ord-r-4", user_id=user.id, total_cents=2400)

        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )
        response = service.check_eligibility(
            user=user,
            payload=RefundEligibilityCheckRequest(
                order_id="ord-r-4",
                reason_code=RefundReasonCode.MISSING_ITEM,
                simulation_scenario_id="delivered-happy",
            ),
        )

        assert response.eligible is True
        assert response.resolution_action == RefundResolutionAction.APPROVE_PARTIAL
        assert response.decision_reason_codes == [RefundDecisionReasonCode.ELIGIBLE_PARTIAL]
        assert response.explanation_template_key == "refund.reason_policy_outcome"
        assert response.explanation_params["submitted_reason"] == RefundReasonCode.MISSING_ITEM
        assert response.refundable_amount.value == 12.0
    finally:
        session.close()


def test_create_request_idempotent_replay() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        _create_delivered_order(order_repo, order_id="ord-r-2", user_id=user.id, total_cents=3000)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        payload = RefundCreateRequest(
            order_id="ord-r-2",
            reason_code=RefundReasonCode.MISSING_ITEM,
            simulation_scenario_id="default",
        )
        first = service.create_request(user=user, payload=payload, idempotency_key="idem-1")
        second = service.create_request(user=user, payload=payload, idempotency_key="idem-1")

        assert first.refund_request_id == second.refund_request_id
        assert first.idempotent_replay is False
        assert second.idempotent_replay is True

        stored = service.refund_repository.get_by_refund_request_id(first.refund_request_id)
        assert stored is not None
        assert stored.policy_version == RefundPolicyVersion.V1
        assert stored.policy_reference == "refund-policy-v1"
        assert stored.resolution_action == RefundResolutionAction.APPROVE_PARTIAL
        assert stored.decision_reason_codes == RefundDecisionReasonCode.ELIGIBLE_PARTIAL
        assert stored.refundable_amount_currency == "USD"
        assert stored.refundable_amount_value == 15.0
        assert stored.explanation_template_key == "refund.reason_policy_outcome"
        explanation_params = json.loads(stored.explanation_params_json or "{}")
        assert explanation_params["submitted_reason"] == RefundReasonCode.MISSING_ITEM
        assert explanation_params["resolution_action"] == RefundResolutionAction.APPROVE_PARTIAL
    finally:
        session.close()


def test_guest_cannot_submit_refund() -> None:
    session = build_session()
    try:
        guest = _create_user(session, is_guest=True)
        owner = _create_user(session)
        order_repo = OrderRepository(session)
        _create_delivered_order(order_repo, order_id="ord-r-3", user_id=owner.id, total_cents=2000)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        try:
            service.check_eligibility(
                user=guest,
                payload=RefundEligibilityCheckRequest(
                    order_id="ord-r-3",
                    reason_code=RefundReasonCode.LATE_DELIVERY,
                    simulation_scenario_id="default",
                ),
            )
            assert False, "Expected ForbiddenError"
        except ForbiddenError:
            assert True
    finally:
        session.close()


def test_create_request_manual_review_emits_handoff_contract() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        _create_delivered_order(order_repo, order_id="ord-r-5", user_id=user.id, total_cents=2800)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        response = service.create_request(
            user=user,
            payload=RefundCreateRequest(
                order_id="ord-r-5",
                reason_code=RefundReasonCode.FRAUD,
                simulation_scenario_id="default",
            ),
            idempotency_key="idem-manual-review-1",
        )

        assert response.status == "pending_manual_review"
        assert response.manual_review_handoff is not None
        assert response.manual_review_handoff.escalation_status == "queued"
        assert response.manual_review_handoff.queue_name == "refund-risk-review"
        assert response.manual_review_handoff.payload["reason_code"] == RefundReasonCode.FRAUD.value
        assert response.manual_review_handoff.payload["resolution_action"] == RefundResolutionAction.MANUAL_REVIEW.value

        replay = service.create_request(
            user=user,
            payload=RefundCreateRequest(
                order_id="ord-r-5",
                reason_code=RefundReasonCode.FRAUD,
                simulation_scenario_id="default",
            ),
            idempotency_key="idem-manual-review-1",
        )
        assert replay.idempotent_replay is True
        assert replay.manual_review_handoff is not None
        assert replay.manual_review_handoff.escalation_status == "queued"
    finally:
        session.close()
