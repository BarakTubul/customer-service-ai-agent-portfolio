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
    )
    second = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
    )

    assert first == second


def test_policy_engine_denies_non_refundable_scenario() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="quality_issue",
        simulation_scenario_id="non-refundable",
        fulfillment_state="delivered",
        payment_state="captured",
    )

    assert decision.eligible is False
    assert decision.resolution_action == RefundResolutionAction.DENY
    assert decision.decision_reason_codes == [RefundDecisionReasonCode.NON_REFUNDABLE_ITEM]
    assert decision.refundable_amount_value == 0.0


def test_policy_engine_partial_for_missing_item() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="missing_item",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
    )

    assert decision.eligible is True
    assert decision.resolution_action == RefundResolutionAction.APPROVE_PARTIAL
    assert decision.decision_reason_codes == [RefundDecisionReasonCode.ELIGIBLE_PARTIAL]
    assert decision.refundable_amount_value == 8.0


def test_policy_engine_emits_policy_version_v1() -> None:
    engine = RefundPolicyEngine()

    decision = engine.evaluate(
        reason_code="late_delivery",
        simulation_scenario_id="default",
        fulfillment_state="delivered",
        payment_state="captured",
    )

    assert decision.policy_version == RefundPolicyVersion.V1
