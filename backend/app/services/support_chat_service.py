from __future__ import annotations

from uuid import uuid4

from app.core.errors import ConflictError
from app.core.errors import ForbiddenError
from app.core.errors import NotFoundError
from app.models.user import User
from app.repositories.support_repository import SupportRepository
from app.schemas.support import SupportConversationCreateRequest


class SupportChatService:
    def __init__(self, support_repository: SupportRepository) -> None:
        self.support_repository = support_repository

    def create_or_reuse_conversation(
        self,
        *,
        customer_user: User,
        payload: SupportConversationCreateRequest,
    ):
        if customer_user.is_guest:
            raise ForbiddenError("Guest users cannot open live support conversations")

        existing = self.support_repository.get_active_conversation_for_customer(customer_user.id)
        if existing is not None:
            return existing

        conversation_id = f"sc_{uuid4().hex[:20]}"

        return self.support_repository.create_conversation(
            conversation_id=conversation_id,
            customer_user_id=customer_user.id,
            source_session_id=payload.source_session_id,
            priority=payload.priority,
            escalation_reason_code=payload.escalation_reason_code,
            escalation_reference_id=payload.escalation_reference_id,
        )

    def get_conversation(self, *, current_user: User, conversation_id: str):
        row = self.support_repository.get_conversation_by_id(conversation_id)
        if row is None:
            raise NotFoundError("Support conversation not found")

        if current_user.is_admin:
            return row
        if row.customer_user_id != current_user.id:
            raise ForbiddenError("Conversation does not belong to current user")
        return row

    def list_messages(self, *, current_user: User, conversation_id: str, limit: int = 50):
        _ = self.get_conversation(current_user=current_user, conversation_id=conversation_id)
        return self.support_repository.list_messages(conversation_id=conversation_id, limit=limit)

    def send_message(self, *, current_user: User, conversation_id: str, body: str):
        row = self.get_conversation(current_user=current_user, conversation_id=conversation_id)
        if row.status == "closed":
            raise ConflictError("Conversation is closed")

        if current_user.is_admin:
            if row.assigned_admin_user_id is None:
                claimed = self.support_repository.claim_conversation(
                    conversation_id=conversation_id,
                    admin_user_id=current_user.id,
                )
                if claimed is None:
                    raise ConflictError("Conversation cannot be claimed")
                row = claimed
            elif row.assigned_admin_user_id != current_user.id:
                raise ForbiddenError("Conversation is assigned to another admin")
            sender_role = "admin"
        else:
            if row.customer_user_id != current_user.id:
                raise ForbiddenError("Conversation does not belong to current user")
            sender_role = "customer"

        message_id = f"sm_{uuid4().hex[:24]}"

        return self.support_repository.create_message(
            message_id=message_id,
            conversation_id=conversation_id,
            sender_user_id=current_user.id,
            sender_role=sender_role,
            body=body.strip(),
        )

    def list_open_queue(self, *, admin_user: User, limit: int = 50):
        if not admin_user.is_admin:
            raise ForbiddenError("Admin access required")
        return self.support_repository.list_open_queue(limit=limit)

    def list_assigned(self, *, admin_user: User, limit: int = 50):
        if not admin_user.is_admin:
            raise ForbiddenError("Admin access required")
        return self.support_repository.list_assigned_to_admin(admin_user_id=admin_user.id, limit=limit)

    def claim_conversation(self, *, admin_user: User, conversation_id: str):
        if not admin_user.is_admin:
            raise ForbiddenError("Admin access required")
        claimed = self.support_repository.claim_conversation(
            conversation_id=conversation_id,
            admin_user_id=admin_user.id,
        )
        if claimed is None:
            raise ConflictError("Conversation cannot be claimed in current state")
        return claimed

    def release_conversation(self, *, admin_user: User, conversation_id: str):
        if not admin_user.is_admin:
            raise ForbiddenError("Admin access required")
        released = self.support_repository.release_conversation(
            conversation_id=conversation_id,
            admin_user_id=admin_user.id,
        )
        if released is None:
            raise ConflictError("Conversation cannot be released in current state")
        return released

    def close_conversation(self, *, admin_user: User, conversation_id: str):
        if not admin_user.is_admin:
            raise ForbiddenError("Admin access required")
        row = self.support_repository.get_conversation_by_id(conversation_id)
        if row is None:
            raise NotFoundError("Support conversation not found")
        if row.assigned_admin_user_id not in {None, admin_user.id}:
            raise ForbiddenError("Conversation is assigned to another admin")

        closed = self.support_repository.close_conversation(conversation_id=conversation_id)
        if closed is None:
            raise ConflictError("Conversation cannot be closed in current state")
        return closed
