from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ForbiddenError
from app.core.security import hash_password
from app.db.base import Base
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.services.account_order_service import AccountOrderService


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return local_session()


def test_guest_cannot_access_account_profile() -> None:
    session = build_session()
    try:
        user_repo = UserRepository(session)
        guest = user_repo.create_guest()

        service = AccountOrderService(OrderRepository(session), user_repo)

        try:
            service.get_account_me(guest)
            assert False, "Expected ForbiddenError"
        except ForbiddenError:
            assert True
    finally:
        session.close()


def test_user_cannot_access_foreign_order() -> None:
    session = build_session()
    try:
        user_repo = UserRepository(session)
        first_user = user_repo.create_registered(email="one@example.com", password_hash="hash")
        second_user = user_repo.create_registered(email="two@example.com", password_hash="hash")

        order_repo = OrderRepository(session)
        order_repo.create(order_id="ord-foreign", user_id=first_user.id)

        service = AccountOrderService(order_repo, user_repo)

        try:
            service.get_order(user=second_user, order_id="ord-foreign")
            assert False, "Expected ForbiddenError"
        except ForbiddenError:
            assert True
    finally:
        session.close()


def test_timeline_progresses_to_delivered_for_old_orders() -> None:
    session = build_session()
    try:
        user_repo = UserRepository(session)
        user = user_repo.create_registered(email="timeline@example.com", password_hash="hash")

        order_repo = OrderRepository(session)
        order = order_repo.create(order_id="ord-old", user_id=user.id)
        order.created_at = datetime.now(UTC) - timedelta(hours=2)
        order.updated_at = order.created_at
        session.commit()

        service = AccountOrderService(order_repo, user_repo)
        timeline = service.get_order_timeline_sim(user=user, order_id="ord-old", scenario_id="default")

        assert timeline.events[-1].event == "delivered"
        assert all(event.event != "status_snapshot" for event in timeline.events)
    finally:
        session.close()


def test_account_profile_includes_demo_card() -> None:
    session = build_session()
    try:
        user_repo = UserRepository(session)
        user = user_repo.create_registered(email="profile@example.com", password_hash="hash")

        service = AccountOrderService(OrderRepository(session), user_repo)
        profile = service.get_account_me(user)

        assert profile.demo_card_last4 is not None
        assert len(profile.demo_card_last4) == 4
    finally:
        session.close()


def test_reveal_demo_card_requires_valid_password() -> None:
    session = build_session()
    try:
        user_repo = UserRepository(session)
        user = user_repo.create_registered(email="secure@example.com", password_hash=hash_password("secret123"))

        service = AccountOrderService(OrderRepository(session), user_repo)
        revealed = service.reveal_demo_card(user=user, password="secret123")

        assert len(revealed.demo_card_number) == 16
    finally:
        session.close()
