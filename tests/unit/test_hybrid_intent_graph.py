from __future__ import annotations

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import IntentClassification


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls = 0

    def classify_intent(self, *, message_text: str) -> IntentClassification:
        self.calls += 1
        return IntentClassification(intent="general_support", confidence=0.77, reason="fake_llm")

    def synthesize_faq_answer(self, *, question: str, base_answer: str, source_label: str) -> str:
        return base_answer


def test_rule_path_skips_llm() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.75)

    result = graph.run(message_text="Where is my order now?")

    assert result["intent"] == "order_status"
    assert result["used_llm"] is False
    assert provider.calls == 0


def test_low_confidence_path_uses_llm() -> None:
    provider = FakeLLMProvider()
    graph = HybridIntentGraph(llm_provider=provider, rule_confidence_threshold=0.75)

    result = graph.run(message_text="hi")

    assert result["used_llm"] is True
    assert result["intent"] == "general_support"
    assert provider.calls == 1
