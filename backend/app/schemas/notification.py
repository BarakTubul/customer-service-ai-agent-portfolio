from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    notification_id: str
    order_id: str
    status: str
    title: str
    message: str
    created_at: datetime