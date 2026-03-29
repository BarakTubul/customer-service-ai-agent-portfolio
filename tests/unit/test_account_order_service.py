from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ForbiddenError
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

        service = AccountOrderService(OrderRepository(session))

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

        service = AccountOrderService(order_repo)

        try:
            service.get_order(user=second_user, order_id="ord-foreign")
            assert False, "Expected ForbiddenError"
        except ForbiddenError:
            assert True
    finally:
        session.close()
