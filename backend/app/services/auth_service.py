from __future__ import annotations

from datetime import date

from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.settings import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import GuestResponse, TokenResponse


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository
        self.settings = get_settings()

    def create_guest(self) -> GuestResponse:
        guest = self.user_repository.create_guest()
        token = create_access_token(str(guest.id), is_guest=True)
        return GuestResponse(access_token=token, guest_id=guest.id)

    def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        date_of_birth: date,
        address: str,
    ) -> TokenResponse:
        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        user = self.user_repository.create_registered(
            email=email,
            password_hash=hash_password(password),
            is_admin=email.lower() in self.settings.admin_emails,
            full_name=full_name,
            date_of_birth=date_of_birth,
            address=address,
        )
        user = self.user_repository.ensure_demo_card(user)
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

        if not user.is_guest:
            user = self.user_repository.ensure_demo_card(user)
            user = self.user_repository.sync_admin_flag_for_email(
                user=user,
                admin_emails=self.settings.admin_emails,
            )

        token = create_access_token(str(user.id), is_guest=user.is_guest)
        return TokenResponse(access_token=token, user_id=user.id, is_guest=user.is_guest)

    def convert_guest_to_registered(
        self,
        *,
        guest_user: User,
        email: str,
        password: str,
        full_name: str | None = None,
        date_of_birth: date | None = None,
        address: str | None = None,
    ) -> TokenResponse:
        if not guest_user.is_guest:
            raise ConflictError("User is already registered")

        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        guest_user.email = email
        guest_user.password_hash = hash_password(password)
        guest_user.is_guest = False
        guest_user.is_admin = email.lower() in self.settings.admin_emails
        guest_user.is_verified = True
        if full_name is not None:
            guest_user.full_name = full_name
        if date_of_birth is not None:
            guest_user.date_of_birth = date_of_birth
        if address is not None:
            guest_user.address = address
        user = self.user_repository.update(guest_user)
        user = self.user_repository.ensure_demo_card(user)

        token = create_access_token(str(user.id), is_guest=False)
        return TokenResponse(access_token=token, user_id=user.id, is_guest=False)
