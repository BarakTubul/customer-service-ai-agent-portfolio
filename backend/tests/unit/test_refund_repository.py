from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return local_session()


def _create_user(session: Session) -> User:
    user = User(email="repo-user@example.com", password_hash=None, is_guest=False, is_active=True, is_verified=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_list_pending_manual_review_orders_by_sla() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-repo-1", user_id=user.id)
        order_repo.create(order_id="ord-repo-2", user_id=user.id)

        repo = RefundRepository(session)
        base_time = datetime.now(UTC)
        repo.create(
            refund_request_id="rr-1",
            idempotency_key="idem-rr-1",
            user_id=user.id,
            order_id="ord-repo-1",
            reason_code="fraud",
            simulation_scenario_id="delivered-happy",
            status="pending_manual_review",
            status_reason="manual_review_required",
            escalation_status="queued",
            escalation_queue_name="refund-risk-review",
            escalation_sla_deadline_at=base_time + timedelta(hours=2),
            escalation_payload_json="{}",
        )
        repo.create(
            refund_request_id="rr-2",
            idempotency_key="idem-rr-2",
            user_id=user.id,
            order_id="ord-repo-2",
            reason_code="fraud",
            simulation_scenario_id="delivered-happy",
            status="pending_manual_review",
            status_reason="manual_review_required",
            escalation_status="queued",
            escalation_queue_name="refund-risk-review",
            escalation_sla_deadline_at=base_time + timedelta(hours=1),
            escalation_payload_json="{}",
        )

        items = repo.list_pending_manual_review(limit=10)
        assert [row.refund_request_id for row in items] == ["rr-2", "rr-1"]

        filtered = repo.list_pending_manual_review(limit=10, before_sla=base_time + timedelta(hours=1, minutes=30))
        assert [row.refund_request_id for row in filtered] == ["rr-2"]
    finally:
        session.close()


def test_transition_escalation_status_enforces_flow() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-repo-3", user_id=user.id)

        repo = RefundRepository(session)
        created = repo.create(
            refund_request_id="rr-3",
            idempotency_key="idem-rr-3",
            user_id=user.id,
            order_id="ord-repo-3",
            reason_code="fraud",
            simulation_scenario_id="delivered-happy",
            status="pending_manual_review",
            status_reason="manual_review_required",
            escalation_status="queued",
            escalation_queue_name="refund-risk-review",
            escalation_sla_deadline_at=datetime.now(UTC) + timedelta(hours=2),
            escalation_payload_json="{}",
        )

        invalid = repo.transition_escalation_status(
            refund_request_id=created.refund_request_id,
            to_status="resolved",
            actor_admin_user_id=user.id,
        )
        assert invalid is None

        in_review = repo.transition_escalation_status(
            refund_request_id=created.refund_request_id,
            to_status="in_review",
            actor_admin_user_id=user.id,
        )
        assert in_review is not None
        assert in_review.escalation_status == "in_review"
        assert in_review.status == "pending_manual_review"
        assert in_review.claimed_by_admin_user_id == user.id
        assert in_review.claimed_at is not None

        resolved = repo.transition_escalation_status(
            refund_request_id=created.refund_request_id,
            to_status="resolved",
            actor_admin_user_id=user.id,
            reviewer_note="Reviewed and approved",
        )
        assert resolved is not None
        assert resolved.escalation_status == "resolved"
        assert resolved.status == "resolved"
        assert resolved.status_reason == "manual_review_resolved"
        assert resolved.decided_by_admin_user_id == user.id
        assert resolved.decided_at is not None
        assert resolved.reviewer_note == "Reviewed and approved"

        no_more_transitions = repo.transition_escalation_status(
            refund_request_id=created.refund_request_id,
            to_status="rejected",
            actor_admin_user_id=user.id,
        )
        assert no_more_transitions is None
    finally:
        session.close()
