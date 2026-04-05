from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_intent_faq_service
from app.models.user import User
from app.schemas.intent_faq import (
    ConversationContextResponse,
    EscalationCheckRequest,
    EscalationCheckResponse,
    FAQSearchRequest,
    FAQSearchResponse,
    IntentResolveRequest,
    IntentResolveResponse,
)
from app.services.intent_faq_service import IntentFAQService

router = APIRouter()


@router.post("/intent/resolve", response_model=IntentResolveResponse)
def resolve_intent(
    payload: IntentResolveRequest,
    current_user: User = Depends(get_current_user),
    intent_faq_service: IntentFAQService = Depends(get_intent_faq_service),
) -> IntentResolveResponse:
    return intent_faq_service.resolve_intent(
        user=current_user,
        session_id=payload.session_id,
        message_text=payload.message_text,
        message_id=payload.message_id,
    )


@router.post("/faq/search", response_model=FAQSearchResponse)
def faq_search(
    payload: FAQSearchRequest,
    current_user: User = Depends(get_current_user),
    intent_faq_service: IntentFAQService = Depends(get_intent_faq_service),
) -> FAQSearchResponse:
    return intent_faq_service.search_faq(
        user=current_user,
        session_id=payload.session_id,
        query_text=payload.query_text,
        intent=payload.intent,
    )


@router.get("/conversations/{session_id}/context", response_model=ConversationContextResponse)
def get_conversation_context(
    session_id: str,
    include_last_n: int = Query(default=6, ge=1, le=20),
    _: User = Depends(get_current_user),
    intent_faq_service: IntentFAQService = Depends(get_intent_faq_service),
) -> ConversationContextResponse:
    return intent_faq_service.get_conversation_context(
        session_id=session_id,
        include_last_n=include_last_n,
    )


@router.post("/fallback/escalation-check", response_model=EscalationCheckResponse)
def escalation_check(
    payload: EscalationCheckRequest,
    _: User = Depends(get_current_user),
    intent_faq_service: IntentFAQService = Depends(get_intent_faq_service),
) -> EscalationCheckResponse:
    return intent_faq_service.escalation_check(
        intent=payload.intent,
        confidence=payload.confidence,
        reason=payload.reason,
    )
