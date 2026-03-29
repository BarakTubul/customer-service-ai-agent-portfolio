# Feature: Guided Support Actions (Refund Eligibility & Request Intake)

## Goal
Help users complete common support actions by checking eligibility and capturing structured request details for downstream processing.

## Functional Requirements
- Identify refund-related requests and route non-refund actions to the relevant feature flow.
- Check refund eligibility based on policy and order state.
- Collect required information when missing (order ID, reason, item selection).
- Present clear eligibility outcome with reason when ineligible.
- For eligible cases, create a refund request record and return confirmation ID.
- Prevent duplicate submissions for the same order/item within a defined window.
- Use simulated order and delivery states as the required source for eligibility checks in MVP.
- Provide next-step expectations (timeline, status tracking method).

## Non-Functional Requirements (if applicable)
- Action decision latency: <= 4 seconds under normal load.
- Idempotency: duplicate request creation rate near zero for same input key.
- Accuracy: eligibility outcomes match policy engine rules consistently.
- Security: only authenticated users can submit requests tied to their orders.
- Compliance: store reason codes and decision basis for audit trail.

## Use Cases

### Happy Path
1. User says, "I want a refund for order 12345."
2. Bot validates authentication and order ownership.
3. Bot checks policy eligibility (window, item state, payment state).
4. Bot asks for missing reason and item details if needed.
5. Bot creates refund request and returns confirmation ID + expected timeline.

### Edge Cases
- Refund window expired.
  Bot explains ineligibility and suggests escalation path if user disagrees.
- Partial refund scenario with multiple items.
  Bot asks user to choose specific item(s) and quantity.
- Duplicate request detected.
  Bot returns existing request ID and current status instead of creating new one.
- Policy engine unavailable.
  Bot communicates temporary inability to process and offers escalation.

## API / Tool Interaction (if applicable)
- POST /api/v1/refunds/eligibility/check
- POST /api/v1/refunds/requests
- GET /api/v1/refunds/requests/{refundRequestId}
- GET /api/v1/orders/{orderId}/state-sim

## Data Considerations
- Required: user ID, order ID, requested item(s), reason code.
- Optional: free-text explanation, attachments metadata (if enabled later).
- Optional: simulation scenario ID used to replay deterministic test scenarios.
- Validation: ownership check, item existence in order, reason code whitelist.
- Constraints: enforce idempotency key; immutable request audit fields; no real card data is collected or processed.

## Acceptance Criteria
- Eligible requests produce a unique confirmation ID and stored request record.
- Ineligible requests provide policy-based reason and no request creation.
- Duplicate submissions return existing request reference without side effects.
- Missing required fields are collected through guided prompts.
- Refund outcomes remain deterministic for the same simulation scenario and input payload.
- Refund eligibility and request intake work end-to-end without any live restaurant/driver integration.
- Refund decisions use synthetic payment state only and never require real card information.
- All eligibility and submission events are audit-logged.

## Out of Scope
- Actual payment disbursement processing.
- Complex dispute workflows/chargeback management.
- Manual exception approval logic by bot.
- Generic order status retrieval.
- New order placement or checkout actions.

## Tasks
- Define action intent schema and slot requirements.
- Document eligibility rule inputs/outputs and decision handling.
- Specify request creation contract and idempotency strategy.
- Define simulation datasets for refundable, non-refundable, and partially refundable orders.
- Design guided prompt flow for missing data collection.
- Add audit/event model for decisions and submissions.
- Build end-to-end tests for eligible, ineligible, and duplicate paths.
