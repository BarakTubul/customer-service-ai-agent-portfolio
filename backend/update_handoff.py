#!/usr/bin/env python
"""Update intent_faq_service.py for handoff integration."""

import re

with open('app/services/intent_faq_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update _build_human_handoff_intake_reply
old_method = r'''    @staticmethod
    def _build_human_handoff_intake_reply\(query_text: str, \*, reference_id: str \| None = None\) -> str:
        order_id = IntentFAQService\._extract_order_id\(query_text\)
        if order_id:
            text = \(
                f"Thanks, I captured your escalation for order \{order_id\}\. "
                "It is routed to the manager review flow now\."
            \)
        else:
            text = "Thanks, I captured your escalation and routed it to the manager review flow\."

        if reference_id:
            return f"\{text\} Reference ID: \{reference_id\}\."
        return text'''

new_method = '''    @staticmethod
    def _build_human_handoff_intake_reply(
        query_text: str, *, reference_id: str | None = None, conversation_id: str | None = None
    ) -> str:
        order_id = IntentFAQService._extract_order_id(query_text)
        if order_id:
            text = (
                f"Thanks, I captured your escalation for order {order_id}. "
                "It is routed to the manager review flow now."
            )
        else:
            text = "Thanks, I captured your escalation and routed it to the manager review flow."

        parts = [text]
        if reference_id:
            parts.append(f"Reference ID: {reference_id}.")
        if conversation_id:
            parts.append(f"You can chat with a manager here: /support/live/{conversation_id}")
        return " ".join(parts)'''

content = re.sub(old_method, new_method, content, flags=re.MULTILINE)

# Now update _enqueue_chat_escalation to return tuple and create support conversations
old_enqueue = '''    def _enqueue_chat_escalation(self, *, user: User, session_id: str, query_text: str) -> str | None:
        if self.refund_repository is None:
            return None

        order_id = self._extract_order_id(query_text)
        if order_id is None:
            return None

        idempotency_key = hashlib.sha256(
            f"chat-escalation:{user.id}:{session_id}:{order_id}".encode("utf-8")
        ).hexdigest()[:32]

        existing = self.refund_repository.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing.refund_request_id

        refund_request_id = hashlib.sha256(
            f"chat-escalation:{idempotency_key}".encode("utf-8")
        ).hexdigest()[:16]
        created_at = datetime.now(UTC)
        sla_deadline = created_at + timedelta(hours=self.MANUAL_REVIEW_SLA_HOURS)
        payload = {
            "source": "chat_escalation",
            "session_id": session_id,
            "user_id": user.id,
            "order_id": order_id,
            "issue_summary": query_text.strip(),
        }

        created = self.refund_repository.create(
            refund_request_id=refund_request_id,
            idempotency_key=idempotency_key,
            user_id=user.id,
            order_id=order_id,
            reason_code="chat_human_assistance",
            simulation_scenario_id="chat-escalation",
            status="pending_manual_review",
            status_reason="chat_escalation_requested",
            policy_version="chat",
            policy_reference="chat-escalation",
            resolution_action="manual_review",
            decision_reason_codes="chat_escalation",
            explanation_template_key="chat_escalation",
            explanation_params_json=json.dumps({"source": "chat"}, separators=(",", ":"), sort_keys=True),
            escalation_status="queued",
            escalation_queue_name=self.MANUAL_REVIEW_QUEUE_NAME,
            escalation_sla_deadline_at=sla_deadline,
            escalation_payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
        )
        return created.refund_request_id'''

new_enqueue = '''    def _enqueue_chat_escalation(self, *, user: User, session_id: str, query_text: str) -> tuple[str | None, str | None]:
        """Enqueue escalation and create support conversation. Returns (reference_id, conversation_id)."""
        reference_id = None
        conversation_id = None

        if self.refund_repository is not None:
            order_id = self._extract_order_id(query_text)
            if order_id is not None:
                idempotency_key = hashlib.sha256(
                    f"chat-escalation:{user.id}:{session_id}:{order_id}".encode("utf-8")
                ).hexdigest()[:32]

                existing = self.refund_repository.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    reference_id = existing.refund_request_id
                else:
                    refund_request_id = hashlib.sha256(
                        f"chat-escalation:{idempotency_key}".encode("utf-8")
                    ).hexdigest()[:16]
                    created_at = datetime.now(UTC)
                    sla_deadline = created_at + timedelta(hours=self.MANUAL_REVIEW_SLA_HOURS)
                    payload = {
                        "source": "chat_escalation",
                        "session_id": session_id,
                        "user_id": user.id,
                        "order_id": order_id,
                        "issue_summary": query_text.strip(),
                    }

                    created = self.refund_repository.create(
                        refund_request_id=refund_request_id,
                        idempotency_key=idempotency_key,
                        user_id=user.id,
                        order_id=order_id,
                        reason_code="chat_human_assistance",
                        simulation_scenario_id="chat-escalation",
                        status="pending_manual_review",
                        status_reason="chat_escalation_requested",
                        policy_version="chat",
                        policy_reference="chat-escalation",
                        resolution_action="manual_review",
                        decision_reason_codes="chat_escalation",
                        explanation_template_key="chat_escalation",
                        explanation_params_json=json.dumps({"source": "chat"}, separators=(",", ":"), sort_keys=True),
                        escalation_status="queued",
                        escalation_queue_name=self.MANUAL_REVIEW_QUEUE_NAME,
                        escalation_sla_deadline_at=sla_deadline,
                        escalation_payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    )
                    reference_id = created.refund_request_id

        if self.support_repository is not None and not user.is_guest:
            existing_conversation = self.support_repository.get_active_conversation_for_customer(user.id)
            if existing_conversation is not None:
                conversation_id = existing_conversation.conversation_id
            else:
                conversation_id = f"sc_{uuid4().hex[:20]}"
                self.support_repository.create_conversation(
                    conversation_id=conversation_id,
                    customer_user_id=user.id,
                    source_session_id=session_id,
                    priority="high",
                    escalation_reason_code="chat_escalation",
                    escalation_reference_id=reference_id,
                )

        return reference_id, conversation_id'''

content = content.replace(old_enqueue, new_enqueue)

# Update search_faq to use tuple return and pass conversation_id
old_search = '''    def search_faq(self, *, user: User, session_id: str, query_text: str, intent: str) -> FAQSearchResponse:
        if self._looks_like_escalation_intake(query_text):
            reference_id = self._enqueue_chat_escalation(
                user=user,
                session_id=session_id,
                query_text=query_text,
            )
            answer = FAQAnswer(
                text=self._build_human_handoff_intake_reply(query_text, reference_id=reference_id),
                confidence=0.97,
                source_label="Support Escalation",
                source_id="support-escalation",
                policy_version="n/a",
            )
            self.conversation_repository.add_message(
                session_id=session_id,
                user_id=user.id,
                role="assistant",
                text=answer.text,
            )
            return FAQSearchResponse(answer=answer, citations=[], retrieval_mode="handoff_intake")'''

new_search = '''    def search_faq(self, *, user: User, session_id: str, query_text: str, intent: str) -> FAQSearchResponse:
        if self._looks_like_escalation_intake(query_text):
            reference_id, conversation_id = self._enqueue_chat_escalation(
                user=user,
                session_id=session_id,
                query_text=query_text,
            )
            answer = FAQAnswer(
                text=self._build_human_handoff_intake_reply(
                    query_text, reference_id=reference_id, conversation_id=conversation_id
                ),
                confidence=0.97,
                source_label="Support Escalation",
                source_id="support-escalation",
                policy_version="n/a",
            )
            self.conversation_repository.add_message(
                session_id=session_id,
                user_id=user.id,
                role="assistant",
                text=answer.text,
            )
            return FAQSearchResponse(answer=answer, citations=[], retrieval_mode="handoff_intake")'''

content = content.replace(old_search, new_search)

with open('app/services/intent_faq_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully updated all handoff integration methods')
