from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_current_user
from app.api.dependencies import get_support_chat_service
from app.api.dependencies import require_admin_user
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.support import (
    SupportConversationCreateRequest,
    SupportConversationPriorityUpdateRequest,
    SupportConversationListResponse,
    SupportConversationResponse,
    SupportMessageCreateRequest,
    SupportMessageListResponse,
    SupportMessageResponse,
)
from app.repositories.support_repository import SupportRepository
from app.repositories.user_repository import UserRepository
from app.services.support_chat_service import SupportChatService

router = APIRouter()
SUPPORT_SNAPSHOT_LIMIT = 30


class SupportWebSocketManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        self._rooms[conversation_id].add(websocket)

    def disconnect(self, conversation_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(conversation_id)
        if room is None:
            return
        room.discard(websocket)
        if not room:
            self._rooms.pop(conversation_id, None)

    async def broadcast_json(self, conversation_id: str, payload: dict[str, object]) -> None:
        room = list(self._rooms.get(conversation_id, set()))
        if not room:
            return

        for websocket in room:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, websocket)


support_ws_manager = SupportWebSocketManager()


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


def _conversation_summary_to_response(row, last_message_at, last_message_preview, unread_message_count) -> SupportConversationResponse:
    response = _conversation_to_response(row)
    response.last_message_at = last_message_at
    response.last_message_preview = last_message_preview
    response.unread_message_count = int(unread_message_count or 0)
    return response


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


def _authenticate_websocket_user(websocket: WebSocket) -> User | None:
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            return None
    except Exception:
        return None

    db_generator = get_db()
    db = next(db_generator)
    try:
        user = UserRepository(db).get_by_id(int(subject))
        if user is None or user.is_guest:
            return None
        return user
    finally:
        db_generator.close()


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
    before_message_id: str | None = Query(default=None, min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportMessageListResponse:
    rows = support_chat_service.list_messages(
        current_user=current_user,
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id,
    )
    items = [_message_to_response(row) for row in rows]
    return SupportMessageListResponse(items=items, total=len(items))


@router.post("/support/conversations/{conversation_id}/messages", response_model=SupportMessageResponse)
async def send_support_message(
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
    updated_conversation = support_chat_service.get_conversation(
        current_user=current_user,
        conversation_id=conversation_id,
    )

    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "conversation.updated",
            "conversation_id": conversation_id,
            "payload": _conversation_to_response(updated_conversation).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "message.new",
            "conversation_id": conversation_id,
            "payload": _message_to_response(row).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
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


@router.get("/admin/support/conversations/all", response_model=SupportConversationListResponse)
def list_all_support_conversations(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None, pattern="^(open|assigned|closed)$"),
    priority: str | None = Query(default=None, pattern="^(normal|high)$"),
    assigned_state: str = Query(default="all", pattern="^(all|assigned|unassigned)$"),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    updated_after: datetime | None = Query(default=None),
    updated_before: datetime | None = Query(default=None),
    unread_only: bool = Query(default=False),
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationListResponse:
    rows = support_chat_service.list_admin_conversations(
        admin_user=admin_user,
        limit=limit,
        status=status,
        priority=priority,
        assigned_state=assigned_state,
        created_after=created_after,
        created_before=created_before,
        updated_after=updated_after,
        updated_before=updated_before,
        unread_only=unread_only,
    )
    items = [
        _conversation_summary_to_response(row[0], row[1], row[2], row[3])
        for row in rows
    ]
    return SupportConversationListResponse(items=items, total=len(items))


@router.post("/admin/support/conversations/{conversation_id}/claim", response_model=SupportConversationResponse)
async def claim_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.claim_conversation(admin_user=admin_user, conversation_id=conversation_id)
    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "conversation.updated",
            "conversation_id": conversation_id,
            "payload": _conversation_to_response(row).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    return _conversation_to_response(row)


@router.post("/admin/support/conversations/{conversation_id}/release", response_model=SupportConversationResponse)
async def release_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.release_conversation(admin_user=admin_user, conversation_id=conversation_id)
    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "conversation.updated",
            "conversation_id": conversation_id,
            "payload": _conversation_to_response(row).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    return _conversation_to_response(row)


@router.post("/admin/support/conversations/{conversation_id}/close", response_model=SupportConversationResponse)
async def close_support_conversation(
    conversation_id: str,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.close_conversation(admin_user=admin_user, conversation_id=conversation_id)
    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "conversation.updated",
            "conversation_id": conversation_id,
            "payload": _conversation_to_response(row).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    return _conversation_to_response(row)


@router.patch("/admin/support/conversations/{conversation_id}/priority", response_model=SupportConversationResponse)
async def update_support_conversation_priority(
    conversation_id: str,
    payload: SupportConversationPriorityUpdateRequest,
    admin_user: User = Depends(require_admin_user),
    support_chat_service: SupportChatService = Depends(get_support_chat_service),
) -> SupportConversationResponse:
    row = support_chat_service.update_conversation_priority(
        admin_user=admin_user,
        conversation_id=conversation_id,
        priority=payload.priority,
    )
    await support_ws_manager.broadcast_json(
        conversation_id,
        {
            "type": "conversation.updated",
            "conversation_id": conversation_id,
            "payload": _conversation_to_response(row).model_dump(mode="json"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    return _conversation_to_response(row)


@router.websocket("/ws/support/{conversation_id}")
async def stream_support_conversation(websocket: WebSocket, conversation_id: str) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    db_generator = get_db()
    db = next(db_generator)
    try:
        user = UserRepository(db).get_by_id(int(subject))
        if user is None or user.is_guest:
            await websocket.close(code=1008)
            return

        support_chat_service = SupportChatService(SupportRepository(db))
        conversation = support_chat_service.get_conversation(current_user=user, conversation_id=conversation_id)
        await websocket.accept()
        await support_ws_manager.connect(conversation_id, websocket)

        snapshot = {
            "type": "conversation.snapshot",
            "conversation_id": conversation_id,
            "payload": {
                "conversation": _conversation_to_response(conversation).model_dump(mode="json"),
                "messages": [
                    _message_to_response(row).model_dump(mode="json")
                    for row in support_chat_service.list_messages(
                        current_user=user,
                        conversation_id=conversation_id,
                        limit=SUPPORT_SNAPSHOT_LIMIT,
                    )
                ],
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await websocket.send_json(snapshot)

        while True:
            try:
                event = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            event_type = event.get("type")
            if event_type != "message.send":
                await websocket.send_json(
                    {
                        "type": "error",
                        "conversation_id": conversation_id,
                        "payload": {"message": "Unsupported websocket event"},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            payload = event.get("payload") or {}
            body = str(payload.get("body", "")).strip()
            if not body:
                await websocket.send_json(
                    {
                        "type": "error",
                        "conversation_id": conversation_id,
                        "payload": {"message": "Message body is required"},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            try:
                message_row = support_chat_service.send_message(
                    current_user=user,
                    conversation_id=conversation_id,
                    body=body,
                )
                updated_conversation = support_chat_service.get_conversation(
                    current_user=user,
                    conversation_id=conversation_id,
                )
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "conversation_id": conversation_id,
                        "payload": {"message": str(exc)},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            await support_ws_manager.broadcast_json(
                conversation_id,
                {
                    "type": "conversation.updated",
                    "conversation_id": conversation_id,
                    "payload": _conversation_to_response(updated_conversation).model_dump(mode="json"),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            await support_ws_manager.broadcast_json(
                conversation_id,
                {
                    "type": "message.new",
                    "conversation_id": conversation_id,
                    "payload": _message_to_response(message_row).model_dump(mode="json"),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
    finally:
        support_ws_manager.disconnect(conversation_id, websocket)
        db_generator.close()
