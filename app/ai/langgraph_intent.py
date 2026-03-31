from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.providers.base import LLMProvider


class IntentGraphState(TypedDict):
    message_text: str
    intent: str
    confidence: float
    reason: str
    used_llm: bool


class HybridIntentGraph:
    def __init__(self, *, llm_provider: LLMProvider, rule_confidence_threshold: float = 0.75) -> None:
        self.llm_provider = llm_provider
        self.rule_confidence_threshold = rule_confidence_threshold
        self.graph = self._build_graph()

    def run(self, *, message_text: str) -> IntentGraphState:
        initial: IntentGraphState = {
            "message_text": message_text,
            "intent": "general_support",
            "confidence": 0.0,
            "reason": "uninitialized",
            "used_llm": False,
        }
        return self.graph.invoke(initial)

    def _build_graph(self):
        builder: StateGraph[IntentGraphState] = StateGraph(IntentGraphState)
        builder.add_node("rule_classify", self._rule_classify_node)
        builder.add_node("llm_classify", self._llm_classify_node)
        builder.add_node("finalize", self._finalize_node)

        builder.add_edge(START, "rule_classify")
        builder.add_conditional_edges(
            "rule_classify",
            self._rule_or_llm_edge,
            {"finalize": "finalize", "llm_classify": "llm_classify"},
        )
        builder.add_edge("llm_classify", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile()

    def _rule_classify_node(self, state: IntentGraphState) -> IntentGraphState:
        normalized = state["message_text"].lower()

        if any(token in normalized for token in ["refund", "money back", "reimburse"]):
            state["intent"] = "refund_policy"
            state["confidence"] = 0.9
            state["reason"] = "rule_refund_keywords"
            return state
        if any(token in normalized for token in ["where is my order", "order", "delivery"]):
            state["intent"] = "order_status"
            state["confidence"] = 0.86
            state["reason"] = "rule_order_keywords"
            return state
        if any(token in normalized for token in ["verify", "verification", "verified"]):
            state["intent"] = "account_verification"
            state["confidence"] = 0.84
            state["reason"] = "rule_verification_keywords"
            return state

        state["intent"] = "general_support"
        state["confidence"] = 0.5
        state["reason"] = "rule_low_confidence"
        return state

    def _rule_or_llm_edge(self, state: IntentGraphState) -> str:
        if state["confidence"] >= self.rule_confidence_threshold:
            return "finalize"
        return "llm_classify"

    def _llm_classify_node(self, state: IntentGraphState) -> IntentGraphState:
        result = self.llm_provider.classify_intent(message_text=state["message_text"])
        state["intent"] = result.intent
        state["confidence"] = result.confidence
        state["reason"] = result.reason
        state["used_llm"] = True
        return state

    @staticmethod
    def _finalize_node(state: IntentGraphState) -> IntentGraphState:
        return state
