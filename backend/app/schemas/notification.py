from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    notification_id: str
    kind: str = "order"
    order_id: str | None = None
    target_path: str | None = None
    status: str
    title: str
    message: str
    created_at: datetime