from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_account_order_service, get_current_user
from app.models.user import User
from app.schemas.account import (
    AccountMeResponse,
    OrderResponse,
    OrderTimelineResponse,
    SessionStateResponse,
)
from app.services.account_order_service import AccountOrderService

router = APIRouter()


@router.get("/auth/session", response_model=SessionStateResponse)
def get_auth_session(
    current_user: User = Depends(get_current_user),
    account_order_service: AccountOrderService = Depends(get_account_order_service),
) -> SessionStateResponse:
    return account_order_service.get_session_state(current_user)


@router.get("/account/me", response_model=AccountMeResponse)
def get_account_me(
    current_user: User = Depends(get_current_user),
    account_order_service: AccountOrderService = Depends(get_account_order_service),
) -> AccountMeResponse:
    return account_order_service.get_account_me(current_user)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    account_order_service: AccountOrderService = Depends(get_account_order_service),
) -> OrderResponse:
    return account_order_service.get_order(user=current_user, order_id=order_id)


@router.get("/orders/{order_id}/timeline-sim", response_model=OrderTimelineResponse)
def get_order_timeline_sim(
    order_id: str,
    scenario_id: str = Query(default="default"),
    current_user: User = Depends(get_current_user),
    account_order_service: AccountOrderService = Depends(get_account_order_service),
) -> OrderTimelineResponse:
    return account_order_service.get_order_timeline_sim(
        user=current_user,
        order_id=order_id,
        scenario_id=scenario_id,
    )
