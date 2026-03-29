from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FAQEntry:
    intent: str
    source_id: str
    source_label: str
    policy_version: str
    answer: str


class FAQRepository:
    def __init__(self) -> None:
        self._entries: list[FAQEntry] = [
            FAQEntry(
                intent="refund_policy",
                source_id="refund-policy-v1",
                source_label="Based on Refund Policy",
                policy_version="2026.03",
                answer="Refunds are typically processed within 5 to 7 business days after approval.",
            ),
            FAQEntry(
                intent="order_status",
                source_id="order-status-v1",
                source_label="Based on Order Status Guide",
                policy_version="2026.03",
                answer="You can track your order from the Orders section once you are signed in.",
            ),
            FAQEntry(
                intent="account_verification",
                source_id="verification-v1",
                source_label="Based on Account Verification Guide",
                policy_version="2026.03",
                answer="Complete email or SMS verification to unlock protected account actions.",
            ),
        ]

    def find_best_match(self, *, intent: str, query_text: str) -> tuple[FAQEntry, float] | None:
        normalized_query = query_text.lower()
        candidates = [entry for entry in self._entries if entry.intent == intent]
        if not candidates:
            candidates = self._entries

        best_entry: FAQEntry | None = None
        best_score = 0.0
        for entry in candidates:
            score = 0.55 if entry.intent == intent else 0.35
            for token in entry.answer.lower().split():
                if token.strip(".,") in normalized_query:
                    score += 0.02
            if score > best_score:
                best_entry = entry
                best_score = min(score, 0.99)

        if best_entry is None:
            return None
        return best_entry, best_score
