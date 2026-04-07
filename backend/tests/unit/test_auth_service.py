from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return local_session()


def test_create_guest_sets_is_guest_true() -> None:
    session = build_session()
    try:
        service = AuthService(UserRepository(session))
        response = service.create_guest()

        user = session.get(User, response.guest_id)
        assert user is not None
        assert user.is_guest is True
    finally:
        session.close()


def test_convert_guest_to_registered_flips_is_guest() -> None:
    session = build_session()
    try:
        service = AuthService(UserRepository(session))
        guest = service.create_guest()
        guest_user = session.get(User, guest.guest_id)
        assert guest_user is not None

        converted = service.convert_guest_to_registered(
            guest_user=guest_user,
            email="guest@example.com",
            password="strong-password",
        )

        user = session.get(User, converted.user_id)
        assert user is not None
        assert user.is_guest is False
        assert user.email == "guest@example.com"
        assert user.demo_card_number is not None
    finally:
        session.close()


def test_register_assigns_demo_card() -> None:
    session = build_session()
    try:
        service = AuthService(UserRepository(session))
        token = service.register(email="new-user@example.com", password="strong-password")

        user = session.get(User, token.user_id)
        assert user is not None
        assert user.demo_card_number is not None
        assert len(user.demo_card_number) == 16
    finally:
        session.close()


def test_login_backfills_demo_card_for_existing_registered_user() -> None:
    session = build_session()
    try:
        service = AuthService(UserRepository(session))
        _ = service.register(email="legacy@example.com", password="strong-password")

        user = session.query(User).filter(User.email == "legacy@example.com").one()
        user.demo_card_number = None
        session.add(user)
        session.commit()

        _ = service.login(email="legacy@example.com", password="strong-password")

        refreshed = session.get(User, user.id)
        assert refreshed is not None
        assert refreshed.demo_card_number is not None
    finally:
        session.close()


def test_register_marks_admin_from_configured_email() -> None:
    session = build_session()
    try:
        service = AuthService(UserRepository(session))
        token = service.register(email="admin@example.com", password="strong-password")

        user = session.get(User, token.user_id)
        assert user is not None
        assert user.is_admin is True
    finally:
        session.close()
