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
    refundable_ratio: float
    explanation_template_key: str
    explanation_params: dict[str, str | int | float | bool]
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
        issue_code: str | None,
        is_delayed: bool,
        refund_window_hours: int,
        order_age_hours: float,
    ) -> RefundPolicyDecision:
        normalized_reason = reason_code.strip().lower()

        if payment_state != "captured":
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[RefundDecisionReasonCode.PAYMENT_NOT_CAPTURED],
                refundable_ratio=0.0,
                explanation_template_key="refund.payment_not_captured",
                explanation_params={"payment_state": payment_state},
            )

        if simulation_scenario_id in SCENARIO_HARD_DENIAL_REASONS:
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[SCENARIO_HARD_DENIAL_REASONS[simulation_scenario_id]],
                refundable_ratio=0.0,
                explanation_template_key="refund.scenario_hard_deny",
                explanation_params={
                    "scenario_id": simulation_scenario_id,
                    "decision_reason_code": SCENARIO_HARD_DENIAL_REASONS[simulation_scenario_id],
                },
            )

        if normalized_reason in REASON_HARD_DENIAL_REASONS:
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.MANUAL_REVIEW,
                decision_reason_codes=[REASON_HARD_DENIAL_REASONS[normalized_reason]],
                refundable_ratio=0.0,
                explanation_template_key="refund.manual_review_required",
                explanation_params={
                    "submitted_reason": normalized_reason,
                    "decision_reason_code": REASON_HARD_DENIAL_REASONS[normalized_reason],
                },
            )

        if fulfillment_state != "delivered":
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[RefundDecisionReasonCode.FULFILLMENT_NOT_COMPLETED],
                refundable_ratio=0.0,
                explanation_template_key="refund.fulfillment_not_completed",
                explanation_params={"fulfillment_state": fulfillment_state},
            )

        if order_age_hours > float(refund_window_hours):
            return RefundPolicyDecision(
                eligible=False,
                resolution_action=RefundResolutionAction.DENY,
                decision_reason_codes=[RefundDecisionReasonCode.REFUND_WINDOW_EXPIRED],
                refundable_ratio=0.0,
                explanation_template_key="refund.refund_window_expired",
                explanation_params={
                    "order_age_hours": round(order_age_hours, 2),
                    "refund_window_hours": refund_window_hours,
                },
            )

        expected_issue_by_reason = {
            "missing_item": "missing_item",
            "wrong_item": "wrong_item",
            "quality_issue": "quality_issue",
        }
        if normalized_reason == "late_delivery":
            if not is_delayed:
                return RefundPolicyDecision(
                    eligible=False,
                    resolution_action=RefundResolutionAction.DENY,
                    decision_reason_codes=[RefundDecisionReasonCode.OUTCOME_MISMATCH],
                    refundable_ratio=0.0,
                    explanation_template_key="refund.outcome_mismatch",
                    explanation_params={
                        "submitted_reason": normalized_reason,
                        "issue_code": issue_code or "none",
                        "is_delayed": is_delayed,
                    },
                )
        elif normalized_reason in expected_issue_by_reason:
            expected_issue = expected_issue_by_reason[normalized_reason]
            if issue_code != expected_issue:
                return RefundPolicyDecision(
                    eligible=False,
                    resolution_action=RefundResolutionAction.DENY,
                    decision_reason_codes=[RefundDecisionReasonCode.OUTCOME_MISMATCH],
                    refundable_ratio=0.0,
                    explanation_template_key="refund.outcome_mismatch",
                    explanation_params={
                        "submitted_reason": normalized_reason,
                        "issue_code": issue_code or "none",
                        "expected_issue": expected_issue,
                    },
                )

        matched_policy = REASON_POLICIES.get(normalized_reason, DEFAULT_UNSUPPORTED_REASON_POLICY)
        return RefundPolicyDecision(
            eligible=matched_policy.eligible,
            resolution_action=matched_policy.resolution_action,
            decision_reason_codes=[matched_policy.reason_code],
            refundable_ratio=matched_policy.refundable_ratio,
            explanation_template_key="refund.reason_policy_outcome",
            explanation_params={
                "submitted_reason": normalized_reason,
                "decision_reason_code": matched_policy.reason_code,
                "eligible": matched_policy.eligible,
                "resolution_action": matched_policy.resolution_action,
                "refund_ratio": matched_policy.refundable_ratio,
                "currency": "USD",
            },
        )
