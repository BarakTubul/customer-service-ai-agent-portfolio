from __future__ import annotations

from app.repositories.faq_repository import FAQRepository


def test_retrieve_chunks_returns_ranked_citations() -> None:
    repository = FAQRepository()

    retrieved = repository.retrieve_chunks(
        intent="refund_policy",
        query_text="how long refund takes",
        top_k=3,
    )

    assert len(retrieved) >= 1
    top_chunk, top_score = retrieved[0]
    assert top_chunk.source_id == "refund-policy-v1"
    assert 0.0 < top_score <= 0.99


def test_find_best_match_aggregates_top_chunks() -> None:
    repository = FAQRepository()

    result = repository.find_best_match(
        intent="order_status",
        query_text="where is my order delivery timeline",
    )

    assert result is not None
    entry, score = result
    assert entry.source_id == "order-status-v1"
    assert "Orders section" in entry.answer or "timeline" in entry.answer.lower()
    assert score > 0.0
