from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from app.ai.providers.base import IntentClassification


class _IntentClassificationResult(BaseModel):
    intent: str = Field(
        description=(
            "Intent label. Prefer one of: refund_request, refund_policy, order_placement, "
            "order_status, account_verification, general_support"
        )
    )
    confidence: float = Field(description="Confidence score between 0 and 1")
    reason: str = Field(description="Short rationale")


class _FAQSynthesisResult(BaseModel):
    answer: str = Field(description="Concise customer-facing answer")


class OpenAILLMProvider:
    def __init__(self, *, api_key: str, model: str, temperature: float = 0.0) -> None:
        self.model = ChatOpenAI(api_key=api_key, model=model, temperature=temperature)

    def classify_intent(self, *, message_text: str) -> IntentClassification:
        structured = self.model.with_structured_output(_IntentClassificationResult)
        result = structured.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You classify customer support intents."
                        "Return one intent label and confidence."
                    ),
                },
                {
                    "role": "user",
                    "content": message_text,
                },
            ]
        )
        confidence = max(0.0, min(1.0, result.confidence))
        return IntentClassification(intent=result.intent, confidence=confidence, reason=result.reason)

    def synthesize_faq_answer(self, *, question: str, base_answer: str, source_label: str) -> str:
        structured = self.model.with_structured_output(_FAQSynthesisResult)
        result = structured.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Rewrite support answers to be concise, clear, and policy-safe."
                        "Do not invent facts beyond the provided base answer."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n"
                        f"Source label: {source_label}\n"
                        f"Base answer: {base_answer}"
                    ),
                },
            ]
        )
        return result.answer.strip()
