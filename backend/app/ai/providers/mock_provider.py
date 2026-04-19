from __future__ import annotations

from app.ai.providers.base import IntentClassification


class MockLLMProvider:
    """Deterministic provider used for tests and local fallback."""

    def classify_intent(
        self,
        *,
        message_text: str,
        conversation_context: str | None = None,
    ) -> IntentClassification:
        normalized = message_text.lower()
        if "refund" in normalized:
            return IntentClassification(intent="refund_policy", confidence=0.88, reason="mock_refund_keyword")
        if "order" in normalized or "delivery" in normalized:
            return IntentClassification(intent="order_status", confidence=0.83, reason="mock_order_keyword")
        if "verify" in normalized:
            return IntentClassification(intent="account_verification", confidence=0.8, reason="mock_verify_keyword")
        return IntentClassification(intent="general_support", confidence=0.55, reason="mock_default")

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
