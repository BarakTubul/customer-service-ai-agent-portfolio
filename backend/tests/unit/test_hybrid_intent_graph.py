from __future__ import annotations

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import IntentClassification


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls = 0

    def classify_intent(self, *, message_text: str) -> IntentClassification:
        self.calls += 1
        return IntentClassification(intent="general_support", confidence=0.77, reason="fake_llm")

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


def test_rule_path_skips_llm() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.75)

    result = graph.run(message_text="Where is my order now?")

    assert result["intent"] == "order_status"
    assert result["used_llm"] is False
    assert provider.calls == 0


def test_greeting_path_skips_llm() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.75)

    result = graph.run(message_text="hi")

    assert result["used_llm"] is False
    assert result["intent"] == "general_support"
    assert result["reason"] == "rule_greeting_smalltalk"
    assert provider.calls == 0


def test_refund_rule_path_skips_llm() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.75)

    result = graph.run(message_text="I want a refund for my order")

    assert result["intent"] == "refund_policy"
    assert result["used_llm"] is False
    assert provider.calls == 0


def test_high_threshold_forces_llm_even_for_rule_match() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.95)

    result = graph.run(message_text="Where is my order now?")

    assert result["used_llm"] is True
    assert provider.calls == 1
