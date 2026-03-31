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

    def classify_intent(self, *, message_text: str) -> IntentClassification:
        return IntentClassification(intent="general_support", confidence=0.8, reason="fake")

    def synthesize_faq_answer(self, *, question: str, base_answer: str, source_label: str) -> str:
        self.synthesis_calls += 1
        return f"LLM: {base_answer}"


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
        assert provider.synthesis_calls == 1
    finally:
        session.close()
