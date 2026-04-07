from __future__ import annotations

from datetime import UTC

from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.account_order_service import AccountOrderService


_LAST_NOTIFIED_STATUSES: dict[int, dict[str, str]] = {}


class NotificationService:
    def __init__(self, account_order_service: AccountOrderService) -> None:
        self.account_order_service = account_order_service

    def get_live_notifications(self, user: User) -> list[NotificationResponse]:
        if user.is_guest:
            return []

        orders = self.account_order_service.list_orders(user)
        if not orders:
            return []

        seen_statuses = _LAST_NOTIFIED_STATUSES.setdefault(user.id, {})
        notifications: list[NotificationResponse] = []

        for order in orders:
            timeline = self.account_order_service.get_order_timeline_sim(
                user=user,
                order_id=order.order_id,
                scenario_id="default",
            )
            latest_event = timeline.events[-1] if timeline.events else None
            current_status = latest_event.event if latest_event else order.status
            if seen_statuses.get(order.order_id) == current_status:
                continue

            seen_statuses[order.order_id] = current_status
            event_time = latest_event.timestamp if latest_event else order.updated_at.astimezone(UTC)
            notifications.append(
                NotificationResponse(
                    notification_id=f"{order.order_id}:{current_status}",
                    order_id=order.order_id,
                    status=current_status,
                    title=self._build_title(current_status),
                    message=self._build_message(order.order_id, current_status),
                    created_at=event_time,
                )
            )

        notifications.sort(key=lambda item: item.created_at, reverse=True)
        return notifications

    @staticmethod
    def _build_title(status: str) -> str:
        if status == "delivered":
            return "Order delivered"
        if status == "arriving":
            return "Order arriving soon"
        return "Order updated"

    @staticmethod
    def _build_message(order_id: str, status: str) -> str:
        readable_status = status.replace("_", " ")
        if status == "delivered":
            return f"{order_id} has been delivered."
        if status == "arriving":
            return f"{order_id} is arriving now."
        return f"{order_id} is now {readable_status}."