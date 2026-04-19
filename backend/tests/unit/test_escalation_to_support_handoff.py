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
        return base_answer


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return SessionLocal()


def _build_service(session: Session) -> IntentFAQService:
    provider = FakeLLMProvider()
    return IntentFAQService(
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


def test_human_support_request_returns_regular_chat_handoff() -> None:
    session = build_session()
    try:
        service = _build_service(session)

        user = User(is_guest=False, is_active=True, is_verified=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-human-handoff",
            query_text="I need human support",
            intent="general_support",
        )

        assert response.retrieval_mode == "handoff_ack"
        assert response.answer.source_id == "support-escalation"
        assert "support chat" in response.answer.text.lower()
        assert "/support" in response.answer.text.lower()
        assert response.citations == []
    finally:
        session.close()


def test_escalation_followup_confirmation_returns_regular_chat_handoff() -> None:
    session = build_session()
    try:
        service = _build_service(session)

        user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)

        # Seed a previous assistant handoff prompt so confirmation-style follow-up is recognized.
        service.conversation_repository.add_message(
            session_id="sess-followup-handoff",
            user_id=user.id,
            role="assistant",
            text="For human support, please open a regular support chat at /support so an admin can assist you directly.",
        )

        response = service.search_faq(
            user=user,
            session_id="sess-followup-handoff",
            query_text="ok yes please",
            intent="general_support",
        )

        assert response.retrieval_mode == "handoff_ack"
        assert "support chat" in response.answer.text.lower()
        assert "/support" in response.answer.text.lower()
    finally:
        session.close()
