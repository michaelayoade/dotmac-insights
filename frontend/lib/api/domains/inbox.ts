/**
 * Inbox Domain API Module
 *
 * Handles omnichannel inbox functionality including:
 * - Conversations management
 * - Contacts management
 * - Routing rules
 * - Analytics
 */

import { fetchApi } from '../core';

// Re-export types from inbox.types
export type {
  InboxConversation,
  InboxContact,
  InboxRoutingRule,
  InboxAnalyticsSummary,
  InboxVolumeData,
  InboxAgentStats,
  InboxChannelStats,
  InboxMessage,
  ConversationListParams,
  ConversationListResponse,
  ConversationUpdatePayload,
  AssignPayload,
  SendMessagePayload,
  CreateTicketPayload,
  CreateLeadPayload,
  ContactListParams,
  ContactListResponse,
  ContactCreatePayload,
  ContactUpdatePayload,
  RoutingRuleListParams,
  RoutingRuleListResponse,
  RoutingRuleCreatePayload,
  RoutingRuleUpdatePayload,
  CompanyListResponse,
} from '../../inbox.types';

import type {
  InboxConversation,
  InboxContact,
  InboxRoutingRule,
  InboxAnalyticsSummary,
  InboxVolumeData,
  InboxAgentStats,
  InboxChannelStats,
  InboxMessage,
  ConversationListParams,
  ConversationListResponse,
  ConversationUpdatePayload,
  AssignPayload,
  SendMessagePayload,
  CreateTicketPayload,
  CreateLeadPayload,
  ContactListParams,
  ContactListResponse,
  ContactCreatePayload,
  ContactUpdatePayload,
  RoutingRuleListParams,
  RoutingRuleListResponse,
  RoutingRuleCreatePayload,
  RoutingRuleUpdatePayload,
  CompanyListResponse,
} from '../../inbox.types';

// =============================================================================
// CONVERSATIONS
// =============================================================================

export const getInboxConversations = (params?: ConversationListParams) =>
  fetchApi<ConversationListResponse>('/inbox/conversations', { params: params as Record<string, any> | undefined });

export const getInboxConversation = (id: number) =>
  fetchApi<InboxConversation>(`/inbox/conversations/${id}`);

export const updateInboxConversation = (id: number, payload: ConversationUpdatePayload) =>
  fetchApi<InboxConversation>(`/inbox/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const assignInboxConversation = (id: number, payload: AssignPayload) =>
  fetchApi<InboxConversation>(`/inbox/conversations/${id}/assign`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const sendInboxMessage = (id: number, payload: SendMessagePayload) =>
  fetchApi<InboxMessage>(`/inbox/conversations/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const markInboxConversationRead = (id: number) =>
  fetchApi<InboxConversation>(`/inbox/conversations/${id}/mark-read`, { method: 'POST' });

export const createTicketFromConversation = (id: number, payload?: CreateTicketPayload) =>
  fetchApi<{ ticket_id: number; message: string }>(`/inbox/conversations/${id}/create-ticket`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  });

export const createLeadFromConversation = (id: number, payload?: CreateLeadPayload) =>
  fetchApi<{ lead_id: number; message: string }>(`/inbox/conversations/${id}/create-lead`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  });

export const archiveInboxConversation = (id: number) =>
  fetchApi<InboxConversation>(`/inbox/conversations/${id}/archive`, { method: 'POST' });

// =============================================================================
// CONTACTS
// =============================================================================

export const getInboxContacts = (params?: ContactListParams) =>
  fetchApi<ContactListResponse>('/inbox/contacts', { params: params as Record<string, any> | undefined });

export const getInboxContact = (id: number) =>
  fetchApi<InboxContact>(`/inbox/contacts/${id}`);

export const createInboxContact = (payload: ContactCreatePayload) =>
  fetchApi<InboxContact>('/inbox/contacts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const updateInboxContact = (id: number, payload: ContactUpdatePayload) =>
  fetchApi<InboxContact>(`/inbox/contacts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const deleteInboxContact = (id: number) =>
  fetchApi<void>(`/inbox/contacts/${id}`, { method: 'DELETE' });

export const getInboxCompanies = (params?: { search?: string; limit?: number; offset?: number }) =>
  fetchApi<CompanyListResponse>('/inbox/contacts/companies', { params });

// =============================================================================
// ROUTING RULES
// =============================================================================

export const getInboxRoutingRules = (params?: RoutingRuleListParams) =>
  fetchApi<RoutingRuleListResponse>('/inbox/routing-rules', { params: params as Record<string, any> | undefined });

export const getInboxRoutingRule = (id: number) =>
  fetchApi<InboxRoutingRule>(`/inbox/routing-rules/${id}`);

export const createInboxRoutingRule = (payload: RoutingRuleCreatePayload) =>
  fetchApi<InboxRoutingRule>('/inbox/routing-rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const updateInboxRoutingRule = (id: number, payload: RoutingRuleUpdatePayload) =>
  fetchApi<InboxRoutingRule>(`/inbox/routing-rules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const deleteInboxRoutingRule = (id: number) =>
  fetchApi<void>(`/inbox/routing-rules/${id}`, { method: 'DELETE' });

export const toggleInboxRoutingRule = (id: number) =>
  fetchApi<InboxRoutingRule>(`/inbox/routing-rules/${id}/toggle`, { method: 'POST' });

// =============================================================================
// ANALYTICS
// =============================================================================

export const getInboxAnalyticsSummary = (params?: { days?: number }) =>
  fetchApi<InboxAnalyticsSummary>('/inbox/analytics/summary', { params });

export const getInboxAnalyticsVolume = (params?: { days?: number }) =>
  fetchApi<InboxVolumeData>('/inbox/analytics/volume', { params });

export const getInboxAnalyticsAgents = (params?: { days?: number }) =>
  fetchApi<{ period_days: number; agents: InboxAgentStats[] }>('/inbox/analytics/agents', { params });

export const getInboxAnalyticsChannels = (params?: { days?: number }) =>
  fetchApi<{ period_days: number; channels: InboxChannelStats[] }>('/inbox/analytics/channels', { params });

// =============================================================================
// UNIFIED API OBJECT
// =============================================================================

export const inboxApi = {
  // Conversations
  getConversations: getInboxConversations,
  getConversation: getInboxConversation,
  updateConversation: updateInboxConversation,
  assignConversation: assignInboxConversation,
  sendMessage: sendInboxMessage,
  markConversationRead: markInboxConversationRead,
  createTicketFromConversation,
  createLeadFromConversation,
  archiveConversation: archiveInboxConversation,

  // Contacts
  getContacts: getInboxContacts,
  getContact: getInboxContact,
  createContact: createInboxContact,
  updateContact: updateInboxContact,
  deleteContact: deleteInboxContact,
  getCompanies: getInboxCompanies,

  // Routing Rules
  getRoutingRules: getInboxRoutingRules,
  getRoutingRule: getInboxRoutingRule,
  createRoutingRule: createInboxRoutingRule,
  updateRoutingRule: updateInboxRoutingRule,
  deleteRoutingRule: deleteInboxRoutingRule,
  toggleRoutingRule: toggleInboxRoutingRule,

  // Analytics
  getAnalyticsSummary: getInboxAnalyticsSummary,
  getAnalyticsVolume: getInboxAnalyticsVolume,
  getAnalyticsAgents: getInboxAnalyticsAgents,
  getAnalyticsChannels: getInboxAnalyticsChannels,

  // Legacy method names for backward compatibility
  getInboxConversations,
  getInboxConversation,
  updateInboxConversation,
  assignInboxConversation,
  sendInboxMessage,
  markInboxConversationRead,
  archiveInboxConversation,
  getInboxContacts,
  getInboxContact,
  createInboxContact,
  updateInboxContact,
  deleteInboxContact,
  getInboxCompanies,
  getInboxRoutingRules,
  getInboxRoutingRule,
  createInboxRoutingRule,
  updateInboxRoutingRule,
  deleteInboxRoutingRule,
  toggleInboxRoutingRule,
  getInboxAnalyticsSummary,
  getInboxAnalyticsVolume,
  getInboxAnalyticsAgents,
  getInboxAnalyticsChannels,
};
