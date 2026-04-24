from __future__ import annotations

from datetime import date
import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_guest(self) -> User:
        user = User(is_guest=True, is_admin=False, is_active=True, is_verified=False, balance_cents=100000)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def create_registered(
        self,
        *,
        email: str,
        password_hash: str,
        is_admin: bool = False,
        full_name: str | None = None,
        date_of_birth: date | None = None,
        address: str | None = None,
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            date_of_birth=date_of_birth,
            address=address,
            password_hash=password_hash,
            is_guest=False,
            is_admin=is_admin,
            is_active=True,
            is_verified=True,
            balance_cents=100000,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def try_debit_balance(self, *, user_id: int, amount_cents: int) -> tuple[bool, int]:
        user = self.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")
        if amount_cents <= 0:
            return True, user.balance_cents

        available_balance = user.balance_cents or 0
        if available_balance < amount_cents:
            return False, available_balance

        user.balance_cents = available_balance - amount_cents
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return True, user.balance_cents

    def credit_balance(self, *, user_id: int, amount_cents: int) -> int:
        user = self.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")
        if amount_cents <= 0:
            return user.balance_cents

        user.balance_cents = (user.balance_cents or 0) + amount_cents
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user.balance_cents

    def update(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def sync_admin_flag_for_email(self, *, user: User, admin_emails: set[str]) -> User:
        if not user.email:
            return user
        should_be_admin = user.email.lower() in admin_emails
        if user.is_admin == should_be_admin:
            return user
        user.is_admin = should_be_admin
        return self.update(user)

    def ensure_demo_card(self, user: User) -> User:
        if user.demo_card_number:
            return user

        card_number = self._build_demo_card_number(user.id)
        user.demo_card_number = card_number
        user.demo_card_assigned_at = datetime.now(UTC)
        return self.update(user)

    @staticmethod
    def _build_demo_card_number(user_id: int) -> str:
        seed = hashlib.sha256(f"demo-card:{user_id}".encode("utf-8")).hexdigest()
        body = "4" + "".join(str(int(char, 16) % 10) for char in seed[:14])
        checksum = UserRepository._luhn_check_digit(body)
        return f"{body}{checksum}"

    @staticmethod
    def _luhn_check_digit(number_without_check: str) -> int:
        digits = [int(ch) for ch in number_without_check]
        parity = (len(digits) + 1) % 2
        total = 0
        for idx, digit in enumerate(digits):
            value = digit
            if idx % 2 == parity:
                value *= 2
                if value > 9:
                    value -= 9
            total += value
        return (10 - (total % 10)) % 10
