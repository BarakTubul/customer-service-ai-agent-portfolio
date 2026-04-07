from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_current_user, get_notification_service
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.services.account_order_service import AccountOrderService
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("/notifications/live", response_model=list[NotificationResponse])
def list_live_notifications(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> list[NotificationResponse]:
    return notification_service.get_live_notifications(current_user)


@router.websocket("/ws/notifications")
async def stream_live_notifications(websocket: WebSocket) -> None:
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

        notification_service = NotificationService(
            AccountOrderService(OrderRepository(db), UserRepository(db))
        )
        await websocket.accept()

        while True:
            notifications = notification_service.get_live_notifications(user)
            if notifications:
                await websocket.send_json([
                    notification.model_dump(mode="json") for notification in notifications
                ])
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    finally:
        db_generator.close()