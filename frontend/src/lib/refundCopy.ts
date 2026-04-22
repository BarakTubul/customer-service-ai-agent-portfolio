const REFUND_REASON_LABELS: Record<string, string> = {
  missing_item: 'Missing item',
  wrong_item: 'Wrong item received',
  late_delivery: 'Late delivery',
  quality_issue: 'Quality issue',
  fraud: 'Fraud concern',
  abuse: 'Abuse concern',
  other: 'Other',
};

const REFUND_STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  submitted: 'Submitted',
  denied: 'Denied',
  pending_manual_review: 'Waiting for review',
  resolved: 'Resolved',
};

const REFUND_RESOLUTION_LABELS: Record<string, string> = {
  approve_full: 'Approved in full',
  approve_partial: 'Approved partially',
  deny: 'Not approved',
  manual_review: 'Needs review',
};

const REFUND_DECISION_LABELS: Record<string, string> = {
  eligible: 'This looks eligible for a refund.',
  eligible_partial: 'Only part of this order is eligible for a refund.',
  outcome_mismatch: 'The issue selected does not match the order details.',
  payment_not_captured: 'We could not confirm that the payment was completed.',
  refund_window_expired: 'The refund window for this order has already closed.',
  non_refundable_item: 'This item is not refundable.',
  manual_review_required: 'This request needs a person to review it.',
  fulfillment_not_completed: 'This order is not completed yet, so we cannot process a refund now.',
  reason_code_not_supported: 'The reason selected is not supported for this order.',
};

const defaultLabel = (value: string): string => value.replace(/_/g, ' ');

export function formatRefundReasonLabel(value: string): string {
  return REFUND_REASON_LABELS[value] ?? defaultLabel(value);
}

export function formatRefundStatusLabel(value: string): string {
  return REFUND_STATUS_LABELS[value] ?? defaultLabel(value);
}

export function formatRefundResolutionLabel(value: string): string {
  return REFUND_RESOLUTION_LABELS[value] ?? defaultLabel(value);
}

export function formatRefundDecisionLabel(value: string): string {
  return REFUND_DECISION_LABELS[value] ?? defaultLabel(value);
}

export function formatRefundEligibilitySummary(
  eligible: boolean,
  reason: string,
  decisionReasonCodes: string[]
): string {
  const trimmedReason = reason.trim();
  const looksLikeCode = /^[a-z0-9_]+$/.test(trimmedReason) && trimmedReason.includes('_');

  if (trimmedReason && !looksLikeCode) {
    return reason;
  }

  if (trimmedReason && looksLikeCode) {
    return REFUND_DECISION_LABELS[trimmedReason] ?? defaultLabel(trimmedReason);
  }

  if (decisionReasonCodes.length > 0) {
    return decisionReasonCodes
      .map((code) => REFUND_DECISION_LABELS[code] ?? defaultLabel(code))
      .join(' ');
  }

  return eligible
    ? 'Good news, this order can be refunded.'
    : 'This order cannot be refunded right now.';
}
