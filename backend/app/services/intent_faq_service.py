from __future__ import annotations

import hashlib
import re

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import LLMProvider
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.faq_repository import FAQRepository
from app.schemas.intent_faq import (
    ConversationContextResponse,
    ContextMessage,
    EscalationCheckResponse,
    FAQAnswer,
    FAQCitation,
    FAQSearchResponse,
    IntentResolveResponse,
)


class IntentFAQService:
    ACTION_INTENTS: set[str] = {"order_placement", "refund_request"}
    INTENT_CTA_LINKS: dict[str, tuple[str, str]] = {
        "refund_policy": ("Refund Page", "/refund"),
        "refund_request": ("Refund Page", "/refund"),
        "order_status": ("My Orders", "/orders"),
        "order_placement": ("Order Page", "/order"),
        "account_verification": ("Dashboard", "/dashboard"),
        "general_support": ("Dashboard", "/dashboard"),
    }

    def __init__(
        self,
        faq_repository: FAQRepository,
        conversation_repository: ConversationRepository,
        llm_provider: LLMProvider,
        intent_graph: HybridIntentGraph,
        escalation_confidence_threshold: float,
        llm_faq_synthesis_enabled: bool,
    ) -> None:
        self.faq_repository = faq_repository
        self.conversation_repository = conversation_repository
        self.llm_provider = llm_provider
        self.intent_graph = intent_graph
        self.escalation_confidence_threshold = escalation_confidence_threshold
        self.llm_faq_synthesis_enabled = llm_faq_synthesis_enabled

    def _append_intent_cta(self, *, text: str, intent: str) -> str:
        link = self.INTENT_CTA_LINKS.get(intent)
        if link is None:
            return text

        link_label, link_path = link
        if link_path in text:
            return text

        cleaned = text.strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        return f"{cleaned} See [{link_label}]({link_path}).".strip()

    @staticmethod
    def _is_how_to_question(query_text: str) -> bool:
        normalized = query_text.strip().lower()
        return bool(
            re.search(
                r"\b(how\s+do\s+i|how\s+can\s+i|how\s+to|where\s+can\s+i|where\s+do\s+i|i\s+want\s+to|need\s+to)\b",
                normalized,
            )
        )

    def _build_action_only_reply(self, *, intent: str) -> str | None:
        link = self.INTENT_CTA_LINKS.get(intent)
        if link is None:
            return None
        link_label, link_path = link
        return f"Go to the [{link_label}]({link_path}) to do that."

    def resolve_intent(self, *, user: User, session_id: str, message_text: str, message_id: str) -> IntentResolveResponse:
        state = self.intent_graph.run(message_text=message_text)
        intent = state["intent"]
        confidence = state["confidence"]
        reason = state.get("reason", "")

        if reason == "rule_greeting_smalltalk":
            trace_id = hashlib.sha256(f"{session_id}:{message_id}:{intent}".encode("utf-8")).hexdigest()[:16]
            self.conversation_repository.add_message(
                session_id=session_id,
                user_id=user.id,
                role="user",
                text=message_text,
            )
            return IntentResolveResponse(
                intent="general_support",
                confidence=confidence,
                requires_clarification=True,
                clarification_question=(
                    "Hi! I can help with refunds, order status, and account verification. "
                    "What do you need help with?"
                ),
                route="clarify",
                trace_id=trace_id,
            )

        requires_clarification = confidence < self.escalation_confidence_threshold
        clarification_question = None
        route = "faq_answer"
        if requires_clarification:
            clarification_question = self._append_intent_cta(
                text="Are you asking about refunds, orders, or account verification?",
                intent=intent,
            )
            route = "clarify"

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
        retrieved = self.faq_repository.retrieve_chunks(intent=intent, query_text=query_text, top_k=3)

        if not retrieved:
            answer = FAQAnswer(
                text="I could not find a reliable answer right now. Please try rephrasing or ask for human support.",
                confidence=0.2,
                source_label="Fallback",
                source_id="fallback",
                policy_version="n/a",
            )
            citations: list[FAQCitation] = []
        else:
            top_chunk, confidence = retrieved[0]
            action_only_reply = None
            if intent in self.ACTION_INTENTS and self._is_how_to_question(query_text):
                action_only_reply = self._build_action_only_reply(intent=intent)

            if action_only_reply is not None:
                response_text = action_only_reply
            else:
                # Keep seeded answers concise: use the top chunk for the response body.
                base_answer = top_chunk.text
                response_text = base_answer
                if self.llm_faq_synthesis_enabled:
                    response_text = self.llm_provider.synthesize_faq_answer(
                        question=query_text,
                        base_answer=base_answer,
                        source_label=top_chunk.source_label,
                    )

                response_text = self._append_intent_cta(text=response_text, intent=intent)

            answer = FAQAnswer(
                text=response_text,
                confidence=confidence,
                source_label=top_chunk.source_label,
                source_id=top_chunk.source_id,
                policy_version=top_chunk.policy_version,
            )
            citations = [
                FAQCitation(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    source_label=chunk.source_label,
                    policy_version=chunk.policy_version,
                    snippet=chunk.text,
                    score=score,
                )
                for chunk, score in retrieved
            ]

        self.conversation_repository.add_message(
            session_id=session_id,
            user_id=user.id,
            role="assistant",
            text=answer.text,
        )
        return FAQSearchResponse(answer=answer, citations=citations, retrieval_mode="rag_seeded")

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
        if confidence < self.escalation_confidence_threshold:
            return EscalationCheckResponse(should_escalate=True, escalation_reason_code="low_confidence")
        if "human" in reason.lower() or "agent" in reason.lower():
            return EscalationCheckResponse(should_escalate=True, escalation_reason_code="user_requested_human")
        return EscalationCheckResponse(should_escalate=False, escalation_reason_code=None)
