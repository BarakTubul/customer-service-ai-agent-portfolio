from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.support_conversation import SupportConversation
from app.models.support_message import SupportMessage


class SupportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_conversation_by_id(self, conversation_id: str) -> SupportConversation | None:
        stmt = select(SupportConversation).where(SupportConversation.conversation_id == conversation_id)
        return self.db.scalar(stmt)

    def get_active_conversation_for_customer(self, customer_user_id: int) -> SupportConversation | None:
        stmt = (
            select(SupportConversation)
            .where(SupportConversation.customer_user_id == customer_user_id)
            .where(SupportConversation.status.in_(["open", "assigned"]))
            .order_by(SupportConversation.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def create_conversation(
        self,
        *,
        conversation_id: str,
        customer_user_id: int,
        source_session_id: str | None,
        priority: str,
        escalation_reason_code: str | None,
        escalation_reference_id: str | None,
    ) -> SupportConversation:
        row = SupportConversation(
            conversation_id=conversation_id,
            customer_user_id=customer_user_id,
            source_session_id=source_session_id,
            status="open",
            priority=priority,
            assigned_admin_user_id=None,
            escalation_reason_code=escalation_reason_code,
            escalation_reference_id=escalation_reference_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_open_queue(self, *, limit: int = 50) -> list[SupportConversation]:
        bounded = max(1, min(limit, 500))
        stmt = (
            select(SupportConversation)
            .where(SupportConversation.status == "open")
            .where(SupportConversation.assigned_admin_user_id.is_(None))
            .order_by(SupportConversation.created_at.asc())
            .limit(bounded)
        )
        return list(self.db.scalars(stmt).all())

    def list_assigned_to_admin(self, *, admin_user_id: int, limit: int = 50) -> list[SupportConversation]:
        bounded = max(1, min(limit, 500))
        stmt = (
            select(SupportConversation)
            .where(SupportConversation.assigned_admin_user_id == admin_user_id)
            .where(SupportConversation.status.in_(["assigned", "open"]))
            .order_by(SupportConversation.updated_at.desc())
            .limit(bounded)
        )
        return list(self.db.scalars(stmt).all())

    def claim_conversation(self, *, conversation_id: str, admin_user_id: int) -> SupportConversation | None:
        row = self.get_conversation_by_id(conversation_id)
        if row is None or row.status == "closed":
            return None
        if row.assigned_admin_user_id is not None and row.assigned_admin_user_id != admin_user_id:
            return None

        row.assigned_admin_user_id = admin_user_id
        row.status = "assigned"
        row.updated_at = datetime.now(UTC)

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def release_conversation(self, *, conversation_id: str, admin_user_id: int) -> SupportConversation | None:
        row = self.get_conversation_by_id(conversation_id)
        if row is None or row.status == "closed":
            return None
        if row.assigned_admin_user_id != admin_user_id:
            return None

        row.assigned_admin_user_id = None
        row.status = "open"
        row.updated_at = datetime.now(UTC)

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def close_conversation(self, *, conversation_id: str) -> SupportConversation | None:
        row = self.get_conversation_by_id(conversation_id)
        if row is None or row.status == "closed":
            return None

        now = datetime.now(UTC)
        row.status = "closed"
        row.closed_at = now
        row.updated_at = now

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_message(
        self,
        *,
        message_id: str,
        conversation_id: str,
        sender_user_id: int,
        sender_role: str,
        body: str,
    ) -> SupportMessage:
        row = SupportMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            body=body,
            delivered_at=datetime.now(UTC),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_messages(self, *, conversation_id: str, limit: int = 50) -> list[SupportMessage]:
        bounded = max(1, min(limit, 500))
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.conversation_id == conversation_id)
            .order_by(SupportMessage.created_at.desc())
            .limit(bounded)
        )
        rows = list(self.db.scalars(stmt).all())
        rows.reverse()
        return rows
