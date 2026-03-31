from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ForbiddenError
from app.db.base import Base
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.services.refund_service import RefundService
from app.schemas.refund import RefundCreateRequest, RefundEligibilityCheckRequest


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


def test_eligibility_ineligible_for_expired_window() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-r-1", user_id=user.id)

        service = RefundService(order_repository=order_repo, refund_repository=RefundRepository(session))
        response = service.check_eligibility(
            user=user,
            payload=RefundEligibilityCheckRequest(
                order_id="ord-r-1",
                reason_code="late_delivery",
                simulation_scenario_id="expired-window",
            ),
        )

        assert response.eligible is False
        assert "refund_window_expired" in response.decision_reason_codes
    finally:
        session.close()


def test_create_request_idempotent_replay() -> None:
    session = build_session()
    try:
        user = _create_user(session)
        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-r-2", user_id=user.id)
        service = RefundService(order_repository=order_repo, refund_repository=RefundRepository(session))

        payload = RefundCreateRequest(order_id="ord-r-2", reason_code="missing_item", simulation_scenario_id="default")
        first = service.create_request(user=user, payload=payload, idempotency_key="idem-1")
        second = service.create_request(user=user, payload=payload, idempotency_key="idem-1")

        assert first.refund_request_id == second.refund_request_id
        assert first.idempotent_replay is False
        assert second.idempotent_replay is True
    finally:
        session.close()


def test_guest_cannot_submit_refund() -> None:
    session = build_session()
    try:
        guest = _create_user(session, is_guest=True)
        owner = _create_user(session)
        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-r-3", user_id=owner.id)
        service = RefundService(order_repository=order_repo, refund_repository=RefundRepository(session))

        try:
            service.check_eligibility(
                user=guest,
                payload=RefundEligibilityCheckRequest(
                    order_id="ord-r-3",
                    reason_code="late_delivery",
                    simulation_scenario_id="default",
                ),
            )
            assert False, "Expected ForbiddenError"
        except ForbiddenError:
            assert True
    finally:
        session.close()
