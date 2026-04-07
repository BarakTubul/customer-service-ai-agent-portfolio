from __future__ import annotations

from dataclasses import dataclass

from app.schemas.refund import (
    RefundDecisionReasonCode,
    RefundPolicyVersion,
    RefundResolutionAction,
)
from app.services.refund_policy_matrix import (
    DEFAULT_UNSUPPORTED_REASON_POLICY,
    POLICY_REFERENCE,
    POLICY_VERSION,
    REASON_HARD_DENIAL_REASONS,
    REASON_POLICIES,
    SCENARIO_HARD_DENIAL_REASONS,
)


@dataclass(frozen=True)
class RefundPolicyDecision:
    eligible: bool
    resolution_action: RefundResolutionAction
    decision_reason_codes: list[RefundDecisionReasonCode]
    refundable_amount_value: float
    policy_version: RefundPolicyVersion = POLICY_VERSION
    policy_reference: str = POLICY_REFERENCE


class RefundPolicyEngine:
    def evaluate(
        self,
        *,
        reason_code: str,
        simulation_scenario_id: str,
        fulfillment_state: str,
        payment_state: str,
    ) -> RefundPolicyDecision:
        normalized_reason = reason_code.strip().lower()

        if payment_state != "captured":
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[RefundDecisionReasonCode.PAYMENT_NOT_CAPTURED],
                refundable_amount_value=0.0,
            )

        if simulation_scenario_id in SCENARIO_HARD_DENIAL_REASONS:
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[SCENARIO_HARD_DENIAL_REASONS[simulation_scenario_id]],
                refundable_amount_value=0.0,
            )

        if normalized_reason in REASON_HARD_DENIAL_REASONS:
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.MANUAL_REVIEW,
                decision_reason_codes=[REASON_HARD_DENIAL_REASONS[normalized_reason]],
                refundable_amount_value=0.0,
            )

        if fulfillment_state != "delivered":
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[RefundDecisionReasonCode.FULFILLMENT_NOT_COMPLETED],
                refundable_amount_value=0.0,
            )

        matched_policy = REASON_POLICIES.get(normalized_reason, DEFAULT_UNSUPPORTED_REASON_POLICY)
        return RefundPolicyDecision(
            eligible=matched_policy.eligible,
            resolution_action=matched_policy.resolution_action,
            decision_reason_codes=[matched_policy.reason_code],
            refundable_amount_value=matched_policy.refundable_amount_value,
        )
