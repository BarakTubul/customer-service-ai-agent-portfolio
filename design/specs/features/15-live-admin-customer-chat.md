# Feature: Live Admin-Customer Chat

## Goal
Enable real-time two-way chat between customer and manager/admin after escalation, with durable message history, assignment workflow, and clear handoff from bot to human.

## Current Baseline
- Escalation requests can be detected in bot flow and queued through refund manual review logic.
- Existing websocket pattern is polling-style notifications, not room-based chat transport.
- Conversation storage exists as flat messages keyed by session_id, without live assignment state.

## Scope (MVP)
- Real-time text chat between one customer and one assigned admin per conversation.
- Admin queue/inbox for unassigned and assigned conversations.
- Claim, release, close conversation actions.
- Bot-to-human handoff creates or reuses a live conversation.
- Durable message persistence and replay on reconnect.

## Out of Scope (MVP)
- File attachments and media.
- Multi-admin group chat.
- External CRM/helpdesk integration.
- Voice/video.

## Data Model Changes

### New table: support_conversations
Fields:
- id (pk)
- conversation_id (string unique, public id)
- customer_user_id (fk users.id)
- source_session_id (string, nullable)
- status (enum: open, assigned, closed)
- priority (enum: normal, high)
- assigned_admin_user_id (fk users.id, nullable)
- escalation_reason_code (string, nullable)
- escalation_reference_id (string, nullable)
- created_at
- updated_at
- closed_at (nullable)

Indexes:
- status + created_at
- assigned_admin_user_id + status
- customer_user_id + created_at

### New table: support_messages
Fields:
- id (pk)
- message_id (string unique, public id)
- conversation_id (fk support_conversations.conversation_id)
- sender_user_id (fk users.id)
- sender_role (enum: customer, admin, system, bot)
- body (text)
- created_at
- delivered_at (nullable)
- read_at (nullable)

Indexes:
- conversation_id + created_at
- sender_user_id + created_at

### Optional table (Phase 2): support_participant_state
- conversation_id
- user_id
- is_typing
- last_seen_at
- is_online

## API Design

### Customer/Admin REST APIs
Base prefix: /api/v1/support

- POST /conversations
  - Create or reuse active conversation for customer.
  - Input: source_session_id?, escalation_reason_code?, priority?
  - Output: conversation summary.

- GET /conversations/{conversation_id}
  - Fetch single conversation metadata with assignment and status.

- GET /conversations/{conversation_id}/messages?after=<timestamp|message_id>&limit=50
  - Fetch history/replay.

- POST /conversations/{conversation_id}/messages
  - Server-side persisted send (fallback path if websocket unavailable).

### Admin-only APIs
- GET /admin/conversations/queue?status=open&limit=50
  - List unassigned conversations.

- GET /admin/conversations/assigned?limit=50
  - List conversations assigned to current admin.

- POST /admin/conversations/{conversation_id}/claim
  - Assign current admin if unassigned.

- POST /admin/conversations/{conversation_id}/release
  - Unassign (admin/system policy controlled).

- POST /admin/conversations/{conversation_id}/close
  - Close conversation.

### Handoff API integration
- Existing escalation flow should call support conversation upsert:
  - open or reuse conversation
  - add system summary message
  - include reference id returned to customer

## WebSocket Design

### Endpoint
- /api/v1/ws/support/{conversation_id}?token=<jwt>

### Authorization
- Customer can join only if customer_user_id matches token user.
- Admin can join if assigned or allowed by policy for open queue preview.
- Reject guest accounts unless explicitly supported.

### Event Envelope
{
  "type": "message.new|typing.start|typing.stop|receipt.read|conversation.assigned|conversation.closed|error",
  "conversation_id": "...",
  "payload": { ... },
  "timestamp": "ISO-8601"
}

### Message Send Event
Client -> server type: message.send
Payload:
- client_message_id
- body

Server behavior:
- validate auth and conversation state
- persist support_messages row
- broadcast message.new to room
- ack sender with canonical message_id

### Presence/Typing
- typing.start / typing.stop events broadcast only to other participant(s).
- read receipts update read_at and emit receipt.read.

## Backend Implementation Plan

### Phase 1: Persistence + APIs
1. Add models:
- backend/app/models/support_conversation.py
- backend/app/models/support_message.py

2. Add Alembic migration for new tables and indexes.

3. Add repository layer:
- backend/app/repositories/support_repository.py

4. Add service layer:
- backend/app/services/support_chat_service.py

5. Add route module:
- backend/app/api/routes/support.py

6. Register new router in API route init wiring.

### Phase 2: WebSocket live channel
1. Add websocket route in support router.
2. Implement in-memory connection manager first (single-instance MVP).
3. Persist before broadcast.
4. Add replay endpoint usage on reconnect.

### Phase 3: Handoff integration
1. In escalation intake path, create or reuse support conversation.
2. Add a system message with issue summary and order id.
3. Return conversation_id + reference_id in bot reply.

## Frontend Implementation Plan

### Customer UI
1. Add a dedicated live support page:
- frontend/src/pages/LiveSupportPage.tsx

2. Add websocket client utility:
- frontend/src/services/supportSocket.ts

3. Add REST client methods in:
- frontend/src/services/apiClient.ts

4. Route integration:
- frontend/src/App.tsx
  - path: /support/live/:conversationId

5. Bot handoff UX:
- when escalation acknowledged, show button/link to open live support conversation.

### Admin UI
1. Add support inbox page:
- frontend/src/pages/AdminSupportInboxPage.tsx

2. Add queue sections:
- Unassigned
- Assigned to me
- Active conversation panel

3. Add claim/release/close actions with optimistic updates.

4. Reuse existing admin route guard (is_admin) for MVP.

## Security and Policy
- Enforce RBAC on all admin endpoints.
- Validate conversation ownership for customer endpoints.
- Sanitize message text and cap length.
- Audit admin actions: claim/release/close/transfer.

## Observability
Track:
- handoff created count
- queue wait time
- first response time
- active chat duration
- close reason
- websocket disconnect/reconnect rates

## Testing Strategy

### Backend tests
- Unit tests for repository and service transitions.
- Integration tests for:
  - claim race conditions
  - unauthorized room access
  - send/receive ordering
  - replay after reconnect

### Frontend tests
- component tests for inbox state and message rendering
- websocket reconnect behavior
- role-based route protections

## Acceptance Criteria
1. Escalated customer can enter a live conversation and exchange messages with assigned admin in real time.
2. Admin can see open queue, claim conversation, and reply live.
3. Messages persist and reload correctly after refresh/reconnect.
4. Unauthorized users cannot access conversations they do not own or manage.
5. Bot escalation acknowledgment includes live conversation reference.

## Suggested Next Build Slice (1-2 days)
1. Build tables + repository + REST queue/claim APIs.
2. Build admin inbox page with polling REST (no websocket yet).
3. Wire escalation intake to create support conversation and show reference id.
4. Add websocket room only for active conversation page in next slice.
