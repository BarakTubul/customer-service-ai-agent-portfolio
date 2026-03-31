from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ItemSelection(BaseModel):
    item_id: str
    quantity: int = Field(ge=1)


class RefundEligibilityCheckRequest(BaseModel):
    order_id: str
    reason_code: str
    item_selections: list[ItemSelection] = []
    simulation_scenario_id: str = "default"


class MoneyAmount(BaseModel):
    currency: str
    value: float


class RefundEligibilityCheckResponse(BaseModel):
    eligible: bool
    decision_reason_codes: list[str]
    policy_reference: str
    refundable_amount: MoneyAmount
    simulated_state: str


class RefundCreateRequest(BaseModel):
    order_id: str
    reason_code: str
    item_selections: list[ItemSelection] = []
    simulation_scenario_id: str = "default"


class RefundRequestResponse(BaseModel):
    refund_request_id: str
    order_id: str
    status: str
    status_reason: str | None
    created_at: datetime
    idempotent_replay: bool = False


class OrderStateSimResponse(BaseModel):
    order_id: str
    simulation_scenario_id: str
    fulfillment_state: str
    payment_state: str
    state_timeline: list[dict[str, str]]
