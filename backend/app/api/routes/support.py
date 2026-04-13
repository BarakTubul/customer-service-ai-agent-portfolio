from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.api.dependencies import get_support_chat_service
from app.api.dependencies import require_admin_user
from app.models.user import User
from app.schemas.support import (
    SupportConversationCreateRequest,
    SupportConversationListResponse,
    SupportConversationResponse,
    SupportMessageCreateRequest,
    SupportMessageListResponse,
    SupportMessageResponse,
)
from app.services.support_chat_service import SupportChatService

router = APIRouter()


def _conversation_to_response(row) -> SupportConversationResponse:
    return SupportConversationResponse(
        conversation_id=row.conversation_id,
        customer_user_id=row.customer_user_id,
        status=row.status,
        priority=row.priority,
        assigned_admin_user_id=row.assigned_admin_user_id,
        source_session_id=row.source_session_id,
        escalation_reason_code=row.escalation_reason_code,
        escalation_reference_id=row.escalation_reference_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
    )


def _message_to_response(row) -> SupportMessageResponse:
    return SupportMessageResponse(
        message_id=row.message_id,
        conversation_id=row.conversation_id,
        sender_user_id=row.sender_user_id,
        sender_role=row.sender_role,
        body=row.body,
        created_at=row.created_at,
        delivered_at=row.delivered_at,
        read_at=row.read_at,
    )


@router.post("/support/conversations", response_model=SupportConversationResponse)
def create_support_conversation(
    payload: SupportConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.create_or_reuse_conversation(customer_user=current_user, payload=payload)
    return _conversation_to_response(row)


@router.get("/support/conversations/{conversation_id}", response_model=SupportConversationResponse)
def get_support_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.get_conversation(current_user=current_user, conversation_id=conversation_id)
    return _conversation_to_response(row)


@router.get("/support/conversations/{conversation_id}/messages", response_model=SupportMessageListResponse)
def list_support_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportMessageListResponse:
    rows = support_chat_service.list_messages(current_user=current_user, conversation_id=conversation_id, limit=limit)
    items = [_message_to_response(row) for row in rows]
    return SupportMessageListResponse(items=items, total=len(items))


@router.post("/support/conversations/{conversation_id}/messages", response_model=SupportMessageResponse)
def send_support_message(
    conversation_id: str,
    payload: SupportMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportMessageResponse:
    row = support_chat_service.send_message(
        current_user=current_user,
        conversation_id=conversation_id,
        body=payload.body,
    )
    return _message_to_response(row)


@router.get("/admin/support/conversations/queue", response_model=SupportConversationListResponse)
def list_support_queue(
    limit: int = Query(default=50, ge=1, le=500),
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationListResponse:
    rows = support_chat_service.list_open_queue(admin_user=admin_user, limit=limit)
    items = [_conversation_to_response(row) for row in rows]
    return SupportConversationListResponse(items=items, total=len(items))


@router.get("/admin/support/conversations/assigned", response_model=SupportConversationListResponse)
def list_assigned_support_conversations(
    limit: int = Query(default=50, ge=1, le=500),
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationListResponse:
    rows = support_chat_service.list_assigned(admin_user=admin_user, limit=limit)
    items = [_conversation_to_response(row) for row in rows]
    return SupportConversationListResponse(items=items, total=len(items))


@router.post("/admin/support/conversations/{conversation_id}/claim", response_model=SupportConversationResponse)
def claim_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.claim_conversation(admin_user=admin_user, conversation_id=conversation_id)
    return _conversation_to_response(row)


@router.post("/admin/support/conversations/{conversation_id}/release", response_model=SupportConversationResponse)
def release_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.release_conversation(admin_user=admin_user, conversation_id=conversation_id)
    return _conversation_to_response(row)


@router.post("/admin/support/conversations/{conversation_id}/close", response_model=SupportConversationResponse)
def close_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.close_conversation(admin_user=admin_user, conversation_id=conversation_id)
    return _conversation_to_response(row)
