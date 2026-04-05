from __future__ import annotations

import hashlib
from datetime import UTC, timedelta

from app.core.errors import ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.account import (
    AccountMeResponse,
    OrderResponse,
    OrderTimelineEvent,
    OrderTimelineResponse,
    SessionStateResponse,
)


class AccountOrderService:
    def __init__(self, order_repository: OrderRepository) -> None:
        self.order_repository = order_repository

    def get_session_state(self, user: User) -> SessionStateResponse:
        return SessionStateResponse(
            authenticated=True,
            user_id=user.id,
            is_guest=user.is_guest,
            is_active=user.is_active,
        )

    def get_account_me(self, user: User) -> AccountMeResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users cannot access account profile")

        status = "verified_active" if user.is_verified and user.is_active else "restricted"
        return AccountMeResponse(
            user_id=user.id,
            email_masked=self._mask_email(user.email),
            account_status=status,
        )

    def get_order(self, *, user: User, order_id: str) -> OrderResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users cannot access orders")

        order = self.order_repository.get_by_order_id(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if order.user_id != user.id:
            raise ForbiddenError("Order does not belong to current user")

        return OrderResponse(
            order_id=order.order_id,
            status=order.status,
            status_label=order.status_label,
            updated_at=order.updated_at,
            eta_from=order.eta_from,
            eta_to=order.eta_to,
        )

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

        base_time = order.updated_at.astimezone(UTC)
        events = [
            OrderTimelineEvent(event="accepted", timestamp=base_time - timedelta(minutes=20 + offset), source="sim"),
            OrderTimelineEvent(event="preparing", timestamp=base_time - timedelta(minutes=12 + offset), source="sim"),
            OrderTimelineEvent(event="pickup", timestamp=base_time - timedelta(minutes=6 + offset), source="sim"),
            OrderTimelineEvent(event="in_transit", timestamp=base_time - timedelta(minutes=2 + offset), source="sim"),
            OrderTimelineEvent(event="status_snapshot", timestamp=base_time, source="sim"),
        ]
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
