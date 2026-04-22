from __future__ import annotations

import hashlib
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
SIMULATION_SCENARIOS = ("on_time", "late_delivery", "missing_item", "wrong_item", "quality_issue")


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


def _pick_default_scenario(order_id: str) -> str:
    seed = hashlib.sha256(order_id.encode("utf-8")).hexdigest()
    idx = int(seed[:2], 16) % len(SIMULATION_SCENARIOS)
    return SIMULATION_SCENARIOS[idx]


def _order_id_for_scenario(prefix: str, scenario: str) -> str:
    for idx in range(5000):
        candidate = f"{prefix}-{idx}"
        if _pick_default_scenario(candidate) == scenario:
            return candidate
    raise AssertionError(f"Could not find order id for scenario {scenario}")


def test_eligibility_ineligible_for_expired_window() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order_id = _order_id_for_scenario("ord-r-1", "late_delivery")
        order = order_repo.create(order_id=order_id, user_id=user.id, total_cents=2500)
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
                order_id=order_id,
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
        order_id = _order_id_for_scenario("ord-r-4", "missing_item")
        _create_delivered_order(order_repo, order_id=order_id, user_id=user.id, total_cents=2400)

        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )
        response = service.check_eligibility(
            user=user,
            payload=RefundEligibilityCheckRequest(
                order_id=order_id,
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
        order_id = _order_id_for_scenario("ord-r-2", "missing_item")
        _create_delivered_order(order_repo, order_id=order_id, user_id=user.id, total_cents=3000)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        payload = RefundCreateRequest(
            order_id=order_id,
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
        order_id = _order_id_for_scenario("ord-r-3", "late_delivery")
        _create_delivered_order(order_repo, order_id=order_id, user_id=owner.id, total_cents=2000)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        try:
            service.check_eligibility(
                user=guest,
                payload=RefundEligibilityCheckRequest(
                    order_id=order_id,
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
        order_id = _order_id_for_scenario("ord-r-5", "on_time")
        _create_delivered_order(order_repo, order_id=order_id, user_id=user.id, total_cents=2800)
        service = RefundService(
            order_repository=order_repo,
            refund_repository=RefundRepository(session),
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        response = service.create_request(
            user=user,
            payload=RefundCreateRequest(
                order_id=order_id,
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
                order_id=order_id,
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


def test_list_user_requests_normalizes_legacy_chat_refund_values() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        _create_delivered_order(order_repo, order_id="ord-r-legacy-chat", user_id=user.id, total_cents=2500)

        refund_repo = RefundRepository(session)
        refund_repo.create(
            refund_request_id="legacy-chat-1",
            idempotency_key="legacy-chat-idem",
            user_id=user.id,
            order_id="ord-r-legacy-chat",
            reason_code="chat_human_assistance",
            simulation_scenario_id="chat",
            status="submitted",
            status_reason=None,
            policy_version="chat",
            policy_reference="legacy-chat-policy",
            resolution_action="approve_partial",
            decision_reason_codes="chat_escalation",
            refundable_amount_currency="USD",
            refundable_amount_value=5.0,
        )

        service = RefundService(
            order_repository=order_repo,
            refund_repository=refund_repo,
            account_order_service=AccountOrderService(order_repo, UserRepository(session)),
        )

        rows = service.list_user_requests(user=user)

        assert rows.total == 1
        assert rows.limit == 10
        assert rows.offset == 0
        assert len(rows.items) == 1
        assert rows.items[0].reason_code == RefundReasonCode.OTHER
        assert rows.items[0].decision_reason_codes == [RefundDecisionReasonCode.REASON_CODE_NOT_SUPPORTED]
        assert rows.items[0].policy_version == RefundPolicyVersion.V1
    finally:
        session.close()
