from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntentResolveRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    message_text: str = Field(min_length=1, max_length=4000)
    locale: str = "en-US"


class IntentResolveResponse(BaseModel):
    intent: str
    confidence: float
    requires_clarification: bool
    clarification_question: str | None
    route: str
    trace_id: str


class FAQSearchRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    query_text: str = Field(min_length=1, max_length=4000)
    intent: str = Field(min_length=1, max_length=128)
    locale: str = "en-US"


class FAQAnswer(BaseModel):
    text: str
    confidence: float
    source_label: str
    source_id: str
    policy_version: str


class FAQSearchResponse(BaseModel):
    answer: FAQAnswer


class ContextMessage(BaseModel):
    role: str
    text: str
    timestamp: datetime


class ConversationContextResponse(BaseModel):
    session_id: str
    summary: str
    recent_messages: list[ContextMessage]


class EscalationCheckRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    intent: str
    confidence: float
    reason: str


class EscalationCheckResponse(BaseModel):
    should_escalate: bool
    escalation_reason_code: str | None
