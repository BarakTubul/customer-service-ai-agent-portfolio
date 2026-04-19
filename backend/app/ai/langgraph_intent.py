from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.providers.base import LLMProvider


class IntentGraphState(TypedDict):
    message_text: str
    conversation_context: str
    intent: str
    confidence: float
    reason: str
    used_llm: bool


class HybridIntentGraph:
    def __init__(self, *, llm_provider: LLMProvider, rule_confidence_threshold: float = 0.75) -> None:
        self.llm_provider = llm_provider
        self.rule_confidence_threshold = rule_confidence_threshold
        self.graph = self._build_graph()

    def run(self, *, message_text: str, conversation_context: str = "") -> IntentGraphState:
        initial: IntentGraphState = {
            "message_text": message_text,
            "conversation_context": conversation_context,
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
        compact = " ".join(normalized.split())

        if compact in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "shalom"}:
            state["intent"] = "general_support"
            state["confidence"] = 0.98
            state["reason"] = "rule_greeting_smalltalk"
            return state

        if any(
            phrase in normalized
            for phrase in [
                "human help",
                "human support",
                "human assistance",
                "human agent",
                "talk to a person",
                "talk to human",
                "speak with a human",
                "speak to a human",
                "need assistance",
                "assistance now",
                "real person",
                "live agent",
                "manager",
                "escalat",
            ]
        ):
            state["intent"] = "general_support"
            state["confidence"] = 0.99
            state["reason"] = "rule_human_escalation_request"
            return state

        if self._looks_context_dependent_followup(
            message_text=compact,
            conversation_context=state["conversation_context"],
        ):
            # Defer context-heavy follow-ups to the LLM classifier.
            state["intent"] = "general_support"
            state["confidence"] = 0.35
            state["reason"] = "rule_context_dependent_followup"
            return state

        if any(token in normalized for token in ["refund", "money back", "reimburse"]):
            if any(phrase in normalized for phrase in ["request a refund", "ask for refund", "get a refund", "where can i ask for refund", "where can i request a refund"]):
                state["intent"] = "refund_request"
                state["confidence"] = 0.95
                state["reason"] = "rule_refund_request_keywords"
                return state
            state["intent"] = "refund_policy"
            state["confidence"] = 0.9
            state["reason"] = "rule_refund_keywords"
            return state
        if any(phrase in normalized for phrase in ["order food", "place an order", "place order", "how do i order", "where can i order", "where can i order food"]):
            state["intent"] = "order_placement"
            state["confidence"] = 0.94
            state["reason"] = "rule_order_placement_keywords"
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

    @staticmethod
    def _looks_context_dependent_followup(*, message_text: str, conversation_context: str) -> bool:
        if not conversation_context.strip() or not message_text:
            return False

        normalized = message_text.lower()
        tokens = [token for token in normalized.replace("?", " ").replace("!", " ").replace(",", " ").split() if token]
        if not tokens:
            return False

        explicit_intent_markers = [
            "refund",
            "money back",
            "reimburse",
            "where is my order",
            "order status",
            "delivery",
            "place an order",
            "order food",
            "verify",
            "verification",
            "human",
            "agent",
            "manager",
            "escalat",
        ]
        if any(marker in normalized for marker in explicit_intent_markers):
            return False

        referential_terms = {
            "it",
            "that",
            "this",
            "those",
            "them",
            "same",
            "one",
            "ones",
            "there",
            "again",
            "too",
            "also",
        }
        acknowledgement_terms = {
            "ok",
            "okay",
            "yes",
            "yeah",
            "yep",
            "sure",
            "please",
            "right",
            "correct",
            "exactly",
            "alright",
        }

        has_referential_signal = any(token in referential_terms for token in tokens)
        has_ack_signal = any(token in acknowledgement_terms for token in tokens)
        return (has_referential_signal or has_ack_signal) and len(tokens) <= 8

    def _rule_or_llm_edge(self, state: IntentGraphState) -> str:
        if state["confidence"] >= self.rule_confidence_threshold:
            return "finalize"
        return "llm_classify"

    def _llm_classify_node(self, state: IntentGraphState) -> IntentGraphState:
        result = self.llm_provider.classify_intent(
            message_text=state["message_text"],
            conversation_context=state["conversation_context"],
        )
        state["intent"] = result.intent
        state["confidence"] = result.confidence
        state["reason"] = result.reason
        state["used_llm"] = True
        return state

    @staticmethod
    def _finalize_node(state: IntentGraphState) -> IntentGraphState:
        return state
