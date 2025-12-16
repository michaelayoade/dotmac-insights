/**
 * Inbox (Omnichannel) React Hooks
 *
 * SWR-based hooks for conversations, contacts, routing rules, and analytics.
 */

import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import { api } from '@/lib/api';
import type {
  InboxConversation,
  InboxContact,
  InboxRoutingRule,
  InboxAnalyticsSummary,
  InboxVolumeData,
  InboxAgentStats,
  InboxChannelStats,
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
} from '@/lib/inbox.types';

// =============================================================================
// CONVERSATIONS
// =============================================================================

export function useInboxConversations(
  params?: ConversationListParams,
  config?: SWRConfiguration
) {
  return useSWR<ConversationListResponse>(
    ['inbox-conversations', params],
    () => api.getInboxConversations(params),
    config
  );
}

export function useInboxConversation(id?: number, config?: SWRConfiguration) {
  const key = id ? (['inbox-conversation', id] as const) : null;
  return useSWR<InboxConversation>(
    key,
    key ? () => api.getInboxConversation(id!) : null,
    config
  );
}

export function useInboxConversationMutations() {
  const { mutate } = useSWRConfig();
  const invalidateList = () =>
    mutate((key) => Array.isArray(key) && key[0] === 'inbox-conversations');

  return {
    updateConversation: async (id: number, payload: ConversationUpdatePayload) => {
      const res = await api.updateInboxConversation(id, payload);
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    assignConversation: async (id: number, payload: AssignPayload) => {
      const res = await api.assignInboxConversation(id, payload);
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    sendMessage: async (id: number, payload: SendMessagePayload) => {
      const res = await api.sendInboxMessage(id, payload);
      await mutate(['inbox-conversation', id]);
      return res;
    },

    markRead: async (id: number) => {
      const res = await api.markInboxConversationRead(id);
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    createTicket: async (id: number, payload?: CreateTicketPayload) => {
      const res = await api.createTicketFromConversation(id, payload);
      await mutate(['inbox-conversation', id]);
      return res;
    },

    createLead: async (id: number, payload?: CreateLeadPayload) => {
      const res = await api.createLeadFromConversation(id, payload);
      await mutate(['inbox-conversation', id]);
      return res;
    },

    archive: async (id: number) => {
      const res = await api.archiveInboxConversation(id);
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    starConversation: async (id: number, isStarred: boolean) => {
      const res = await api.updateInboxConversation(id, { is_starred: isStarred });
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    setPriority: async (id: number, priority: 'low' | 'medium' | 'high' | 'urgent') => {
      const res = await api.updateInboxConversation(id, { priority });
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    setStatus: async (id: number, status: 'open' | 'pending' | 'resolved' | 'archived') => {
      const res = await api.updateInboxConversation(id, { status });
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    addTag: async (id: number, currentTags: string[], newTag: string) => {
      const tags = Array.from(new Set([...(currentTags || []), newTag]));
      const res = await api.updateInboxConversation(id, { tags });
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },

    removeTag: async (id: number, currentTags: string[], tagToRemove: string) => {
      const tags = (currentTags || []).filter((t) => t !== tagToRemove);
      const res = await api.updateInboxConversation(id, { tags });
      await invalidateList();
      await mutate(['inbox-conversation', id]);
      return res;
    },
  };
}

// =============================================================================
// CONTACTS
// =============================================================================

export function useInboxContacts(
  params?: ContactListParams,
  config?: SWRConfiguration
) {
  return useSWR<ContactListResponse>(
    ['inbox-contacts', params],
    () => api.getInboxContacts(params),
    config
  );
}

export function useInboxContact(id?: number, config?: SWRConfiguration) {
  const key = id ? (['inbox-contact', id] as const) : null;
  return useSWR<InboxContact>(
    key,
    key ? () => api.getInboxContact(id!) : null,
    config
  );
}

export function useInboxCompanies(
  params?: { search?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CompanyListResponse>(
    ['inbox-companies', params],
    () => api.getInboxCompanies(params),
    config
  );
}

export function useInboxContactMutations() {
  const { mutate } = useSWRConfig();
  const invalidateList = () =>
    mutate((key) => Array.isArray(key) && key[0] === 'inbox-contacts');

  return {
    createContact: async (payload: ContactCreatePayload) => {
      const res = await api.createInboxContact(payload);
      await invalidateList();
      return res;
    },

    updateContact: async (id: number, payload: ContactUpdatePayload) => {
      const res = await api.updateInboxContact(id, payload);
      await invalidateList();
      await mutate(['inbox-contact', id]);
      return res;
    },

    deleteContact: async (id: number) => {
      await api.deleteInboxContact(id);
      await invalidateList();
    },
  };
}

// =============================================================================
// ROUTING RULES
// =============================================================================

export function useInboxRoutingRules(
  params?: RoutingRuleListParams,
  config?: SWRConfiguration
) {
  return useSWR<RoutingRuleListResponse>(
    ['inbox-routing-rules', params],
    () => api.getInboxRoutingRules(params),
    config
  );
}

export function useInboxRoutingRule(id?: number, config?: SWRConfiguration) {
  const key = id ? (['inbox-routing-rule', id] as const) : null;
  return useSWR<InboxRoutingRule>(
    key,
    key ? () => api.getInboxRoutingRule(id!) : null,
    config
  );
}

export function useInboxRoutingRuleMutations() {
  const { mutate } = useSWRConfig();
  const invalidateList = () =>
    mutate((key) => Array.isArray(key) && key[0] === 'inbox-routing-rules');

  return {
    createRule: async (payload: RoutingRuleCreatePayload) => {
      const res = await api.createInboxRoutingRule(payload);
      await invalidateList();
      return res;
    },

    updateRule: async (id: number, payload: RoutingRuleUpdatePayload) => {
      const res = await api.updateInboxRoutingRule(id, payload);
      await invalidateList();
      await mutate(['inbox-routing-rule', id]);
      return res;
    },

    deleteRule: async (id: number) => {
      await api.deleteInboxRoutingRule(id);
      await invalidateList();
    },

    toggleRule: async (id: number) => {
      const res = await api.toggleInboxRoutingRule(id);
      await invalidateList();
      await mutate(['inbox-routing-rule', id]);
      return res;
    },
  };
}

// =============================================================================
// ANALYTICS
// =============================================================================

export function useInboxAnalyticsSummary(
  params?: { days?: number },
  config?: SWRConfiguration
) {
  return useSWR<InboxAnalyticsSummary>(
    ['inbox-analytics-summary', params],
    () => api.getInboxAnalyticsSummary(params),
    config
  );
}

export function useInboxAnalyticsVolume(
  params?: { days?: number },
  config?: SWRConfiguration
) {
  return useSWR<InboxVolumeData>(
    ['inbox-analytics-volume', params],
    () => api.getInboxAnalyticsVolume(params),
    config
  );
}

export function useInboxAnalyticsAgents(
  params?: { days?: number },
  config?: SWRConfiguration
) {
  return useSWR<{ period_days: number; agents: InboxAgentStats[] }>(
    ['inbox-analytics-agents', params],
    () => api.getInboxAnalyticsAgents(params),
    config
  );
}

export function useInboxAnalyticsChannels(
  params?: { days?: number },
  config?: SWRConfiguration
) {
  return useSWR<{ period_days: number; channels: InboxChannelStats[] }>(
    ['inbox-analytics-channels', params],
    () => api.getInboxAnalyticsChannels(params),
    config
  );
}
