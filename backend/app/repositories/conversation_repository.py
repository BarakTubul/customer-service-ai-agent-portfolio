from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_message(self, *, session_id: str, user_id: int, role: str, text: str) -> ConversationMessage:
        message = ConversationMessage(session_id=session_id, user_id=user_id, role=role, text=text)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_recent_messages(self, *, session_id: str, limit: int = 6) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        rows = list(self.db.scalars(stmt).all())
        rows.reverse()
        return rows
