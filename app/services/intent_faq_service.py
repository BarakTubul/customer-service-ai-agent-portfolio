from __future__ import annotations

import hashlib

from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.faq_repository import FAQRepository
from app.schemas.intent_faq import (
    ConversationContextResponse,
    ContextMessage,
    EscalationCheckResponse,
    FAQAnswer,
    FAQSearchResponse,
    IntentResolveResponse,
)


class IntentFAQService:
    def __init__(
        self,
        faq_repository: FAQRepository,
        conversation_repository: ConversationRepository,
    ) -> None:
        self.faq_repository = faq_repository
        self.conversation_repository = conversation_repository

    def resolve_intent(self, *, user: User, session_id: str, message_text: str, message_id: str) -> IntentResolveResponse:
        normalized = message_text.lower()
        intent = "general_support"
        confidence = 0.58
        requires_clarification = False
        clarification_question = None
        route = "faq_answer"

        if any(token in normalized for token in ["refund", "money back", "reimburse"]):
            intent = "refund_policy"
            confidence = 0.9
        elif any(token in normalized for token in ["where is my order", "order", "delivery"]):
            intent = "order_status"
            confidence = 0.86
        elif any(token in normalized for token in ["verify", "verification", "verified"]):
            intent = "account_verification"
            confidence = 0.84
        elif len(normalized.split()) < 3:
            requires_clarification = True
            clarification_question = "Are you asking about refunds, orders, or account verification?"
            route = "clarify"
            confidence = 0.4

        trace_id = hashlib.sha256(f"{session_id}:{message_id}:{intent}".encode("utf-8")).hexdigest()[:16]
        self.conversation_repository.add_message(
            session_id=session_id,
            user_id=user.id,
            role="user",
            text=message_text,
        )

        return IntentResolveResponse(
            intent=intent,
            confidence=confidence,
            requires_clarification=requires_clarification,
            clarification_question=clarification_question,
            route=route,
            trace_id=trace_id,
        )

    def search_faq(self, *, user: User, session_id: str, query_text: str, intent: str) -> FAQSearchResponse:
        result = self.faq_repository.find_best_match(intent=intent, query_text=query_text)
        if result is None:
            answer = FAQAnswer(
                text="I could not find a reliable answer right now. Please try rephrasing or ask for human support.",
                confidence=0.2,
                source_label="Fallback",
                source_id="fallback",
                policy_version="n/a",
            )
        else:
            entry, confidence = result
            answer = FAQAnswer(
                text=entry.answer,
                confidence=confidence,
                source_label=entry.source_label,
                source_id=entry.source_id,
                policy_version=entry.policy_version,
            )

        self.conversation_repository.add_message(
            session_id=session_id,
            user_id=user.id,
            role="assistant",
            text=answer.text,
        )
        return FAQSearchResponse(answer=answer)

    def get_conversation_context(self, *, session_id: str, include_last_n: int = 6) -> ConversationContextResponse:
        messages = self.conversation_repository.list_recent_messages(session_id=session_id, limit=include_last_n)
        rendered = [
            ContextMessage(role=item.role, text=item.text, timestamp=item.created_at)
            for item in messages
        ]
        summary = "No conversation yet" if not rendered else f"{len(rendered)} recent message(s)"
        return ConversationContextResponse(session_id=session_id, summary=summary, recent_messages=rendered)

    def escalation_check(self, *, intent: str, confidence: float, reason: str) -> EscalationCheckResponse:
        high_risk_intents = {"billing_dispute", "account_lockout", "legal_threat", "safety_concern"}
        if intent in high_risk_intents:
            return EscalationCheckResponse(should_escalate=True, escalation_reason_code="high_risk_intent")
        if confidence < 0.6:
            return EscalationCheckResponse(should_escalate=True, escalation_reason_code="low_confidence")
        if "human" in reason.lower() or "agent" in reason.lower():
            return EscalationCheckResponse(should_escalate=True, escalation_reason_code="user_requested_human")
        return EscalationCheckResponse(should_escalate=False, escalation_reason_code=None)
