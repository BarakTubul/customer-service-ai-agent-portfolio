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
    assert faq.json()["answer"]["source_id"] == "verification-v1"

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
