from __future__ import annotations

from dataclasses import dataclass
import re


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if token}


@dataclass(frozen=True)
class FAQEntry:
    intent: str
    source_id: str
    source_label: str
    policy_version: str
    answer: str


@dataclass(frozen=True)
class FAQChunk:
    chunk_id: str
    intent: str
    source_id: str
    source_label: str
    policy_version: str
    text: str


class FAQRepository:
    def __init__(self) -> None:
        self._chunks: list[FAQChunk] = [
            FAQChunk(
                chunk_id="refund-policy-v1-1",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Refunds are typically processed within 5 to 7 business days after approval.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-2",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Users can check refund progress from support using the refund request ID.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-3",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Refund eligibility depends on order state, reason code, and policy time window.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-4",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Duplicate refund submissions return the existing request reference instead of creating a new one.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-5",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Partial refunds may require selecting specific items and quantities from the original order.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-6",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="If a refund request is ineligible, users receive a policy reason and can request escalation.",
            ),
            FAQChunk(
                chunk_id="refund-policy-v1-7",
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                text="Refund status values include submitted, under review, approved, and denied.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-1",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="You can track your order from the Orders section once you are signed in.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-2",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="Order timeline updates include accepted, preparing, pickup, in transit, and delivered.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-3",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="Expected delivery windows are estimates and may change when simulation scenarios include delays.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-4",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="If no updates appear for an extended period, users can request human escalation.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-5",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="Only authenticated users can retrieve their own order status and timeline data.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-6",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="Invalid order IDs return a not found response with guidance to verify the identifier.",
            ),
            FAQChunk(
                chunk_id="order-status-v1-7",
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                text="Timeline simulation supports scenarios like slow preparation, delayed pickup, and driver shortage.",
            ),
            FAQChunk(
                chunk_id="order-placement-v1-1",
                intent="order_placement",
                source_id="order-placement-v1",
                source_label="Based on Order Placement Guide",
                policy_version="2026.03",
                text="You can place a food order from the Order page after signing in.",
            ),
            FAQChunk(
                chunk_id="order-placement-v1-2",
                intent="order_placement",
                source_id="order-placement-v1",
                source_label="Based on Order Placement Guide",
                policy_version="2026.03",
                text="Use the catalog to choose items, add them to your cart, and complete checkout.",
            ),
            FAQChunk(
                chunk_id="order-placement-v1-3",
                intent="order_placement",
                source_id="order-placement-v1",
                source_label="Based on Order Placement Guide",
                policy_version="2026.03",
                text="Guest users can browse the catalog, but a registered account is required to submit an order.",
            ),
            FAQChunk(
                chunk_id="order-placement-v1-4",
                intent="order_placement",
                source_id="order-placement-v1",
                source_label="Based on Order Placement Guide",
                policy_version="2026.03",
                text="Checkout validation checks shipping address, delivery option, and payment reference before submission.",
            ),
            FAQChunk(
                chunk_id="refund-request-v1-1",
                intent="refund_request",
                source_id="refund-request-v1",
                source_label="Based on Refund Request Guide",
                policy_version="2026.03",
                text="You can start a refund request from the Refund page after selecting an eligible order.",
            ),
            FAQChunk(
                chunk_id="refund-request-v1-2",
                intent="refund_request",
                source_id="refund-request-v1",
                source_label="Based on Refund Request Guide",
                policy_version="2026.03",
                text="Refund requests require a reason code and may be reviewed before approval.",
            ),
            FAQChunk(
                chunk_id="refund-request-v1-3",
                intent="refund_request",
                source_id="refund-request-v1",
                source_label="Based on Refund Request Guide",
                policy_version="2026.03",
                text="Duplicate refund requests reuse the existing request instead of creating a duplicate.",
            ),
            FAQChunk(
                chunk_id="refund-request-v1-4",
                intent="refund_request",
                source_id="refund-request-v1",
                source_label="Based on Refund Request Guide",
                policy_version="2026.03",
                text="If a refund request is not eligible, the assistant can explain the policy reason and next steps.",
            ),
            FAQChunk(
                chunk_id="verification-v1-1",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Complete email or SMS verification to unlock protected account actions.",
            ),
            FAQChunk(
                chunk_id="verification-v1-2",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Unverified accounts can browse but cannot perform protected account or refund actions.",
            ),
            FAQChunk(
                chunk_id="verification-v1-3",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Verification challenges can expire and users may request resend after cooldown.",
            ),
            FAQChunk(
                chunk_id="verification-v1-4",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Too many incorrect verification attempts can trigger temporary lockout behavior.",
            ),
            FAQChunk(
                chunk_id="verification-v1-5",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Verified and active accounts can log in and access protected support features.",
            ),
            FAQChunk(
                chunk_id="verification-v1-6",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Guest sessions can be upgraded to registered accounts without losing eligible conversation context.",
            ),
            FAQChunk(
                chunk_id="verification-v1-7",
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                text="Verification state transitions are pending, verified active, locked, or disabled.",
            ),
            FAQChunk(
                chunk_id="general-support-v1-1",
                intent="general_support",
                source_id="support-guide-v1",
                source_label="Based on Support Guide",
                policy_version="2026.03",
                text="If the assistant is uncertain, it should ask a clarifying question before taking action.",
            ),
            FAQChunk(
                chunk_id="general-support-v1-2",
                intent="general_support",
                source_id="support-guide-v1",
                source_label="Based on Support Guide",
                policy_version="2026.03",
                text="Users can ask for human help at any point and receive escalation status updates.",
            ),
            FAQChunk(
                chunk_id="general-support-v1-3",
                intent="general_support",
                source_id="support-guide-v1",
                source_label="Based on Support Guide",
                policy_version="2026.03",
                text="Sensitive account details are masked in responses to protect user privacy.",
            ),
        ]

    def retrieve_chunks(self, *, intent: str, query_text: str, top_k: int = 3) -> list[tuple[FAQChunk, float]]:
        query_tokens = _tokenize(query_text)
        candidates = [chunk for chunk in self._chunks if chunk.intent == intent]
        if not candidates:
            candidates = self._chunks

        scored: list[tuple[FAQChunk, float]] = []
        for chunk in candidates:
            chunk_tokens = _tokenize(chunk.text)
            if not chunk_tokens:
                continue

            overlap = len(query_tokens & chunk_tokens)
            lexical_score = overlap / max(1, len(query_tokens))
            intent_bonus = 0.45 if chunk.intent == intent else 0.2
            score = min(intent_bonus + lexical_score, 0.99)
            scored.append((chunk, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def find_best_match(self, *, intent: str, query_text: str) -> tuple[FAQEntry, float] | None:
        retrieved = self.retrieve_chunks(intent=intent, query_text=query_text, top_k=3)
        if not retrieved:
            return None

        top_chunk, top_score = retrieved[0]
        answer = " ".join(chunk.text for chunk, _ in retrieved)
        entry = FAQEntry(
            intent=top_chunk.intent,
            source_id=top_chunk.source_id,
            source_label=top_chunk.source_label,
            policy_version=top_chunk.policy_version,
            answer=answer,
        )
        return entry, top_score
