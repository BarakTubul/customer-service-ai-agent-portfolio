from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_order_id(self, order_id: str) -> Order | None:
        stmt = select(Order).where(Order.order_id == order_id)
        return self.db.scalar(stmt)

    def create(
        self,
        *,
        order_id: str,
        user_id: int,
        status: str = "confirmed",
        status_label: str = "Confirmed",
    ) -> Order:
        order = Order(order_id=order_id, user_id=user_id, status=status, status_label=status_label)
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order
