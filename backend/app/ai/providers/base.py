from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IntentClassification:
    intent: str
    confidence: float
    reason: str


class LLMProvider(Protocol):
    def classify_intent(self, *, message_text: str) -> IntentClassification:
        ...

    def synthesize_faq_answer(
        self,
        *,
        question: str,
        base_answer: str,
        source_label: str,
        faq_context: str | None = None,
        conversation_context: str | None = None,
    ) -> str:
        ...
