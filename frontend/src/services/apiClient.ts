import axios, { AxiosInstance } from 'axios';
import * as t from '@/types';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').trim();
const API_PREFIX = (import.meta.env.VITE_API_PREFIX || '/api/v1').trim();
const hasVersionedPrefix = /\/api\/v\d+\/?$/.test(API_ORIGIN);
const API_BASE_URL = hasVersionedPrefix
  ? API_ORIGIN.replace(/\/+$/, '')
  : `${API_ORIGIN.replace(/\/+$/, '')}/${API_PREFIX.replace(/^\/+/, '')}`;

function stringifyErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }
  if (detail && typeof detail === 'object') {
    return JSON.stringify(detail);
  }
  return '';
}

function formatAxiosError(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return 'Unexpected client error';
  }

  const status = error.response?.status;
  const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
  const detailMessage = stringifyErrorDetail(data?.detail ?? data?.message);

  if (status && status >= 400 && status < 500) {
    return detailMessage
      ? `Client error (${status}): ${detailMessage}`
      : `Client error (${status}): Please verify your input and try again.`;
  }

  if (status && status >= 500) {
    return detailMessage
      ? `Server error (${status}): ${detailMessage}`
      : `Server error (${status}): Please try again later.`;
  }

  return detailMessage || error.message || 'Request failed';
}

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use((config) => {
      const method = (config.method || 'GET').toUpperCase();
      console.debug(`[api] request ${method} ${config.baseURL || ''}${config.url || ''}`, {
        withCredentials: config.withCredentials ?? false,
      });
      return config;
    });

    this.client.interceptors.response.use(
      (response) => {
        const method = (response.config.method || 'GET').toUpperCase();
        console.debug(
          `[api] response ${response.status} ${method} ${response.config.url || ''}`
        );
        return response;
      },
      (error) => {
        const formatted = formatAxiosError(error);
        if (axios.isAxiosError(error)) {
          console.error('[api] axios error', {
            message: error.message,
            method: (error.config?.method || 'GET').toUpperCase(),
            url: `${error.config?.baseURL || ''}${error.config?.url || ''}`,
            status: error.response?.status,
            response: error.response?.data,
            formatted,
          });
        } else {
          console.error('[api] unexpected client error', error);
        }
        return Promise.reject(new Error(formatted));
      }
    );
  }

  // Auth endpoints
  async guestAccess(email: string): Promise<t.AuthTokenResponse> {
    const response = await this.client.post<t.AuthTokenResponse>('/auth/guest', { email });
    return response.data;
  }

  async register(email: string, password: string): Promise<t.AuthTokenResponse> {
    const response = await this.client.post<t.AuthTokenResponse>('/auth/register', {
      email,
      password,
    });
    return response.data;
  }

  async login(email: string, password: string): Promise<t.AuthTokenResponse> {
    const response = await this.client.post<t.AuthTokenResponse>('/auth/login', {
      email,
      password,
    });
    return response.data;
  }

  async convertGuestToRegistered(password: string): Promise<t.AuthTokenResponse> {
    const response = await this.client.post<t.AuthTokenResponse>('/auth/guest/convert', {
      password,
    });
    return response.data;
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout');
  }

  // Account endpoints
  async getSessionState(): Promise<t.SessionState> {
    const response = await this.client.get<t.SessionState>('/auth/session');
    return response.data;
  }

  async getAccountMe(): Promise<t.AccountMeResponse> {
    const response = await this.client.get<t.AccountMeResponse>('/account/me');
    return response.data;
  }

  // Order endpoints
  async getUserOrders(): Promise<t.Order[]> {
    const response = await this.client.get<t.Order[]>('/orders');
    return response.data;
  }

  async getOrderDetail(orderId: string): Promise<t.Order> {
    const response = await this.client.get<t.Order>(`/orders/${orderId}`);
    return response.data;
  }

  async getOrderTimeline(orderId: string): Promise<t.OrderTimeline> {
    const response = await this.client.get<{
      order_id: string;
      scenario_id: string;
      events: Array<{ event: string; timestamp: string; source: string }>;
    }>(`/orders/${orderId}/timeline-sim`);

    const filteredEvents = response.data.events.filter((event) => event.event !== 'status_snapshot');

    const timeline = filteredEvents.map((event) => ({
      date: new Date(event.timestamp).toLocaleString(),
      event: event.event,
    }));

    return {
      order_id: response.data.order_id,
      current_status:
        filteredEvents.length > 0
          ? filteredEvents[filteredEvents.length - 1].event
          : 'unknown',
      timeline,
    };
  }

  // Intent & FAQ endpoints
  async resolveIntent(message: string, sessionId: string): Promise<t.IntentResolveResponse> {
    const response = await this.client.post<t.IntentResolveResponse>('/intent/resolve', {
      message,
      session_id: sessionId,
    });
    return response.data;
  }

  async searchFAQ(query: string, sessionId: string): Promise<t.FAQSearchResponse> {
    const response = await this.client.post<t.FAQSearchResponse>('/faq/search', {
      query,
      session_id: sessionId,
    });
    return response.data;
  }

  async getConversationContext(sessionId: string): Promise<t.ConversationMessage[]> {
    const response = await this.client.get<t.ConversationMessage[]>(
      `/conversations/${sessionId}/context`
    );
    return response.data;
  }

  // Refund endpoints
  async checkRefundEligibility(orderId: string): Promise<t.RefundEligibilityResponse> {
    const response = await this.client.post<t.RefundEligibilityResponse>(
      '/refunds/eligibility/check',
      { order_id: orderId }
    );
    return response.data;
  }

  async createRefundRequest(
    orderId: string,
    reasonCode: string,
    idempotencyKey?: string
  ): Promise<{ refund_request: t.RefundRequest; status_code: number }> {
    const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {};
    const response = await this.client.post<t.RefundRequest>(
      '/refunds/requests',
      {
        order_id: orderId,
        reason_code: reasonCode,
      },
      { headers }
    );
    return {
      refund_request: response.data,
      status_code: response.status,
    };
  }

  async getRefundRequest(refundRequestId: string): Promise<t.RefundRequest> {
    const response = await this.client.get<t.RefundRequest>(
      `/refunds/requests/${refundRequestId}`
    );
    return response.data;
  }

  async getOrderStateSim(orderId: string): Promise<t.OrderStateSim> {
    const response = await this.client.get<t.OrderStateSim>(`/orders/${orderId}/state-sim`);
    return response.data;
  }

  // Order placement endpoints
  async getCatalogItems(params: t.CatalogQueryParams): Promise<t.CatalogListResponse> {
    const response = await this.client.get<t.CatalogListResponse>('/catalog/items', {
      params: {
        page: params.page,
        page_size: params.page_size,
        search: params.search || undefined,
        restaurant: params.restaurant || undefined,
        cuisine: params.cuisine || undefined,
        availability: params.availability || 'all',
        sort_by: params.sort_by || 'featured',
      },
    });
    return response.data;
  }

  async getCart(): Promise<t.CartResponse> {
    const response = await this.client.get<t.CartResponse>('/cart');
    return response.data;
  }

  async addCartItem(itemId: string, quantity = 1): Promise<t.CartResponse> {
    const response = await this.client.post<t.CartResponse>('/cart/items', {
      item_id: itemId,
      quantity,
    });
    return response.data;
  }

  async updateCartItem(itemId: string, quantity: number): Promise<t.CartResponse> {
    const response = await this.client.patch<t.CartResponse>(`/cart/items/${itemId}`, {
      quantity,
    });
    return response.data;
  }

  async removeCartItem(itemId: string): Promise<t.CartResponse> {
    const response = await this.client.delete<t.CartResponse>(`/cart/items/${itemId}`);
    return response.data;
  }

  async validateCheckout(payload: t.CheckoutValidateRequest): Promise<t.CheckoutValidateResponse> {
    const response = await this.client.post<t.CheckoutValidateResponse>('/checkout/validate', payload);
    return response.data;
  }

  async authorizePaymentSim(
    payload: t.PaymentAuthorizeSimRequest
  ): Promise<t.PaymentAuthorizeSimResponse> {
    const response = await this.client.post<t.PaymentAuthorizeSimResponse>(
      '/payments/authorize-sim',
      payload
    );
    return response.data;
  }

  async createOrder(
    payload: t.OrderCreateRequest,
    idempotencyKey?: string
  ): Promise<t.OrderCreateResponse> {
    const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {};
    const response = await this.client.post<t.OrderCreateResponse>('/orders', payload, { headers });
    return response.data;
  }

  async getOrderLifecycleSim(orderId: string, scenarioId = 'default') {
    const response = await this.client.get(`/orders/${orderId}/lifecycle-sim`, {
      params: { scenario_id: scenarioId },
    });
    return response.data;
  }
}

export const apiClient = new APIClient();
