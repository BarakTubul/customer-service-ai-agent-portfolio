from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.services.account_order_service import AccountOrderService
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(user_repository: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repository)


def get_order_repository(db: Session = Depends(get_db)) -> OrderRepository:
    return OrderRepository(db)


def get_account_order_service(
    order_repository: OrderRepository = Depends(get_order_repository),
) -> AccountOrderService:
    return AccountOrderService(order_repository)


def _extract_token_from_request(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str:
    if credentials is not None:
        return credentials.credentials

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    raise UnauthorizedError("Missing authentication token")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    token = _extract_token_from_request(request, credentials)
    payload = decode_access_token(token)

    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid token subject")

    user = user_repository.get_by_id(int(subject))
    if user is None:
        raise UnauthorizedError("User not found")
    return user


def get_current_guest_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_guest:
        raise UnauthorizedError("Guest account required")
    return current_user
