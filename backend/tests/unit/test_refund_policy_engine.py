from __future__ import annotations

from app.services.refund_policy_engine import RefundPolicyEngine
from app.schemas.refund import (
    RefundDecisionReasonCode,
    RefundPolicyVersion,
    RefundResolutionAction,
)


def test_policy_engine_is_deterministic_for_same_input() -> None:
    engine = RefundPolicyEngine()

    first = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=48,
        order_age_hours=2.0,
    )
    second = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=48,
        order_age_hours=2.0,
    )

    assert first == second


def test_policy_engine_denies_non_refundable_scenario() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="quality_issue",
        simulation_scenario_id="non-refundable",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=48,
        order_age_hours=1.0,
    )

    assert decision.eligible is False
    assert decision.resolution_action == RefundResolutionAction.DENY
    assert decision.decision_reason_codes == [RefundDecisionReasonCode.NON_REFUNDABLE_ITEM]
    assert decision.refundable_ratio == 0.0
    assert decision.explanation_template_key == "refund.scenario_hard_deny"
    assert decision.explanation_params["scenario_id"] == "non-refundable"


def test_policy_engine_partial_for_missing_item() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="missing_item",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=48,
        order_age_hours=3.0,
    )

    assert decision.eligible is True
    assert decision.resolution_action == RefundResolutionAction.APPROVE_PARTIAL
    assert decision.decision_reason_codes == [RefundDecisionReasonCode.ELIGIBLE_PARTIAL]
    assert decision.refundable_ratio == 0.5
    assert decision.explanation_template_key == "refund.reason_policy_outcome"
    assert decision.explanation_params["submitted_reason"] == "missing_item"
    assert decision.explanation_params["resolution_action"] == RefundResolutionAction.APPROVE_PARTIAL


def test_policy_engine_emits_policy_version_v1() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=48,
        order_age_hours=4.0,
    )

    assert decision.policy_version == RefundPolicyVersion.V1


def test_policy_engine_denies_when_order_age_exceeds_refund_window() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
        refund_window_hours=24,
        order_age_hours=49.0,
    )

    assert decision.eligible is False
    assert decision.resolution_action == RefundResolutionAction.DENY
    assert decision.decision_reason_codes == [RefundDecisionReasonCode.REFUND_WINDOW_EXPIRED]
    assert decision.explanation_template_key == "refund.refund_window_expired"
