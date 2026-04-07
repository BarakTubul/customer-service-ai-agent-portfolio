from __future__ import annotations

from dataclasses import dataclass

from app.schemas.refund import (
    RefundDecisionReasonCode,
    RefundPolicyVersion,
    RefundResolutionAction,
)

POLICY_REFERENCE = "refund-policy-v1"
POLICY_VERSION = RefundPolicyVersion.V1

# High-priority hard denials.
SCENARIO_HARD_DENIAL_REASONS: dict[str, RefundDecisionReasonCode] = {
    "expired-window": RefundDecisionReasonCode.REFUND_WINDOW_EXPIRED,
    "non-refundable": RefundDecisionReasonCode.NON_REFUNDABLE_ITEM,
}

REASON_HARD_DENIAL_REASONS: dict[str, RefundDecisionReasonCode] = {
    "fraud": RefundDecisionReasonCode.MANUAL_REVIEW_REQUIRED,
    "abuse": RefundDecisionReasonCode.MANUAL_REVIEW_REQUIRED,
}


@dataclass(frozen=True)
class ReasonPolicy:
    eligible: bool
    resolution_action: RefundResolutionAction
    reason_code: RefundDecisionReasonCode
    refundable_amount_value: float


REASON_POLICIES: dict[str, ReasonPolicy] = {
    "missing_item": ReasonPolicy(
        eligible=True,
        resolution_action=RefundResolutionAction.APPROVE_PARTIAL,
        reason_code=RefundDecisionReasonCode.ELIGIBLE_PARTIAL,
        refundable_amount_value=8.0,
    ),
    "wrong_item": ReasonPolicy(
        eligible=True,
        resolution_action=RefundResolutionAction.APPROVE_PARTIAL,
        reason_code=RefundDecisionReasonCode.ELIGIBLE_PARTIAL,
        refundable_amount_value=8.0,
    ),
    "late_delivery": ReasonPolicy(
        eligible=True,
        resolution_action=RefundResolutionAction.APPROVE_FULL,
        reason_code=RefundDecisionReasonCode.ELIGIBLE,
        refundable_amount_value=12.5,
    ),
    "quality_issue": ReasonPolicy(
        eligible=True,
        resolution_action=RefundResolutionAction.APPROVE_FULL,
        reason_code=RefundDecisionReasonCode.ELIGIBLE,
        refundable_amount_value=12.5,
    ),
}

DEFAULT_UNSUPPORTED_REASON_POLICY = ReasonPolicy(
    eligible=False,
    resolution_action=RefundResolutionAction.DENY,
    reason_code=RefundDecisionReasonCode.REASON_CODE_NOT_SUPPORTED,
    refundable_amount_value=0.0,
)
