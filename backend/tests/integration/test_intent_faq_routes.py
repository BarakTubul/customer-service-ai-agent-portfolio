from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/guest")
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_intent_resolve_returns_refund_intent(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/intent/resolve",
        json={
            "session_id": "sess-1",
            "message_id": "msg-1",
            "message_text": "How long does a refund take?",
            "locale": "en-US",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "refund_policy"
    assert payload["route"] == "faq_answer"


def test_intent_resolve_returns_refund_request_intent(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/intent/resolve",
        json={
            "session_id": "sess-refund-request",
            "message_id": "msg-refund-request",
            "message_text": "Where can I ask for refund?",
            "locale": "en-US",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "refund_request"
    assert payload["route"] == "faq_answer"


def test_intent_resolve_returns_order_placement_intent(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/intent/resolve",
        json={
            "session_id": "sess-order-placement",
            "message_id": "msg-order-placement",
            "message_text": "Where can I order food?",
            "locale": "en-US",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "order_placement"
    assert payload["route"] == "faq_answer"


def test_faq_search_and_context_roundtrip(client: TestClient) -> None:
    headers = _auth_headers(client)

    resolve = client.post(
        "/api/v1/intent/resolve",
        json={
            "session_id": "sess-ctx",
            "message_id": "msg-ctx-1",
            "message_text": "I need info about account verification",
            "locale": "en-US",
        },
        headers=headers,
    )
    assert resolve.status_code == 200

    faq = client.post(
        "/api/v1/faq/search",
        json={
            "session_id": "sess-ctx",
            "query_text": "How do I verify account",
            "intent": "account_verification",
            "locale": "en-US",
        },
        headers=headers,
    )
    assert faq.status_code == 200
    payload = faq.json()
    assert payload["answer"]["source_id"] == "verification-v1"
    assert payload["retrieval_mode"] == "rag_seeded"
    assert len(payload["citations"]) >= 1
    assert payload["citations"][0]["source_id"] == "verification-v1"

    context = client.get("/api/v1/conversations/sess-ctx/context", headers=headers)
    assert context.status_code == 200
    assert len(context.json()["recent_messages"]) >= 2


def test_escalation_check_low_confidence(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/fallback/escalation-check",
        json={
            "session_id": "sess-esc",
            "intent": "general_support",
            "confidence": 0.2,
            "reason": "unclear",
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["should_escalate"] is True


def test_faq_search_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/faq/search",
        json={
            "session_id": "sess-no-auth",
            "query_text": "refund time",
            "intent": "refund_policy",
            "locale": "en-US",
        },
    )

    assert response.status_code == 401


def test_intent_resolve_short_message_returns_clarify_route(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/intent/resolve",
        json={
            "session_id": "sess-short",
            "message_id": "msg-short",
            "message_text": "hi",
            "locale": "en-US",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "clarify"
    assert payload["requires_clarification"] is True


def test_escalation_check_high_risk_reason_code(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/fallback/escalation-check",
        json={
            "session_id": "sess-high-risk",
            "intent": "billing_dispute",
            "confidence": 0.95,
            "reason": "charge issue",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["should_escalate"] is True
    assert payload["escalation_reason_code"] == "high_risk_intent"
