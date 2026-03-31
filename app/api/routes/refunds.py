from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.api.dependencies import get_current_user, get_refund_service
from app.models.user import User
from app.schemas.refund import (
    OrderStateSimResponse,
    RefundCreateRequest,
    RefundEligibilityCheckRequest,
    RefundEligibilityCheckResponse,
    RefundRequestResponse,
)
from app.services.refund_service import RefundService

router = APIRouter()


@router.post("/refunds/eligibility/check", response_model=RefundEligibilityCheckResponse)
def check_refund_eligibility(
    payload: RefundEligibilityCheckRequest,
    current_user: User = Depends(get_current_user),
    refund_service: RefundService = Depends(get_refund_service),
) -> RefundEligibilityCheckResponse:
    return refund_service.check_eligibility(user=current_user, payload=payload)


@router.post("/refunds/requests", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED)
def create_refund_request(
    payload: RefundCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    refund_service: RefundService = Depends(get_refund_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RefundRequestResponse:
    result = refund_service.create_request(
        user=current_user,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    if result.idempotent_replay:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/refunds/requests/{refund_request_id}", response_model=RefundRequestResponse)
def get_refund_request(
    refund_request_id: str,
    current_user: User = Depends(get_current_user),
    refund_service: RefundService = Depends(get_refund_service),
) -> RefundRequestResponse:
    return refund_service.get_request(user=current_user, refund_request_id=refund_request_id)


@router.get("/orders/{order_id}/state-sim", response_model=OrderStateSimResponse)
def get_order_state_sim(
    order_id: str,
    scenario_id: str = Query(default="default"),
    current_user: User = Depends(get_current_user),
    refund_service: RefundService = Depends(get_refund_service),
) -> OrderStateSimResponse:
    return refund_service.get_order_state_sim(user=current_user, order_id=order_id, scenario_id=scenario_id)
