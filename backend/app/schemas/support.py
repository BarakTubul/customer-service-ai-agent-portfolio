from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SupportConversationCreateRequest(BaseModel):
    source_session_id: str | None = Field(default=None, min_length=1, max_length=128)
    escalation_reason_code: str | None = Field(default=None, min_length=1, max_length=64)
    escalation_reference_id: str | None = Field(default=None, min_length=1, max_length=64)
    priority: str = Field(default="normal", pattern="^(normal|high)$")


class SupportConversationResponse(BaseModel):
    conversation_id: str
    customer_user_id: int
    status: str
    priority: str
    assigned_admin_user_id: int | None
    source_session_id: str | None
    escalation_reason_code: str | None
    escalation_reference_id: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class SupportConversationListResponse(BaseModel):
    items: list[SupportConversationResponse]
    total: int


class SupportMessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class SupportMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    sender_user_id: int
    sender_role: str
    body: str
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


class SupportMessageListResponse(BaseModel):
    items: list[SupportMessageResponse]
    total: int
