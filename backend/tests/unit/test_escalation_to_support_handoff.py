from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import IntentClassification
from app.db.base import Base
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.faq_repository import FAQRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.support_repository import SupportRepository
from app.services.intent_faq_service import IntentFAQService


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


class FakeLLMProvider:
    def __init__(self) -> None:
        self.synthesis_calls = 0

    def classify_intent(self, *, message_text: str) -> IntentClassification:
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


def build_session() -> Session:
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return SessionLocal()


def test_escalation_intake_creates_support_conversation() -> None:
    """Test that escalation with order ID creates a support conversation."""
    session = build_session()
    try:
        from app.models.support_conversation import SupportConversation
        
        provider = FakeLLMProvider()
        support_repo = SupportRepository(session)
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
            refund_repository=RefundRepository(session),
            support_repository=support_repo,
        )

        user = User(is_guest=False, is_active=True, is_verified=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        response = service.search_faq(
            user=user,
            session_id="sess-escalation-support",
            query_text="Order ord_12345 arrived damaged and I need a refund",
            intent="general_support",
        )

        assert response.answer.source_id == "support-escalation"
        assert "support/live" in response.answer.text.lower()
        assert "Reference ID:" in response.answer.text

        # Verify conversation was created
        support_convos = session.query(SupportConversation).filter_by(customer_user_id=user.id).all()
        assert len(support_convos) >= 1
        assert support_convos[0].customer_user_id == user.id
        assert support_convos[0].status == "open"
        assert support_convos[0].priority == "high"
    finally:
        session.close()


def test_escalation_intake_reuses_active_conversation() -> None:
    """Test that escalation reuses an existing active conversation."""
    session = build_session()
    try:
        provider = FakeLLMProvider()
        support_repo = SupportRepository(session)

        user = User(is_guest=False, is_active=True, is_verified=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        # Pre-create an active conversation
        existing_conv = support_repo.create_conversation(
            conversation_id="sc_existing",
            customer_user_id=user.id,
            source_session_id="sess-old",
            priority="normal",
            escalation_reason_code="previous_issue",
            escalation_reference_id=None,
        )

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
            refund_repository=RefundRepository(session),
            support_repository=support_repo,
        )

        response = service.search_faq(
            user=user,
            session_id="sess-new-escalation",
            query_text="Order ord_99999 is missing",
            intent="general_support",
        )

        assert "support/live/sc_existing" in response.answer.text

    finally:
        session.close()


def test_escalation_intake_guest_user_no_conversation() -> None:
    """Test that guest users cannot create support conversations even during escalation."""
    session = build_session()
    try:
        from app.models.support_conversation import SupportConversation

        provider = FakeLLMProvider()
        support_repo = SupportRepository(session)
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
            refund_repository=RefundRepository(session),
            support_repository=support_repo,
        )

        guest_user = User(is_guest=True, is_active=True, is_verified=False)
        session.add(guest_user)
        session.commit()
        session.refresh(guest_user)

        # Use an escalation-style query with order ID
        response = service.search_faq(
            user=guest_user,
            session_id="sess-guest-escalation",
            query_text="Order ord_guest arrived broken and I need refund",
            intent="general_support",
        )

        # Verify no conversation was created for guest, even though escalation occurred
        support_convos = session.query(SupportConversation).filter_by(customer_user_id=guest_user.id).all()
        assert len(support_convos) == 0

    finally:
        session.close()
