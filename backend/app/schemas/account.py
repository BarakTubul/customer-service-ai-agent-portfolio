from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SessionStateResponse(BaseModel):
    authenticated: bool
    user_id: int
    is_guest: bool
    is_active: bool


class AccountMeResponse(BaseModel):
    user_id: int
    email_masked: str | None
    account_status: str


class OrderTimelineEvent(BaseModel):
    event: str
    timestamp: datetime
    source: str


class OrderResponse(BaseModel):
    order_id: str
    status: str
    status_label: str
    updated_at: datetime
    eta_from: datetime | None
    eta_to: datetime | None


class OrderTimelineResponse(BaseModel):
    order_id: str
    scenario_id: str
    events: list[OrderTimelineEvent]
