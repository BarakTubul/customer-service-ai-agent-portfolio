from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import IntentClassification
from app.db.base import Base
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.faq_repository import FAQRepository
from app.services.intent_faq_service import IntentFAQService


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


class FakeLLMProvider:
    def __init__(self) -> None:
        self.synthesis_calls = 0

    def classify_intent(
        self,
        *,
        message_text: str,
        conversation_context: str | None = None,
    ) -> IntentClassification:
        return IntentClassification(intent="general_support", confidence=0.8, reason="fake")

    def synthesize_faq_answer(
        self,
        *,
        question: str,
        base_answer: str,
        source_label: str,
        faq_context: str | None = None,
        conversation_context: str | None = None,
    ) -> str:
        self.synthesis_calls += 1
        return f"LLM: {base_answer}"


class LowConfidenceLLMProvider(FakeLLMProvider):
    def classify_intent(
        self,
        *,
        message_text: str,
        conversation_context: str | None = None,
    ) -> IntentClassification:
        return IntentClassification(intent="general_support", confidence=0.2, reason="low_confidence")


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return local_session()


def test_faq_synthesis_uses_llm_provider() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-llm",
            query_text="How long refund takes",
            intent="refund_policy",
        )

        assert response.answer.text.startswith("LLM:")
        assert "/refund" in response.answer.text
        assert provider.synthesis_calls == 1
    finally:
        session.close()


def test_faq_without_llm_synthesis_keeps_grounded_text() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=False,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-grounded",
            query_text="refund processing time",
            intent="refund_policy",
        )

        assert response.answer.text.startswith("LLM:") is False
        assert "/refund" in response.answer.text
        assert response.retrieval_mode == "rag_seeded"
        assert len(response.citations) >= 1
        assert provider.synthesis_calls == 0
    finally:
        session.close()


def test_order_status_faq_includes_orders_link() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=False,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-orders",
            query_text="How do I track my order",
            intent="order_status",
        )

        assert "(/orders)" in response.answer.text
        assert response.answer.text.startswith("LLM:") is False
    finally:
        session.close()


def test_account_verification_faq_includes_dashboard_link() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=False,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-dashboard",
            query_text="How do I verify my account",
            intent="account_verification",
        )

        assert "(/dashboard)" in response.answer.text
        assert response.answer.text.startswith("LLM:") is False
    finally:
        session.close()


def test_refund_request_faq_includes_refund_page_link() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=False,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-refund-request",
            query_text="Where can I ask for refund?",
            intent="refund_request",
        )

        assert "(/refund)" in response.answer.text
        assert response.answer.text.startswith("LLM:") is False
    finally:
        session.close()


def test_order_placement_faq_includes_order_page_link() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=False,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-order-placement",
            query_text="Where can I order food?",
            intent="order_placement",
        )

        assert "(/order)" in response.answer.text
        assert response.answer.text.startswith("LLM:") is False
    finally:
        session.close()


def test_action_how_to_question_returns_short_order_cta_only() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-action-order",
            query_text="I want to place an order, how do I do it?",
            intent="order_placement",
        )

        assert response.answer.text == "Go to the [Order Page](/order) to do that."
        assert provider.synthesis_calls == 0
    finally:
        session.close()


def test_action_how_to_question_returns_short_refund_cta_only() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-action-refund",
            query_text="Where can I ask for refund?",
            intent="refund_request",
        )

        assert response.answer.text == "Go to the [Refund Page](/refund) to do that."
        assert provider.synthesis_calls == 0
    finally:
        session.close()


def test_low_confidence_intent_requires_clarification() -> None:
    session = build_session()
    try:
        provider = LowConfidenceLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.95),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.resolve_intent(
            user=user,
            session_id="sess-clarify",
            message_text="hi",
            message_id="msg-clarify",
        )

        assert response.requires_clarification is True
        assert response.route == "clarify"
        assert response.clarification_question is not None
        assert "/dashboard" not in response.clarification_question
    finally:
        session.close()


def test_human_help_intent_returns_escalation_clarification() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.resolve_intent(
            user=user,
            session_id="sess-human-help",
            message_text="Can I speak with a human?",
            message_id="msg-human-help",
        )

        assert response.route == "clarify"
        assert response.requires_clarification is True
        assert response.clarification_question is not None
        assert "support chat" in response.clarification_question.lower()
    finally:
        session.close()


def test_human_support_request_in_search_returns_handoff_ack() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-escalation-intake",
            query_text="I need human support now",
            intent="order_status",
        )

        assert response.retrieval_mode == "handoff_ack"
        assert "support chat" in response.answer.text.lower()
        assert "/support" in response.answer.text.lower()
        assert response.citations == []
    finally:
        session.close()


def test_escalation_follow_up_confirmation_keeps_handoff_prompt() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        first = service.resolve_intent(
            user=user,
            session_id="sess-escalation-followup",
            message_text="Can I ask for human assistance?",
            message_id="msg-escalation-first",
        )
        assert first.route == "clarify"
        assert first.clarification_question is not None

        service.conversation_repository.add_message(
            session_id="sess-escalation-followup",
            user_id=user.id,
            role="assistant",
            text=first.clarification_question,
        )

        follow_up = service.resolve_intent(
            user=user,
            session_id="sess-escalation-followup",
            message_text="ok i need one please",
            message_id="msg-escalation-followup",
        )

        assert follow_up.route == "clarify"
        assert follow_up.clarification_question is not None
        assert "support chat" in follow_up.clarification_question.lower()
    finally:
        session.close()


def test_direct_human_request_uses_clarify_handoff() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.resolve_intent(
            user=user,
            session_id="sess-direct-human",
            message_text="I would like to speak to a human please",
            message_id="msg-direct-human",
        )

        assert response.route == "clarify"
        assert response.clarification_question is not None
        assert "support chat" in response.clarification_question.lower()
    finally:
        session.close()


def test_need_assistance_now_uses_clarify_handoff() -> None:
    session = build_session()
    try:
        provider = FakeLLMProvider()
        service = IntentFAQService(
            faq_repository=FAQRepository(),
            conversation_repository=ConversationRepository(session),
            llm_provider=provider,
            intent_graph=HybridIntentGraph(llm_provider=provider),
            escalation_confidence_threshold=0.6,
            llm_faq_synthesis_enabled=True,
            retrieval_top_k=10,
            max_context_chunks=5,
            max_context_chars=2200,
            min_chunk_score=0.10,
            relative_score_floor=0.60,
            synthesis_history_messages=6,
            synthesis_history_chars=1200,
        )

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.resolve_intent(
            user=user,
            session_id="sess-assistance-now",
            message_text="i need assistance now",
            message_id="msg-assistance-now",
        )

        assert response.route == "clarify"
        assert response.clarification_question is not None
        assert "support chat" in response.clarification_question.lower()
    finally:
        session.close()


