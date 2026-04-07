from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import verify_password
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account import (
    AccountMeResponse,
    DemoCardRevealResponse,
    OrderResponse,
    OrderTimelineEvent,
    OrderTimelineResponse,
    SessionStateResponse,
)


class AccountOrderService:
    def __init__(self, order_repository: OrderRepository, user_repository: UserRepository) -> None:
        self.order_repository = order_repository
        self.user_repository = user_repository

    def get_session_state(self, user: User) -> SessionStateResponse:
        return SessionStateResponse(
            authenticated=True,
            user_id=user.id,
            is_guest=user.is_guest,
            is_admin=user.is_admin,
            is_active=user.is_active,
        )

    def get_account_me(self, user: User) -> AccountMeResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users cannot access account profile")

        user = self.user_repository.ensure_demo_card(user)

        status = "verified_active" if user.is_verified and user.is_active else "restricted"
        return AccountMeResponse(
            user_id=user.id,
            email_masked=self._mask_email(user.email),
            account_status=status,
            is_admin=user.is_admin,
            demo_card_last4=self._card_last4(user.demo_card_number),
        )

    def reveal_demo_card(self, *, user: User, password: str) -> DemoCardRevealResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users cannot access demo card")
        if not user.password_hash:
            raise ForbiddenError("Password is not configured for this account")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid password")

        user = self.user_repository.ensure_demo_card(user)
        if not user.demo_card_number:
            raise NotFoundError("Demo card not found")
        return DemoCardRevealResponse(demo_card_number=user.demo_card_number)

    def list_orders(self, user: User) -> list[OrderResponse]:
        if user.is_guest:
            return []

        orders = self.order_repository.list_by_user(user.id)
        return [
            self._build_order_response(order)
            for order in orders
        ]

    def get_order(self, *, user: User, order_id: str) -> OrderResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users cannot access orders")

        order = self.order_repository.get_by_order_id(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if order.user_id != user.id:
            raise ForbiddenError("Order does not belong to current user")

        return self._build_order_response(order)

    def _build_order_response(self, order) -> OrderResponse:
        eta_from, eta_to = self._resolve_eta_window(order)
        return OrderResponse(
            order_id=order.order_id,
            status=order.status,
            status_label=order.status_label,
            ordered_items_summary=order.ordered_items_summary,
            total_cents=order.total_cents or 0,
            created_at=order.created_at,
            updated_at=order.updated_at,
            eta_from=eta_from,
            eta_to=eta_to,
        )

    @staticmethod
    def _resolve_eta_window(order) -> tuple[datetime | None, datetime | None]:
        if order.eta_from and order.eta_to:
            return order.eta_from, order.eta_to

        now = datetime.now(UTC)
        eta_from = order.created_at.astimezone(UTC) + timedelta(seconds=35)
        eta_to = order.created_at.astimezone(UTC) + timedelta(seconds=50)

        if now > eta_to:
            eta_from = now + timedelta(seconds=10)
            eta_to = now + timedelta(seconds=20)

        return eta_from, eta_to

    def get_order_timeline_sim(
        self,
        *,
        user: User,
        order_id: str,
        scenario_id: str,
    ) -> OrderTimelineResponse:
        order = self.get_order(user=user, order_id=order_id)
        seed = hashlib.sha256(f"{order_id}:{scenario_id}".encode("utf-8")).hexdigest()
        offset = int(seed[:2], 16) % 5
        base_time = order.created_at.astimezone(UTC)
        now = datetime.now(UTC)
        simulated_now = max(now, base_time + timedelta(seconds=30 + offset))

        stage_definitions = [
            ("accepted", 2 + offset),
            ("preparing", 8 + offset),
            ("pickup", 18 + offset),
            ("in_transit", 30 + offset),
            ("arriving", 40 + offset),
            ("delivered", 45 + offset),
        ]

        events = [
            OrderTimelineEvent(event=event_name, timestamp=base_time + timedelta(seconds=seconds_after), source="sim")
            for event_name, seconds_after in stage_definitions
            if base_time + timedelta(seconds=seconds_after) <= simulated_now
        ]

        if not events:
            events = [OrderTimelineEvent(event="accepted", timestamp=base_time + timedelta(seconds=2 + offset), source="sim")]
        return OrderTimelineResponse(order_id=order.order_id, scenario_id=scenario_id, events=events)

    @staticmethod
    def _mask_email(email: str | None) -> str | None:
        if email is None:
            return None
        name, _, domain = email.partition("@")
        if not domain:
            return "***"
        if len(name) <= 2:
            masked_name = "*" * len(name)
        else:
            masked_name = f"{name[0]}***{name[-1]}"
        return f"{masked_name}@{domain}"

    @staticmethod
    def _card_last4(card_number: str | None) -> str | None:
        if not card_number:
            return None
        digits = "".join(ch for ch in card_number if ch.isdigit())
        if len(digits) < 4:
            return None
        return digits[-4:]
