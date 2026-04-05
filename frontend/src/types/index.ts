// Type definitions for all API responses and requests

export interface User {
  user_id: string;
  email: string;
  is_guest: boolean;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface SessionState {
  authenticated: boolean;
  user_id: number;
  is_guest: boolean;
  is_active: boolean;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user_id?: number;
  guest_id?: number;
  is_guest: boolean;
}

export interface Order {
  order_id: string;
  user_id: string;
  status: string;
  status_label: string;
  created_at: string;
  eta_from?: string;
  eta_to?: string;
}

export interface OrderTimeline {
  order_id: string;
  current_status: string;
  timeline: Array<{
    date: string;
    event: string;
  }>;
}

export interface ConversationMessage {
  message_id: string;
  session_id: string;
  user_id: string;
  role: 'user' | 'assistant';
  text: string;
  created_at: string;
}

export interface FAQCitation {
  chunk_id: string;
  source_id: string;
  snippet: string;
  score: number;
}

export interface IntentResolveResponse {
  intent: string;
  confidence: number;
  route: 'faq_answer' | 'order_status' | 'refund' | 'account' | 'clarify' | 'escalate';
  requires_clarification: boolean;
  answer?: {
    text: string;
    retrieval_mode: 'deterministic' | 'rule_based' | 'llm_synthesis';
  };
  citations?: FAQCitation[];
  escalation_reason_code?: string;
  session_id: string;
}

export interface FAQSearchResponse {
  query: string;
  best_match?: FAQCitation;
  all_citations: FAQCitation[];
  session_id: string;
}

export interface RefundEligibilityResponse {
  eligible: boolean;
  reason: string;
  decision_reason_codes: string[];
}

export interface RefundRequest {
  refund_request_id: string;
  user_id: string;
  order_id: string;
  reason_code: string;
  status: string;
  status_reason?: string;
  idempotent_replay: boolean;
  created_at: string;
}

export interface OrderStateSim {
  order_id: string;
  fulfillment_state: string;
  payment_state: string;
  state_timeline: Array<{
    date: string;
    event: string;
  }>;
}

// Request types
export interface GuestAccessRequest {
  email: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface IntentResolveRequest {
  message: string;
  session_id: string;
}

export interface RefundCheckRequest {
  order_id: string;
}

export interface RefundCreateRequest {
  order_id: string;
  reason_code: string;
  simulation_scenario_id?: string;
}
