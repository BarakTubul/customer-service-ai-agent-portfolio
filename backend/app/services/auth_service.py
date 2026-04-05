from __future__ import annotations

from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import GuestResponse, TokenResponse


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def create_guest(self) -> GuestResponse:
        guest = self.user_repository.create_guest()
        token = create_access_token(str(guest.id), is_guest=True)
        return GuestResponse(access_token=token, guest_id=guest.id)

    def register(self, *, email: str, password: str) -> TokenResponse:
        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        user = self.user_repository.create_registered(
            email=email,
            password_hash=hash_password(password),
        )
        token = create_access_token(str(user.id), is_guest=False)
        return TokenResponse(access_token=token, user_id=user.id, is_guest=False)

    def login(self, *, email: str, password: str) -> TokenResponse:
        user = self.user_repository.get_by_email(email)
        if user is None or user.password_hash is None:
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise ForbiddenError("Account is not active")

        token = create_access_token(str(user.id), is_guest=user.is_guest)
        return TokenResponse(access_token=token, user_id=user.id, is_guest=user.is_guest)

    def convert_guest_to_registered(self, *, guest_user: User, email: str, password: str) -> TokenResponse:
        if not guest_user.is_guest:
            raise ConflictError("User is already registered")

        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        guest_user.email = email
        guest_user.password_hash = hash_password(password)
        guest_user.is_guest = False
        guest_user.is_verified = True
        user = self.user_repository.update(guest_user)

        token = create_access_token(str(user.id), is_guest=False)
        return TokenResponse(access_token=token, user_id=user.id, is_guest=False)
