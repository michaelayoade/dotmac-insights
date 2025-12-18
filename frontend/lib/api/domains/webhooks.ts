/**
 * Webhooks Domain API
 * Includes: Outbound webhooks, Inbound webhook events, OmniChannel webhooks
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export interface WebhookEvent {
  id: number;
  provider: string;
  event_type: string;
  idempotency_key: string;
  status: string;
  error_message?: string;
  created_at: string;
  processed_at?: string;
}

export interface WebhookEventListResponse {
  items: WebhookEvent[];
  limit: number;
  offset: number;
}

export interface WebhookEventDetail extends WebhookEvent {
  payload: Record<string, unknown>;
}

export interface Webhook {
  id: number;
  url: string;
  events: string[];
  is_active: boolean;
  secret?: string;
  created_at: string;
  updated_at?: string;
}

export interface WebhookCreatePayload {
  url: string;
  events: string[];
  is_active?: boolean;
}

export interface WebhookUpdatePayload {
  url?: string;
  events?: string[];
  is_active?: boolean;
}

export interface WebhookDelivery {
  id: number;
  webhook_id: number;
  event_type: string;
  status: string;
  response_code?: number;
  response_body?: string;
  error_message?: string;
  created_at: string;
  delivered_at?: string;
}

export interface WebhookDeliveryListResponse {
  items: WebhookDelivery[];
  limit: number;
  offset: number;
}

export interface WebhookProvider {
  name: string;
  label: string;
  description?: string;
  event_count?: number;
}

export interface WebhookProviderStats {
  provider: string;
  total_events: number;
  processed_events: number;
  failed_events: number;
  pending_events: number;
}

export interface OmniChannel {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  webhook_url?: string;
  secret?: string;
  created_at: string;
  updated_at?: string;
}

export interface OmniChannelStats {
  channel_id: number;
  total_events: number;
  processed_events: number;
  failed_events: number;
}

export interface OmniChannelWebhookEvent {
  id: number;
  channel_id: number;
  event_type: string;
  status: string;
  payload?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  processed_at?: string;
}

// =============================================================================
// OUTBOUND WEBHOOKS API
// =============================================================================

export const webhooksApi = {
  // -------------------------------------------------------------------------
  // Outbound Webhooks (notifications)
  // -------------------------------------------------------------------------

  /** List all outbound webhooks */
  listWebhooks: () =>
    fetchApi<Webhook[]>('/v1/notifications/webhooks'),

  /** Create a new webhook */
  createWebhook: (body: WebhookCreatePayload) =>
    fetchApi<Webhook>('/v1/notifications/webhooks', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Get a webhook by ID */
  getWebhook: (id: number | string) =>
    fetchApi<Webhook>(`/v1/notifications/webhooks/${id}`),

  /** Update a webhook */
  updateWebhook: (id: number | string, body: WebhookUpdatePayload) =>
    fetchApi<Webhook>(`/v1/notifications/webhooks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a webhook */
  deleteWebhook: (id: number | string) =>
    fetchApi<void>(`/v1/notifications/webhooks/${id}`, { method: 'DELETE' }),

  /** Test a webhook by sending a test event */
  testWebhook: (id: number | string) =>
    fetchApi<{ status: string }>(`/v1/notifications/webhooks/${id}/test`, {
      method: 'POST',
    }),

  /** Get delivery history for a webhook */
  getWebhookDeliveries: (
    id: number | string,
    params?: { status?: string; limit?: number; offset?: number }
  ) =>
    fetchApi<WebhookDeliveryListResponse>(
      `/v1/notifications/webhooks/${id}/deliveries`,
      { params }
    ),

  /** Get a specific delivery */
  getWebhookDelivery: (webhookId: number | string, deliveryId: number | string) =>
    fetchApi<WebhookDelivery>(
      `/v1/notifications/webhooks/${webhookId}/deliveries/${deliveryId}`
    ),

  /** Rotate the webhook secret */
  rotateWebhookSecret: (id: number | string) =>
    fetchApi<{ secret: string }>(`/v1/notifications/webhooks/${id}/rotate-secret`, {
      method: 'POST',
    }),

  /** Retry a failed delivery */
  retryWebhookDelivery: (deliveryId: number | string) =>
    fetchApi<{ status: string }>(
      `/v1/notifications/webhook-deliveries/${deliveryId}/retry`,
      { method: 'POST' }
    ),

  // -------------------------------------------------------------------------
  // Inbound Webhook Events (integrations)
  // -------------------------------------------------------------------------

  /** Get available webhook providers */
  getWebhookProviders: () =>
    fetchApi<{ providers: WebhookProvider[] }>('/integrations/webhooks/providers'),

  /** Get stats for a specific provider */
  getWebhookProviderStats: (name: string) =>
    fetchApi<WebhookProviderStats>(`/integrations/webhooks/providers/${name}/stats`),

  /** Get webhook events with optional filters */
  getWebhookEvents: (params?: {
    provider?: string;
    event_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<WebhookEventListResponse>('/integrations/webhooks/events', { params }),

  /** Get a specific webhook event with payload */
  getWebhookEvent: (id: number) =>
    fetchApi<WebhookEventDetail>(`/integrations/webhooks/events/${id}`),

  /** Replay a webhook event */
  replayWebhookEvent: (id: number) =>
    fetchApi<{ status: string }>(`/integrations/webhooks/events/${id}/replay`, {
      method: 'POST',
    }),

  // -------------------------------------------------------------------------
  // OmniChannel Webhooks
  // -------------------------------------------------------------------------

  /** List all omni channels */
  getOmniChannels: () => fetchApi<OmniChannel[]>('/omni/channels'),

  /** Get a specific omni channel */
  getOmniChannel: (id: number | string) =>
    fetchApi<OmniChannel>(`/omni/channels/${id}`),

  /** Get stats for an omni channel */
  getOmniChannelStats: (id: number | string) =>
    fetchApi<OmniChannelStats>(`/omni/channels/${id}/stats`),

  /** Get webhook events for an omni channel */
  getOmniChannelWebhookEvents: (id: number | string) =>
    fetchApi<OmniChannelWebhookEvent[]>(`/omni/channels/${id}/webhook-events`),

  /** Get a specific webhook event for an omni channel */
  getOmniChannelWebhookEvent: (id: number | string, eventId: number | string) =>
    fetchApi<OmniChannelWebhookEvent>(`/omni/channels/${id}/webhook-events/${eventId}`),

  /** Rotate the secret for an omni channel */
  rotateOmniChannelSecret: (id: number | string) =>
    fetchApi<{ secret: string }>(`/omni/channels/${id}/rotate-secret`, {
      method: 'POST',
    }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

export const listWebhooks = webhooksApi.listWebhooks;
export const createWebhook = webhooksApi.createWebhook;
export const getWebhook = webhooksApi.getWebhook;
export const updateWebhook = webhooksApi.updateWebhook;
export const deleteWebhook = webhooksApi.deleteWebhook;
export const testWebhook = webhooksApi.testWebhook;
export const getWebhookDeliveries = webhooksApi.getWebhookDeliveries;
export const getWebhookDelivery = webhooksApi.getWebhookDelivery;
export const rotateWebhookSecret = webhooksApi.rotateWebhookSecret;
export const retryWebhookDelivery = webhooksApi.retryWebhookDelivery;
export const getWebhookProviders = webhooksApi.getWebhookProviders;
export const getWebhookProviderStats = webhooksApi.getWebhookProviderStats;
export const getWebhookEvents = webhooksApi.getWebhookEvents;
export const getWebhookEvent = webhooksApi.getWebhookEvent;
export const replayWebhookEvent = webhooksApi.replayWebhookEvent;
export const getOmniChannels = webhooksApi.getOmniChannels;
export const getOmniChannel = webhooksApi.getOmniChannel;
export const getOmniChannelStats = webhooksApi.getOmniChannelStats;
export const getOmniChannelWebhookEvents = webhooksApi.getOmniChannelWebhookEvents;
export const getOmniChannelWebhookEvent = webhooksApi.getOmniChannelWebhookEvent;
export const rotateOmniChannelSecret = webhooksApi.rotateOmniChannelSecret;
