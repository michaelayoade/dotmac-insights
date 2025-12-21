import { useState } from 'react';
import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import {
  accountingApi,
  adminApi,
  analyticsApi,
  apiFetch,
  ApiError,
  assetsApi,
  customersApi,
  documentsApi,
  expensesApi,
  fieldServiceApi,
  financeApi,
  fleetApi,
  hrApi,
  inboxApi,
  inventoryApi,
  insightsApi,
  paymentsApi,
  projectsApi,
  purchasingApi,
  supportApi,
  webhooksApi,
  fetchApi,
  InventoryItemPayload,
  InventoryWarehousePayload,
  InventoryStockEntryPayload,
  CustomerWritePayload,
  CustomerSubscriptionPayload,
  CustomerInvoicePayload,
  CustomerPaymentPayload,
  ReportsRevenueTrendPoint,
  ReportsExpenseTrendPoint,
  ReportsProfitabilityTrendPoint,
  ReportsCashPositionForecastPoint,
  PurchasingBillPayload,
  PurchasingOrderPayload,
  PurchasingDebitNotePayload,
  SupportTeamPayload,
  SupportTeamMemberPayload,
  SupportTicketCommentPayload,
  SupportTicketActivityPayload,
  SupportTicketDependencyPayload,
  SupportTicketCommunicationPayload,
  SupportTicketAssigneePayload,
  SupportTicketPayload,
  SupportTicketSlaPayload,
  SupportOverviewRequest,
  ProjectPayload,
  ProjectPriority,
  SupportAgentPayload,
  HrLeaveApplicationPayload,
  HrAttendancePayload,
  HrInterviewPayload,
  HrTrainingEventPayload,
  HrTrainingResultPayload,
  HrJobOpeningPayload,
  AccountingGeneralLedgerResponse,
  AccountingBankTransactionListResponse,
  AccountingBankTransactionDetail,
  PurchasingSupplierDetail,
} from '@/lib/api';
import { crmApi, dashboardsApi } from '@/lib/api/domains';

type ApiGroup = Record<string, (...args: any[]) => any>;

function withDomainPrefix(apiGroup: ApiGroup, prefix: string): ApiGroup {
  return Object.fromEntries(
    Object.entries(apiGroup).map(([key, value]) => {
      const firstUpper = key.search(/[A-Z]/);
      const base = firstUpper > 0 ? key.slice(0, firstUpper) : key;
      const rest = firstUpper > 0 ? key.slice(firstUpper) : '';
      return [`${base}${prefix}${rest}`, value];
    })
  ) as ApiGroup;
}

const api: ApiGroup = {
  ...supportApi,
  ...withDomainPrefix(supportApi, 'Support'),
  ...customersApi,
  ...withDomainPrefix(customersApi, 'Customer'),
  ...financeApi,
  ...withDomainPrefix(financeApi, 'Finance'),
  ...purchasingApi,
  ...withDomainPrefix(purchasingApi, 'Purchasing'),
  ...accountingApi,
  ...withDomainPrefix(accountingApi, 'Accounting'),
  ...inventoryApi,
  ...withDomainPrefix(inventoryApi, 'Inventory'),
  ...hrApi,
  ...withDomainPrefix(hrApi, 'Hr'),
  ...fleetApi,
  ...withDomainPrefix(fleetApi, 'Fleet'),
  ...analyticsApi,
  ...withDomainPrefix(analyticsApi, 'Reports'),
  ...insightsApi,
  ...projectsApi,
  ...crmApi,
  ...assetsApi,
  ...paymentsApi,
  ...fieldServiceApi,
  ...webhooksApi,
  ...documentsApi,
  ...inboxApi,
  ...expensesApi,
  ...adminApi,
  // Legacy analytics endpoints not yet mapped to domain modules
  getOverview: (currency?: string) =>
    fetchApi<import('@/lib/api').OverviewData>('/analytics/overview', {
      params: { currency },
    }),
  getRevenueTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<import('@/lib/api').RevenueTrend[]>('/analytics/revenue/trend', {
      params: { months, start_date: startDate, end_date: endDate },
    }),
  getChurnTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<import('@/lib/api').ChurnTrend[]>('/analytics/churn/trend', {
      params: { months, start_date: startDate, end_date: endDate },
    }),
  getPopPerformance: (currency?: string) =>
    fetchApi<import('@/lib/api').PopPerformance[]>('/analytics/pop/performance', {
      params: { currency },
    }),
  getInvoiceAging: () => fetchApi<import('@/lib/api').InvoiceAging>('/analytics/invoices/aging'),
  getPlanDistribution: (currency?: string) =>
    fetchApi<import('@/lib/api').PlanDistribution[]>('/analytics/customers/by-plan', {
      params: { currency },
    }),
  getDSOTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<import('@/lib/api').DSOTrend>('/analytics/revenue/dso', {
      params: { months, start_date: startDate, end_date: endDate },
    }),
  getRevenueByTerritory: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<import('@/lib/api').TerritoryRevenue[]>('/analytics/revenue/by-territory', {
      params: { months, start_date: startDate, end_date: endDate },
    }),
  getRevenueCohort: () => fetchApi<import('@/lib/api').CohortData>('/analytics/revenue/cohort'),
  getAgingBySegment: () => fetchApi<import('@/lib/api').AgingBySegment>('/analytics/collections/aging-by-segment'),
  getSalesPipeline: () => fetchApi<import('@/lib/api').SalesPipeline>('/analytics/sales/pipeline'),
  getTicketsByType: (days = 30) =>
    fetchApi<import('@/lib/api').TicketsByType>('/analytics/support/by-type', { params: { days } }),
  getNetworkDeviceStatus: () => fetchApi<import('@/lib/api').NetworkDeviceStatus>('/analytics/network/device-status'),
  getIPUtilization: () => fetchApi<import('@/lib/api').IPUtilization>('/analytics/network/ip-utilization'),
};

// Generic fetcher for SWR
export function useOverview(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['overview', currency],
    () => api.getOverview(currency),
    {
      refreshInterval: 60000, // Refresh every minute
      ...config,
    }
  );
}

export function useRevenueTrend(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['revenue-trend', months, startDate, endDate],
    () => api.getRevenueTrend(months, startDate, endDate),
    config
  );
}

export function useChurnTrend(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['churn-trend', months, startDate, endDate],
    () => api.getChurnTrend(months, startDate, endDate),
    config
  );
}

export function usePopPerformance(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['pop-performance', currency],
    () => api.getPopPerformance(currency),
    config
  );
}

export function useSupportMetrics(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['support-metrics', days],
    () => api.getSupportMetrics(days),
    config
  );
}

export function useSupportTicketDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['support-ticket-detail', id] as const : null,
    ([, ticketId]) => api.getSupportTicketDetail(ticketId),
    config
  );
}

export function useSupportOverview(params?: SupportOverviewRequest, config?: SWRConfiguration) {
  return useSWR(['support-overview', params], () => api.getSupportOverview(params), config);
}

export function useSupportDashboard(config?: SWRConfiguration) {
  return useSWR('support-dashboard', () => api.getSupportDashboard(), config);
}

export function useSupportTickets(
  params?: {
    start?: string;
    end?: string;
    team_id?: number;
    agent?: string;
    ticket_type?: string;
    priority?: 'low' | 'medium' | 'high' | 'urgent';
    status?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(['support-tickets', params], () => api.getSupportTickets(params), config);
}

export function useSupportTicketMutations() {
  const { mutate } = useSWRConfig();
  return {
    createTicket: async (payload: SupportTicketPayload) => {
      const res = await api.createSupportTicket(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-ticket-detail');
      return res;
    },
    updateTicket: async (id: number | string, payload: Partial<SupportTicketPayload>) => {
      const res = await api.updateSupportTicket(id, payload);
      await mutate(['support-ticket-detail', id]);
      return res;
    },
    deleteTicket: async (id: number | string) => {
      await api.deleteSupportTicket(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-ticket-detail');
    },
    assignTicket: async (id: number | string, payload: SupportTicketAssigneePayload) => {
      const res = await api.assignSupportTicket(id, payload);
      await mutate(['support-ticket-detail', id]);
      return res;
    },
    overrideSla: async (id: number | string, payload: SupportTicketSlaPayload) => {
      const res = await api.overrideSupportTicketSla(id, payload);
      await mutate(['support-ticket-detail', id]);
      return res;
    },
  };
}

export function useSupportTeams(config?: SWRConfiguration) {
  return useSWR('support-teams', () => api.getSupportTeams(), config);
}

// Extended Support
export function useSupportAutomationRules(params?: { trigger?: string; active_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-automation-rules', params], () => api.getSupportAutomationRules(params), config);
}

export function useSupportAutomationLogs(params?: { rule_id?: number; ticket_id?: number; trigger?: string; success?: boolean; days?: number; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['support-automation-logs', params], () => api.getSupportAutomationLogs(params), config);
}

export function useSupportAutomationLogsSummary(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-automation-logs-summary', params], () => api.getSupportAutomationLogsSummary(params), config);
}

export function useSupportSlaCalendars(params?: { active_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-sla-calendars', params], () => api.getSupportSlaCalendars(params), config);
}

export function useSupportSlaPolicies(params?: { active_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-sla-policies', params], () => api.getSupportSlaPolicies(params), config);
}

export function useSupportSlaBreachesSummary(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-sla-breach-summary', params], () => api.getSupportSlaBreachesSummary(params), config);
}

export function useSupportRoutingRules(params?: { team_id?: number; active_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-routing-rules', params], () => api.getSupportRoutingRules(params), config);
}

export function useSupportRoutingQueueHealth(config?: SWRConfiguration) {
  return useSWR(['support-routing-queue-health'], () => api.getSupportRoutingQueueHealth(), config);
}

export function useSupportRoutingWorkload(teamId?: number, config?: SWRConfiguration) {
  return useSWR(['support-routing-workload', teamId], () => api.getSupportRoutingWorkload(teamId), config);
}

export function useSupportKbCategories(params?: { parent_id?: number; include_inactive?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-kb-categories', params], () => api.getSupportKbCategories(params), config);
}

export function useSupportKbArticles(params?: { category_id?: number; status?: string; visibility?: string; search?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['support-kb-articles', params], () => api.getSupportKbArticles(params), config);
}

export function useSupportCannedResponses(params?: { scope?: string; category?: string; team_id?: number; search?: string; include_inactive?: boolean; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['support-canned', params], () => api.getSupportCannedResponses(params), config);
}

export function useSupportCannedCategories(config?: SWRConfiguration) {
  return useSWR(['support-canned-categories'], () => api.getSupportCannedCategories(), config);
}

export function useSupportCsatSurveys(params?: { active_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['support-csat-surveys', params], () => api.getSupportCsatSurveys(params), config);
}

export function useSupportCsatSummary(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-csat-summary', params], () => api.getSupportCsatSummary(params), config);
}

export function useSupportCsatAgentPerformance(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-csat-agents', params], () => api.getSupportCsatAgentPerformance(params), config);
}

export function useSupportCsatTrends(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR(['support-csat-trends', params], () => api.getSupportCsatTrends(params), config);
}

// Support Analytics & Insights Hooks
export function useSupportAnalyticsVolumeTrend(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR(['support-analytics-volume-trend', params], () => api.getSupportAnalyticsVolumeTrend(params), config);
}

export function useSupportAnalyticsResolutionTime(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR(['support-analytics-resolution-time', params], () => api.getSupportAnalyticsResolutionTime(params), config);
}

export function useSupportAnalyticsByCategory(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-analytics-by-category', params], () => api.getSupportAnalyticsByCategory(params), config);
}

export function useSupportAnalyticsSlaPerformance(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR(['support-analytics-sla-performance', params], () => api.getSupportAnalyticsSlaPerformance(params), config);
}

export function useSupportInsightsPatterns(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-insights-patterns', params], () => api.getSupportInsightsPatterns(params), config);
}

export function useSupportInsightsAgentPerformance(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['support-insights-agent-performance', params], () => api.getSupportInsightsAgentPerformance(params), config);
}

export function useSupportAgents(teamId?: number, domain?: string, config?: SWRConfiguration) {
  return useSWR(['support-agents', teamId, domain], () => api.getSupportAgents(teamId, domain), config);
}

export function useSupportTeamMutations() {
  const { mutate } = useSWRConfig();
  return {
    createTeam: async (payload: SupportTeamPayload & { team_name: string }) => {
      const res = await api.createSupportTeam(payload);
      await mutate('support-teams');
      return res;
    },
    updateTeam: async (id: number, payload: SupportTeamPayload) => {
      const res = await api.updateSupportTeam(id, payload);
      await mutate('support-teams');
      return res;
    },
    deleteTeam: async (id: number) => {
      await api.deleteSupportTeam(id);
      await mutate('support-teams');
    },
    addMember: async (teamId: number, payload: SupportTeamMemberPayload) => {
      const res = await api.addSupportTeamMember(teamId, payload);
      await mutate('support-teams');
      await mutate(['support-agents', teamId]);
      return res;
    },
    deleteMember: async (teamId: number, memberId: number) => {
      await api.deleteSupportTeamMember(teamId, memberId);
      await mutate('support-teams');
      await mutate(['support-agents', teamId]);
    },
  };
}

export function useSupportAgentMutations() {
  const { mutate } = useSWRConfig();
  return {
    createAgent: async (payload: SupportAgentPayload) => {
      const res = await api.createSupportAgent(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-agents');
      return res;
    },
    updateAgent: async (id: number, payload: SupportAgentPayload) => {
      const res = await api.updateSupportAgent(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-agents');
      return res;
    },
    deleteAgent: async (id: number) => {
      await api.deleteSupportAgent(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-agents');
    },
  };
}

export function useSupportTicketCommentMutations(ticketId: number | string | null) {
  const { mutate } = useSWRConfig();
  return {
    addComment: async (payload: SupportTicketCommentPayload) => {
      if (ticketId == null) return;
      const res = await api.createSupportTicketComment(ticketId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    updateComment: async (commentId: number, payload: SupportTicketCommentPayload) => {
      if (ticketId == null) return;
      const res = await api.updateSupportTicketComment(ticketId, commentId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    deleteComment: async (commentId: number) => {
      if (ticketId == null) return;
      await api.deleteSupportTicketComment(ticketId, commentId);
      await mutate(['support-ticket-detail', ticketId]);
    },
  };
}

export function useSupportTicketActivityMutations(ticketId: number | string | null) {
  const { mutate } = useSWRConfig();
  return {
    addActivity: async (payload: SupportTicketActivityPayload) => {
      if (ticketId == null) return;
      const res = await api.createSupportTicketActivity(ticketId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    updateActivity: async (activityId: number, payload: SupportTicketActivityPayload) => {
      if (ticketId == null) return;
      const res = await api.updateSupportTicketActivity(ticketId, activityId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    deleteActivity: async (activityId: number) => {
      if (ticketId == null) return;
      await api.deleteSupportTicketActivity(ticketId, activityId);
      await mutate(['support-ticket-detail', ticketId]);
    },
  };
}

export function useSupportTicketDependencyMutations(ticketId: number | string | null) {
  const { mutate } = useSWRConfig();
  return {
    addDependency: async (payload: SupportTicketDependencyPayload) => {
      if (ticketId == null) return;
      const res = await api.createSupportTicketDependency(ticketId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    updateDependency: async (dependencyId: number, payload: SupportTicketDependencyPayload) => {
      if (ticketId == null) return;
      const res = await api.updateSupportTicketDependency(ticketId, dependencyId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    deleteDependency: async (dependencyId: number) => {
      if (ticketId == null) return;
      await api.deleteSupportTicketDependency(ticketId, dependencyId);
      await mutate(['support-ticket-detail', ticketId]);
    },
  };
}

export function useSupportTicketCommunicationMutations(ticketId: number | string | null) {
  const { mutate } = useSWRConfig();
  return {
    addCommunication: async (payload: SupportTicketCommunicationPayload) => {
      if (ticketId == null) return;
      const res = await api.createSupportTicketCommunication(ticketId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    updateCommunication: async (communicationId: number, payload: SupportTicketCommunicationPayload) => {
      if (ticketId == null) return;
      const res = await api.updateSupportTicketCommunication(ticketId, communicationId, payload);
      await mutate(['support-ticket-detail', ticketId]);
      return res;
    },
    deleteCommunication: async (communicationId: number) => {
      if (ticketId == null) return;
      await api.deleteSupportTicketCommunication(ticketId, communicationId);
      await mutate(['support-ticket-detail', ticketId]);
    },
  };
}

export function useInvoiceAging(config?: SWRConfiguration) {
  return useSWR('invoice-aging', () => api.getInvoiceAging(), config);
}

export function usePlanDistribution(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['plan-distribution', currency],
    () => api.getPlanDistribution(currency),
    config
  );
}

// Projects
export function useProjects(
  params?: {
    status?: string;
    priority?: ProjectPriority;
    customer_id?: number;
    project_type?: string;
    department?: string;
    search?: string;
    overdue_only?: boolean;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(['projects', params], () => api.getProjects(params), config);
}

export function useProjectDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['project-detail', id] as const : null,
    ([, projectId]) => api.getProjectDetail(projectId),
    config
  );
}

export function useProjectTasks(
  projectId: number | null,
  params?: {
    status?: string;
    priority?: string;
    assigned_to?: string;
    task_type?: string;
    search?: string;
    overdue_only?: boolean;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    projectId ? ['project-tasks', projectId, params] as const : null,
    ([, pid, p]) => api.getProjectTasks({ project_id: pid, ...p }),
    config
  );
}

export function useAllTasks(
  params?: {
    project_id?: number;
    status?: string;
    priority?: string;
    assigned_to?: string;
    task_type?: string;
    search?: string;
    overdue_only?: boolean;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['all-tasks', params] as const,
    ([, p]) => api.getProjectTasks(p),
    config
  );
}

export function useTaskDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['task-detail', id] as const : null,
    ([, taskId]) => api.getTaskDetail(taskId),
    config
  );
}

export function useTaskMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateTask: async (id: number, payload: import('@/lib/api').ProjectTaskUpdatePayload) => {
      const res = await api.updateTask(id, payload);
      await mutate(['task-detail', id]);
      await mutate('all-tasks');
      await mutate('projects');
      return res;
    },
  };
}

export function useProjectMutations() {
  const { mutate } = useSWRConfig();
  return {
    createProject: async (payload: ProjectPayload & { project_name: string }) => {
      const res = await api.createProject(payload);
      await mutate('projects');
      return res;
    },
    updateProject: async (id: number, payload: ProjectPayload) => {
      const res = await api.updateProject(id, payload);
      await mutate('projects');
      await mutate(['project-detail', id]);
      return res;
    },
    deleteProject: async (id: number) => {
      await api.deleteProject(id);
      await mutate('projects');
    },
  };
}

export function useProjectsDashboard(config?: SWRConfiguration) {
  return useSWR('projects-dashboard', () => api.getProjectsDashboard(), config);
}

export function useProjectsStatusTrend(months = 12, config?: SWRConfiguration) {
  return useSWR(['projects-status-trend', months], () => api.getProjectsStatusTrend(months), config);
}

export function useProjectsTaskDistribution(config?: SWRConfiguration) {
  return useSWR('projects-task-distribution', () => api.getProjectsTaskDistribution(), config);
}

export function useProjectsPerformance(config?: SWRConfiguration) {
  return useSWR('projects-performance', () => api.getProjectsPerformance(), config);
}

export function useProjectsDepartmentSummary(months = 12, config?: SWRConfiguration) {
  return useSWR(['projects-dept-summary', months], () => api.getProjectsDepartmentSummary(months), config);
}

// Customer Domain Hooks
export function useCustomerDashboard(enabled = true, config?: SWRConfiguration) {
  return useSWR(
    enabled ? 'customer-dashboard' : null,
    () => api.getCustomerDashboard(),
    {
      refreshInterval: 60000, // Refresh every minute
      ...config,
    }
  );
}

export function useCustomers(
  params?: {
    status?: string;
    customer_type?: string;
    billing_type?: string;
    pop_id?: number;
    search?: string;
    limit?: number;
    offset?: number;
    cohort?: string;
    signup_start?: string;
    signup_end?: string;
    city?: string;
    base_station?: string;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['customers', params],
    () => api.getCustomers(params),
    config
  );
}

export function useCustomer(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['customer', id] as const : null,
    ([, customerId]) => api.getCustomer(customerId),
    config
  );
}

export function useCustomerUsage(
  id: number | null,
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    id ? ['customer-usage', id, params] as const : null,
    ([, customerId, usageParams]) => api.getCustomerUsage(customerId, usageParams),
    config
  );
}

export function useCustomer360(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['customer-360', id] as const : null,
    ([, customerId]) => api.getCustomer360(customerId),
    config
  );
}

export function useBlockedCustomers(
  params?: {
    min_days_blocked?: number;
    max_days_blocked?: number;
    pop_id?: number;
    plan?: string;
    min_mrr?: number;
    sort_by?: 'mrr' | 'days_blocked' | 'tenure';
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['blocked-customers', params],
    () => api.getBlockedCustomers(params),
    config
  );
}

// Customer Analytics Hooks
export function useBlockedAnalytics(config?: SWRConfiguration) {
  return useSWR('customer-blocked-analytics', () => api.getBlockedAnalytics(), config);
}

export function useActiveAnalytics(config?: SWRConfiguration) {
  return useSWR('customer-active-analytics', () => api.getActiveAnalytics(), config);
}

export function useCustomerSignupTrend(
  params?: { start_date?: string; end_date?: string; interval?: 'month' | 'week' },
  config?: SWRConfiguration
) {
  return useSWR(
    ['customer-signup-trend', params],
    () => api.getCustomerSignupTrend(params),
    config
  );
}

export function useCustomerCohort(months = 12, config?: SWRConfiguration) {
  return useSWR(['customer-cohort', months], () => api.getCustomerCohort(months), config);
}

export function useCustomersByPlan(config?: SWRConfiguration) {
  return useSWR('customers-by-plan', () => api.getCustomersByPlan(), config);
}

export function useCustomersByType(config?: SWRConfiguration) {
  return useSWR('customers-by-type', () => api.getCustomersByType(), config);
}

export function useCustomersByLocation(limit?: number, config?: SWRConfiguration) {
  return useSWR(['customers-by-location', limit], () => api.getCustomersByLocation(limit), config);
}

export function useCustomersByPop(config?: SWRConfiguration) {
  return useSWR('customers-by-pop', () => api.getCustomersByPop(), config);
}

export function useCustomersByRouter(popId?: number, config?: SWRConfiguration) {
  return useSWR(
    ['customers-by-router', popId],
    () => api.getCustomersByRouter(popId),
    config
  );
}

export function useCustomersByTicketVolume(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['customers-by-ticket-volume', days],
    () => api.getCustomersByTicketVolume(days),
    config
  );
}

export function useCustomerDataQualityOutreach(config?: SWRConfiguration) {
  return useSWR(
    'customer-data-quality-outreach',
    () => api.getCustomerDataQualityOutreach(),
    config
  );
}

export function useCustomerRevenueOverdue(popId?: number, planName?: string, config?: SWRConfiguration) {
  return useSWR(
    ['customer-revenue-overdue', popId, planName],
    () => api.getCustomerRevenueOverdue(popId, planName),
    config
  );
}

export function useCustomerPaymentTimeliness(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['customer-payment-timeliness', days],
    () => api.getCustomerPaymentTimeliness(days),
    config
  );
}

// Customer Insights Hooks
export function useCustomerSegmentsInsights(config?: SWRConfiguration) {
  return useSWR<import('@/lib/api').CustomerSegmentsInsightsResponse>(
    'customer-segments-insights',
    () => api.getCustomerSegmentsInsights(),
    config
  );
}

export function useCustomerHealthInsights(config?: SWRConfiguration) {
  return useSWR<import('@/lib/api').CustomerHealthInsightsResponse>(
    'customer-health-insights',
    () => api.getCustomerHealthInsights(),
    config
  );
}

export function useCustomerCompletenessInsights(config?: SWRConfiguration) {
  return useSWR<import('@/lib/api').CustomerCompletenessResponse>(
    'customer-completeness-insights',
    () => api.getCustomerCompletenessInsights(),
    config
  );
}

export function useCustomerPlanChanges(months = 6, config?: SWRConfiguration) {
  return useSWR<import('@/lib/api').CustomerPlanChangesResponse>(
    ['customer-plan-changes', months],
    () => api.getCustomerPlanChanges(months),
    config
  );
}

export function useSyncStatus(config?: SWRConfiguration) {
  return useSWR('sync-status', () => api.getSyncStatus(), {
    refreshInterval: 10000, // Refresh every 10 seconds
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    ...config,
  });
}

export function useTables(config?: SWRConfiguration) {
  return useSWR('tables', () => api.getTables(), config);
}

export function useTableData(
  table: string | null,
  params?: {
    limit?: number;
    offset?: number;
    order_by?: string;
    order_dir?: 'asc' | 'desc';
  },
  config?: SWRConfiguration
) {
  return useSWR(
    table ? ['table-data', table, params] as const : null,
    ([, tableName, tableParams]) => api.getTableData(tableName, tableParams),
    config
  );
}

export function useDataQuality(config?: SWRConfiguration) {
  return useSWR('data-quality', () => api.getDataQuality(), config);
}

export function useSyncLogs(limit = 50, config?: SWRConfiguration) {
  return useSWR(
    ['sync-logs', limit],
    () => api.getSyncLogs(limit),
    {
      refreshInterval: 10000,
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      ...config,
    }
  );
}

export function useChurnRisk(limit = 20, config?: SWRConfiguration) {
  return useSWR(
    ['churn-risk', limit],
    () => api.getChurnRisk(limit),
    config
  );
}

// Revenue Quality Analytics
export function useDSOTrend(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['dso-trend', months, startDate, endDate],
    () => api.getDSOTrend(months, startDate, endDate),
    config
  );
}

export function useRevenueByTerritory(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['revenue-by-territory', months, startDate, endDate],
    () => api.getRevenueByTerritory(months, startDate, endDate),
    config
  );
}

export function useRevenueCohort(config?: SWRConfiguration) {
  return useSWR('revenue-cohort', () => api.getRevenueCohort(), config);
}

// Collections & Risk
export function useAgingBySegment(config?: SWRConfiguration) {
  return useSWR('aging-by-segment', () => api.getAgingBySegment(), config);
}

export function useCreditNotes(months = 12, config?: SWRConfiguration) {
  return useSWR(
    ['credit-notes', months],
    () => api.getCreditNotesSummary(months),
    config
  );
}

// Sales Pipeline
export function useSalesPipeline(config?: SWRConfiguration) {
  return useSWR('sales-pipeline', () => api.getSalesPipeline(), config);
}

export function useQuotationTrend(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['quotation-trend', months, startDate, endDate],
    () => api.getQuotationTrend(months, startDate, endDate),
    config
  );
}

// Support/SLA
export function useSLAAttainment(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['sla-attainment', days],
    () => api.getSLAAttainment(days),
    config
  );
}

export function useAgentProductivity(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['agent-productivity', days],
    () => api.getAgentProductivity(days),
    config
  );
}

export function useTicketsByType(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['tickets-by-type', days],
    () => api.getTicketsByType(days),
    config
  );
}

// Network
export function useNetworkDeviceStatus(config?: SWRConfiguration) {
  return useSWR('network-device-status', () => api.getNetworkDeviceStatus(), config);
}

export function useIPUtilization(config?: SWRConfiguration) {
  return useSWR('ip-utilization', () => api.getIPUtilization(), config);
}

// Expenses
export function useExpensesByCategory(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['expenses-by-category', months, startDate, endDate],
    () => api.getExpensesByCategory(months, startDate, endDate),
    config
  );
}

export function useExpensesByCostCenter(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['expenses-by-cost-center', months, startDate, endDate],
    () => api.getExpensesByCostCenter(months, startDate, endDate),
    config
  );
}

export function useExpenseTrend(months = 12, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['expense-trend', months, startDate, endDate],
    () => api.getExpenseTrend(months, startDate, endDate),
    config
  );
}

export function useVendorSpend(months = 12, limit = 20, startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['vendor-spend', months, limit, startDate, endDate],
    () => api.getVendorSpend(months, limit, startDate, endDate),
    config
  );
}

// People/Ops
export function useTicketsPerEmployee(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['tickets-per-employee', days],
    () => api.getTicketsPerEmployee(days),
    config
  );
}

export function useMetricsByDepartment(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['metrics-by-department', days],
    () => api.getMetricsByDepartment(days),
    config
  );
}

// Deep Insights Hooks
export function useDataCompleteness(config?: SWRConfiguration) {
  return useSWR('data-completeness', () => api.getDataCompleteness(), config);
}

export function useCustomerSegments(config?: SWRConfiguration) {
  return useSWR('customer-segments', () => api.getCustomerSegments(), config);
}

export function useCustomerHealth(limit = 100, riskLevel?: string, config?: SWRConfiguration) {
  return useSWR(
    ['customer-health', limit, riskLevel],
    () => api.getCustomerHealth(limit, riskLevel),
    config
  );
}

export function useRelationshipMap(config?: SWRConfiguration) {
  return useSWR('relationship-map', () => api.getRelationshipMap(), config);
}

export function useFinancialInsights(config?: SWRConfiguration) {
  return useSWR('financial-insights', () => api.getFinancialInsights(), config);
}

export function useOperationalInsights(config?: SWRConfiguration) {
  return useSWR('operational-insights', () => api.getOperationalInsights(), config);
}

export function useAnomalies(config?: SWRConfiguration) {
  return useSWR('anomalies', () => api.getAnomalies(), config);
}

export function useDataAvailability(config?: SWRConfiguration) {
  return useSWR('data-availability', () => api.getDataAvailability(), config);
}

export function useDataExplorer(
  entity: string | null,
  params: Record<string, unknown>,
  config?: SWRConfiguration
) {
  return useSWR(
    entity ? ['data-explorer', entity, params] as const : null,
    ([, entityName, explorerParams]) => api.exploreEntity(entityName, explorerParams),
    config
  );
}

// Finance Domain Hooks
export function useFinanceDashboard(currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    ['finance-dashboard', currency],
    () => api.getFinanceDashboard(currency),
    {
      refreshInterval: 60000, // Refresh every minute
      ...config,
    }
  );
}

export function useFinanceInvoices(
  params?: {
    status?: string;
    customer_id?: number;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    overdue_only?: boolean;
    search?: string;
    sort_by?: 'invoice_date' | 'total_amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['finance-invoices', params],
    () => api.getFinanceInvoices(params),
    config
  );
}

export function useFinancePayments(
  params?: {
    status?: string;
    payment_method?: string;
    customer_id?: number;
    invoice_id?: number;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: 'payment_date' | 'amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['finance-payments', params],
    () => api.getFinancePayments(params),
    config
  );
}

export function useFinanceCreditNotes(
  params?: {
    customer_id?: number;
    invoice_id?: number;
    start_date?: string;
    end_date?: string;
    currency?: string;
    search?: string;
    status?: string;
    sort_by?: 'issue_date' | 'amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['finance-credit-notes', params],
    () => api.getFinanceCreditNotes(params),
    config
  );
}

export function useFinanceRevenueTrend(
  params?: { start_date?: string; end_date?: string; interval?: 'month' | 'week'; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['finance-revenue-trend', params],
    () => api.getFinanceRevenueTrend({ interval: 'month', ...params }),
    config
  );
}

export function useFinanceCollections(
  params?: { start_date?: string; end_date?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['finance-collections', params],
    () => api.getFinanceCollections(params),
    config
  );
}

export function useFinanceAging(params?: { currency?: string }, config?: SWRConfiguration) {
  return useSWR(['finance-aging', params], () => api.getFinanceAging(params), config);
}

export function useFinanceRevenueBySegment(config?: SWRConfiguration) {
  return useSWR('finance-revenue-by-segment', () => api.getFinanceRevenueBySegment(), config);
}

export function useFinancePaymentBehavior(params?: { start_date?: string; end_date?: string; currency?: string }, config?: SWRConfiguration) {
  return useSWR(['finance-payment-behavior', params], () => api.getFinancePaymentBehavior(params), config);
}

export function useFinanceForecasts(currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(['finance-forecasts', currency], () => api.getFinanceForecasts(currency), config);
}

export function useFinanceInvoiceDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-invoice-detail', id, currency] as const : null,
    ([, invoiceId, invCurrency]) => api.getFinanceInvoiceDetail(invoiceId, invCurrency),
    config
  );
}

export function useFinancePaymentDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-payment-detail', id, currency] as const : null,
    ([, paymentId, payCurrency]) => api.getFinancePaymentDetail(paymentId, payCurrency),
    config
  );
}

export function useFinanceCreditNoteDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-credit-note-detail', id, currency] as const : null,
    ([, creditNoteId, creditCurrency]) => api.getFinanceCreditNoteDetail(creditNoteId, creditCurrency),
    config
  );
}

export function useFinanceOrderDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-order-detail', id, currency] as const : null,
    ([, orderId, orderCurrency]) => api.getFinanceOrderDetail(orderId, orderCurrency),
    config
  );
}

export function useFinanceQuotationDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-quotation-detail', id, currency] as const : null,
    ([, quotationId, quotationCurrency]) => api.getFinanceQuotationDetail(quotationId, quotationCurrency),
    config
  );
}

export function useFinanceCustomerDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-customer-detail', id] as const : null,
    ([, customerId]) => api.getFinanceCustomerDetail(customerId),
    config
  );
}

export function useFinanceOrders(
  params?: {
    customer_id?: number;
    status?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: 'order_date' | 'total_amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(['finance-orders', params], () => api.getFinanceOrders(params), config);
}

export function useFinanceQuotations(
  params?: {
    customer_id?: number;
    status?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: 'quotation_date' | 'total_amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(['finance-quotations', params], () => api.getFinanceQuotations(params), config);
}

export function useFinanceCustomers(
  params?: { search?: string; status?: string; customer_type?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['finance-customers', params], () => api.getFinanceCustomers(params), config);
}

// Finance mutations
export function useFinanceInvoiceMutations() {
  const { mutate } = useSWRConfig();

  const createInvoice = async (payload: any) => {
    const created = await api.createFinanceInvoice(payload);
    // Refresh invoice lists and dashboards
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-invoices'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return created;
  };

  const updateInvoice = async (id: number, payload: any) => {
    const updated = await api.updateFinanceInvoice(id, payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-invoices'),
      mutate(['finance-invoice-detail', id, payload?.currency || 'NGN']),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return updated;
  };

  const deleteInvoice = async (id: number, soft = true) => {
    await api.deleteFinanceInvoice(id, soft);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-invoices'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
  };

  return { createInvoice, updateInvoice, deleteInvoice };
}

export function useFinancePaymentMutations() {
  const { mutate } = useSWRConfig();

  const createPayment = async (payload: any) => {
    const created = await api.createFinancePayment(payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-payments'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return created;
  };

  const updatePayment = async (id: number, payload: any) => {
    const updated = await api.updateFinancePayment(id, payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-payments'),
      mutate(['finance-payment-detail', id, payload?.currency || 'NGN']),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return updated;
  };

  const deletePayment = async (id: number, soft = true) => {
    await api.deleteFinancePayment(id, soft);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-payments'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
  };

  return { createPayment, updatePayment, deletePayment };
}

export function useFinanceCreditNoteMutations() {
  const { mutate } = useSWRConfig();

  const createCreditNote = async (payload: any) => {
    const created = await api.createFinanceCreditNote(payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-credit-notes'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return created;
  };

  const updateCreditNote = async (id: number, payload: any) => {
    const updated = await api.updateFinanceCreditNote(id, payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-credit-notes'),
      mutate(['finance-credit-note-detail', id, payload?.currency || 'NGN']),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return updated;
  };

  const deleteCreditNote = async (id: number, soft = true) => {
    await api.deleteFinanceCreditNote(id, soft);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-credit-notes'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
  };

  return { createCreditNote, updateCreditNote, deleteCreditNote };
}

export function useFinanceOrderMutations() {
  const { mutate } = useSWRConfig();

  const createOrder = async (payload: any) => {
    const created = await api.createFinanceOrder(payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-orders'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return created;
  };

  const updateOrder = async (id: number, payload: any) => {
    const updated = await api.updateFinanceOrder(id, payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-orders'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return updated;
  };

  const deleteOrder = async (id: number, soft = true) => {
    await api.deleteFinanceOrder(id, soft);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-orders'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
  };

  return { createOrder, updateOrder, deleteOrder };
}

export function useFinanceQuotationMutations() {
  const { mutate } = useSWRConfig();

  const createQuotation = async (payload: any) => {
    const created = await api.createFinanceQuotation(payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-quotations'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return created;
  };

  const updateQuotation = async (id: number, payload: any) => {
    const updated = await api.updateFinanceQuotation(id, payload);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-quotations'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
    return updated;
  };

  const deleteQuotation = async (id: number, soft = true) => {
    await api.deleteFinanceQuotation(id, soft);
    await Promise.all([
      mutate((key) => Array.isArray(key) && key[0] === 'finance-quotations'),
      mutate((key) => Array.isArray(key) && key[0] === 'finance-dashboard'),
    ]);
  };

  return { createQuotation, updateQuotation, deleteQuotation };
}

export function useFinanceCustomerMutations() {
  const { mutate } = useSWRConfig();

  const createCustomer = async (payload: any) => {
    const created = await api.createFinanceCustomer(payload);
    await mutate((key) => Array.isArray(key) && key[0] === 'finance-customers');
    await mutate((key) => Array.isArray(key) && key[0] === 'customers');
    return created;
  };

  const updateCustomer = async (id: number, payload: any) => {
    const updated = await api.updateFinanceCustomer(id, payload);
    await mutate((key) => Array.isArray(key) && key[0] === 'finance-customers');
    await mutate((key) => Array.isArray(key) && key[0] === 'customers');
    await mutate(['finance-customer-detail', id]);
    return updated;
  };

  return { createCustomer, updateCustomer };
}

export function useTablesEnhanced(config?: SWRConfiguration) {
  return useSWR('tables-enhanced', () => api.getTablesEnhanced(), config);
}

export function useTableDataEnhanced(
  table: string | null,
  params?: {
    limit?: number;
    offset?: number;
    order_by?: string;
    order_dir?: 'asc' | 'desc';
    date_column?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    table ? ['table-data-enhanced', table, params] as const : null,
    ([, tableName, tableParams]) => api.getTableDataEnhanced(tableName, tableParams),
    config
  );
}

// Accounting Domain Hooks
export function useAccountingDashboard(currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(['accounting-dashboard', currency], () => api.getAccountingDashboard(currency), {
    refreshInterval: 60000,
    dedupingInterval: 60000,
    revalidateOnFocus: false,
    revalidateIfStale: true,
    keepPreviousData: true,
    ...config,
  });
}

export function useAccountingChartOfAccounts(accountType?: string, config?: SWRConfiguration) {
  return useSWR(
    ['accounting-chart-of-accounts', accountType],
    () => api.getAccountingChartOfAccounts(accountType),
    config
  );
}

export function useAccountingAccountDetail(id: number | null, params?: { include_ledger?: boolean; start_date?: string; end_date?: string; limit?: number }, config?: SWRConfiguration) {
  return useSWR(
    id ? ['accounting-account-detail', id, params] as const : null,
    ([, accountId, detailParams]) => api.getAccountingAccountDetail(accountId, detailParams),
    config
  );
}

export function useAccountingTrialBalance(
  params?: { fiscal_year?: string; start_date?: string; end_date?: string; currency?: string; drill?: boolean },
  config?: SWRConfiguration
) {
  const key = ['accounting-trial-balance', params];
  return useSWR(
    key,
    () => api.getAccountingTrialBalance(params),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useAccountingBalanceSheet(
  params?: { fiscal_year?: string; as_of_date?: string; currency?: string; common_size?: boolean },
  config?: SWRConfiguration
) {
  const key = ['accounting-balance-sheet', params];
  return useSWR(
    key,
    () => api.getAccountingBalanceSheet(params),
    {
      dedupingInterval: 5 * 60 * 1000,
      revalidateOnFocus: false,
      revalidateIfStale: true,
      keepPreviousData: true,
      ...config,
    }
  );
}

export function useAccountingIncomeStatement(
  params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
    compare_start?: string;
    compare_end?: string;
    show_ytd?: boolean;
    common_size?: boolean;
    basis?: string;
  },
  config?: SWRConfiguration
) {
  const key = ['accounting-income-statement', params];
  return useSWR(
    key,
    () => api.getAccountingIncomeStatement(params),
    {
      dedupingInterval: 5 * 60 * 1000,
      revalidateOnFocus: false,
      revalidateIfStale: true,
      keepPreviousData: true,
      ...config,
    }
  );
}

export function useAccountingTaxCategories(config?: SWRConfiguration) {
  return useSWR('accounting-tax-categories', () => api.getAccountingTaxCategories(), config);
}

export function useAccountingTaxTemplates(config?: SWRConfiguration) {
  return useSWR('accounting-tax-templates', async () => {
    const [sales, purchase, item, rules] = await Promise.all([
      api.getAccountingSalesTaxTemplates(),
      api.getAccountingPurchaseTaxTemplates(),
      api.getAccountingItemTaxTemplates(),
      api.getAccountingTaxRules(),
    ]);
    return { sales, purchase, item, rules };
  }, config);
}

export function useAccountingTaxPayable(
  params?: { start_date?: string; end_date?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(['accounting-tax-payable', params], () => api.getAccountingTaxPayable(params), {
    dedupingInterval: 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useAccountingTaxReceivable(
  params?: { start_date?: string; end_date?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(['accounting-tax-receivable', params], () => api.getAccountingTaxReceivable(params), {
    dedupingInterval: 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useAccountingReceivablesEnhanced(
  params?: Record<string, any>,
  config?: SWRConfiguration
) {
  return useSWR(['accounting-receivables-aging-enhanced', params], () => api.getAccountingReceivablesAgingEnhanced(params), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useCustomerCreditStatus(customerId: number | null, config?: SWRConfiguration) {
  return useSWR(customerId ? ['accounting-customer-credit', customerId] : null, () => api.getAccountingCustomerCreditStatus(customerId as number), config);
}

export function useAccountingInvoiceDunningHistory(invoiceId: number | null, config?: SWRConfiguration) {
  return useSWR(invoiceId ? ['accounting-invoice-dunning', invoiceId] : null, () => api.getAccountingInvoiceDunningHistory(invoiceId as number), config);
}

export function useAccountingDunningQueue(config?: SWRConfiguration) {
  return useSWR('accounting-dunning-queue', () => api.getAccountingDunningQueue(), config);
}

export function useAccountingGeneralLedger(
  params?: {
    account?: string;
    party?: string;
    start_date?: string;
    end_date?: string;
    cost_center?: string;
    fiscal_year?: string;
    currency?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR<AccountingGeneralLedgerResponse>(
    ['accounting-general-ledger', params],
    () => api.getAccountingGeneralLedger(params),
    {
      revalidateOnFocus: false,
      revalidateIfStale: true,
      keepPreviousData: true,
      ...config,
    }
  );
}

export function useAccountingCashFlow(
  params?: { start_date?: string; end_date?: string; fiscal_year?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-cash-flow', params],
    () => api.getAccountingCashFlow(params),
    {
      dedupingInterval: 5 * 60 * 1000,
      revalidateOnFocus: false,
      revalidateIfStale: true,
      keepPreviousData: true,
      ...config,
    }
  );
}

export function useAccountingEquityStatement(
  params?: { start_date?: string; end_date?: string; fiscal_year?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-equity-statement', params],
    () => api.getAccountingEquityStatement(params),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useAccountingFinancialRatios(
  params?: { as_of_date?: string; fiscal_year?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-financial-ratios', params],
    () => api.getAccountingFinancialRatios(params),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useAccountingPayables(
  params?: {
    currency?: string;
    supplier_id?: number;
    as_of_date?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-payables', params],
    () => api.getAccountingPayables(params),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useAccountingReceivables(
  params?: {
    customer_id?: number;
    currency?: string;
    as_of_date?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-receivables', params],
    () => api.getAccountingReceivables(params),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useAccountingReceivablesOutstanding(
  params?: { currency?: string; top?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-receivables-outstanding', params],
    () => api.getAccountingReceivablesOutstanding(params),
    config
  );
}

export function useAccountingPayablesOutstanding(
  params?: { currency?: string; top?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-payables-outstanding', params],
    () => api.getAccountingPayablesOutstanding(params),
    config
  );
}

export function useAccountingJournalEntries(
  params?: {
    voucher_type?: string;
    party?: string;
    cost_center?: string;
    start_date?: string;
    end_date?: string;
    currency?: string;
    search?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
  ) {
  return useSWR(
    ['accounting-journal-entries', params],
    () => api.getAccountingJournalEntries(params),
    config
  );
}

export function useAccountingJournalEntryDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['accounting-journal-entry-detail', id] as const : null,
    ([, entryId]) => api.getAccountingJournalEntryDetail(entryId),
    config
  );
}

export function useAccountingSuppliers(
  params?: {
    search?: string;
    status?: string;
    currency?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-suppliers', params],
    () => api.getAccountingSuppliers(params),
    config
  );
}

export function useAccountingBankAccounts(config?: SWRConfiguration) {
  return useSWR('accounting-bank-accounts', () => api.getAccountingBankAccounts(), config);
}

export function useAccountingFiscalYears(config?: SWRConfiguration) {
  return useSWR('accounting-fiscal-years', () => api.getAccountingFiscalYears(), config);
}

export function useAccountingCostCenters(config?: SWRConfiguration) {
  return useSWR('accounting-cost-centers', () => api.getAccountingCostCenters(), config);
}

export function useAccountingPurchaseInvoices(
  params?: {
    status?: string;
    supplier_id?: number;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(['accounting-purchase-invoices', params], () => api.getAccountingPurchaseInvoices(params), config);
}

export function useAccountingPurchaseInvoiceDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['accounting-purchase-invoice-detail', id, currency] as const : null,
    ([, invoiceId, invoiceCurrency]) => api.getAccountingPurchaseInvoiceDetail(invoiceId, invoiceCurrency),
    config
  );
}

export function useAccountingBankTransactions(
  params?: {
    status?: string;
    account?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR<AccountingBankTransactionListResponse>(
    ['accounting-bank-transactions', params],
    () => api.getAccountingBankTransactions(params),
    config
  );
}

export function useAccountingBankTransactionDetail(id: number | string | null, config?: SWRConfiguration) {
  const key = id ? (['accounting-bank-transaction-detail', id] as const) : null;
  return useSWR<AccountingBankTransactionDetail>(
    key,
    key ? ([, transactionId]: [string, string | number]) => api.getAccountingBankTransactionDetail(transactionId) : null,
    config
  );
}

export function useBankTransactionSuggestions(
  id: number | string | null,
  params?: { party_type?: string; limit?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    id ? ['bank-transaction-suggestions', id, params] as const : null,
    ([, transactionId, suggestionParams]) => api.getBankTransactionSuggestions(transactionId, suggestionParams),
    config
  );
}

export function useBankTransactionMutations() {
  const { mutate } = useSWRConfig();

  return {
    createTransaction: async (payload: Parameters<typeof api.createBankTransaction>[0]) => {
      const res = await api.createBankTransaction(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-bank-transactions');
      return res;
    },

    importTransactions: async (formData: FormData) => {
      const res = await api.importBankTransactions(formData);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-bank-transactions');
      return res;
    },

    reconcile: async (id: number | string, payload: Parameters<typeof api.reconcileBankTransaction>[1]) => {
      const res = await api.reconcileBankTransaction(id, payload);
      await Promise.all([
        mutate((key) => Array.isArray(key) && key[0] === 'accounting-bank-transactions'),
        mutate(['accounting-bank-transaction-detail', id]),
        mutate((key) => Array.isArray(key) && key[0] === 'bank-transaction-suggestions'),
      ]);
      return res;
    },
  };
}

// Nigerian Tax Module Hooks
export function useTaxDashboard(config?: SWRConfiguration) {
  return useSWR(['tax-dashboard'], () => api.getTaxDashboard(), {
    refreshInterval: 60000,
    ...config,
  });
}

export function useTaxSettings(config?: SWRConfiguration) {
  return useSWR(['tax-settings'], () => api.getTaxSettings(), config);
}

export function useVATTransactions(
  params?: { period?: string; type?: string; page?: number; page_size?: number },
  config?: SWRConfiguration
) {
  return useSWR(['vat-transactions', params], () => api.getVATTransactions(params), config);
}

export function useVATSummary(period: string | null, config?: SWRConfiguration) {
  return useSWR(period ? ['vat-summary', period] : null, () => api.getVATSummary(period!), config);
}

export function useVATFilingPrep(period: string | null, config?: SWRConfiguration) {
  return useSWR(period ? ['vat-filing-prep', period] : null, () => api.getVATFilingPrep(period!), config);
}

export function useWHTTransactions(
  params?: { period?: string; supplier_id?: string; page?: number; page_size?: number },
  config?: SWRConfiguration
) {
  return useSWR(['wht-transactions', params], () => api.getWHTTransactions(params), config);
}

export function useWHTSupplierSummary(supplierId: string | number | null, config?: SWRConfiguration) {
  return useSWR(
    supplierId ? ['wht-supplier-summary', supplierId] : null,
    () => api.getWHTSupplierSummary(supplierId!),
    config
  );
}

export function useWHTRemittanceDue(config?: SWRConfiguration) {
  return useSWR(['wht-remittance-due'], () => api.getWHTRemittanceDue(), config);
}

export function usePAYECalculations(
  params?: { period?: string; employee_id?: string; page?: number; page_size?: number },
  config?: SWRConfiguration
) {
  return useSWR(['paye-calculations', params], () => api.getPAYECalculations(params), config);
}

export function usePAYESummary(period: string | null, config?: SWRConfiguration) {
  return useSWR(period ? ['paye-summary', period] : null, () => api.getPAYESummary(period!), config);
}

export function useCITAssessments(
  params?: { year?: number; page?: number; page_size?: number },
  config?: SWRConfiguration
) {
  return useSWR(['cit-assessments', params], () => api.getCITAssessments(params), config);
}

export function useCITComputation(year: number | null, config?: SWRConfiguration) {
  return useSWR(year ? ['cit-computation', year] : null, () => api.getCITComputation(year!), config);
}

export function useFilingCalendar(
  params?: { year?: number; tax_type?: string },
  config?: SWRConfiguration
) {
  return useSWR(['filing-calendar', params], () => api.getFilingCalendar(params), config);
}

export function useUpcomingFilings(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR(['upcoming-filings', params], () => api.getUpcomingFilings(params), config);
}

export function useOverdueFilings(config?: SWRConfiguration) {
  return useSWR(['overdue-filings'], () => api.getOverdueFilings(), config);
}

export function useTaxMutations() {
  const { mutate } = useSWRConfig();

  return {
    updateSettings: async (payload: Parameters<typeof api.updateTaxSettings>[0]) => {
      const res = await api.updateTaxSettings(payload);
      await mutate(['tax-settings']);
      return res;
    },
    recordVATOutput: async (payload: Parameters<typeof api.recordVATOutput>[0]) => {
      const res = await api.recordVATOutput(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'vat-transactions');
      await mutate(['tax-dashboard']);
      return res;
    },
    recordVATInput: async (payload: Parameters<typeof api.recordVATInput>[0]) => {
      const res = await api.recordVATInput(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'vat-transactions');
      await mutate(['tax-dashboard']);
      return res;
    },
    deductWHT: async (payload: Parameters<typeof api.deductWHT>[0]) => {
      const res = await api.deductWHT(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'wht-transactions');
      await mutate(['tax-dashboard']);
      return res;
    },
    calculatePAYE: async (payload: Parameters<typeof api.calculatePAYE>[0]) => {
      const res = await api.calculatePAYE(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'paye-calculations');
      await mutate(['tax-dashboard']);
      return res;
    },
    createCITAssessment: async (payload: Parameters<typeof api.createCITAssessment>[0]) => {
      const res = await api.createCITAssessment(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'cit-assessments');
      await mutate(['tax-dashboard']);
      return res;
    },
    generateWHTCertificate: async (payload: Parameters<typeof api.generateWHTCertificate>[0]) => {
      const res = await api.generateWHTCertificate(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'wht-transactions');
      return res;
    },
    createEInvoice: async (payload: Parameters<typeof api.createEInvoice>[0]) => {
      const res = await api.createEInvoice(payload);
      return res;
    },
    validateEInvoice: async (id: number | string) => {
      const res = await api.validateEInvoice(id);
      return res;
    },
  };
}

// Purchasing Domain Hooks
export function usePurchasingDashboard(
  params?: { start_date?: string; end_date?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-dashboard', params],
    () => api.getPurchasingDashboard(params),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

export function usePurchasingBills(
  params?: {
    status?: string;
    supplier?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    outstanding_only?: boolean;
    overdue_only?: boolean;
    search?: string;
    sort_by?: 'posting_date' | 'due_date' | 'grand_total' | 'outstanding_amount' | 'supplier';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-bills', params],
    () => api.getPurchasingBills(params),
    config
  );
}

export function usePurchasingBillDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-bill-detail', id] as const : null,
    ([, billId]) => api.getPurchasingBillDetail(billId),
    config
  );
}

export function usePurchasingPayments(
  params?: {
    supplier?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-payments', params],
    () => api.getPurchasingPayments(params),
    config
  );
}

export function usePurchasingOrders(
  params?: {
    supplier?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: 'transaction_date' | 'grand_total' | 'supplier_name';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-orders', params],
    () => api.getPurchasingOrders(params),
    config
  );
}

export function usePurchasingOrderDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-order-detail', id] as const : null,
    ([, orderId]) => api.getPurchasingOrderDetail(orderId),
    config
  );
}

export function usePurchasingDebitNotes(
  params?: {
    supplier?: string;
    start_date?: string;
    end_date?: string;
    status?: string;
    currency?: string;
    search?: string;
    sort_by?: 'posting_date' | 'grand_total' | 'supplier_name';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-debit-notes', params],
    () => api.getPurchasingDebitNotes(params),
    config
  );
}

export function usePurchasingDebitNoteDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-debit-note-detail', id] as const : null,
    ([, debitNoteId]) => api.getPurchasingDebitNoteDetail(debitNoteId),
    config
  );
}

export function usePurchasingSuppliers(
  params?: {
    search?: string;
    supplier_group?: string;
    supplier_type?: string;
    include_disabled?: boolean;
    sort_by?: 'supplier_name' | 'supplier_group' | 'country';
    sort_dir?: 'asc' | 'desc';
    country?: string;
    with_outstanding?: boolean;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-suppliers', params],
    () => api.getPurchasingSuppliers(params),
    config
  );
}

export function usePurchasingSupplierGroups(config?: SWRConfiguration) {
  return useSWR('purchasing-supplier-groups', () => api.getPurchasingSupplierGroups(), config);
}

export function usePurchasingSupplierDetail(id: number | null, config?: SWRConfiguration) {
  const key = id ? (['purchasing-supplier-detail', id] as const) : null;
  return useSWR<PurchasingSupplierDetail>(
    key,
    key ? ([, supplierId]: [string, number]) => api.getPurchasingSupplierDetail(supplierId) : null,
    config
  );
}

export function usePurchasingPaymentDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-payment-detail', id] as const : null,
    ([, paymentId]) => api.getPurchasingPaymentDetail(paymentId),
    config
  );
}

// Purchasing mutations
export function usePurchasingBillMutations() {
  const { mutate } = useSWRConfig();
  return {
    createBill: async (payload: PurchasingBillPayload) => {
      const res = await api.createPurchasingBill(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-bills');
      return res;
    },
    updateBill: async (id: number, payload: PurchasingBillPayload) => {
      const res = await api.updatePurchasingBill(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-bills');
      await mutate(['purchasing-bill-detail', id]);
      return res;
    },
    deleteBill: async (id: number, soft = true) => {
      await api.deletePurchasingBill(id, soft);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-bills');
    },
  };
}

// Accounting admin & controls
export function useFiscalPeriods(config?: SWRConfiguration) {
  return useSWR('accounting-fiscal-periods', () => api.getAccountingFiscalPeriods(), config);
}

export function useAccountingWorkflows(config?: SWRConfiguration) {
  return useSWR('accounting-workflows', () => api.getAccountingWorkflows(), config);
}

export function useAccountingPendingApprovals(config?: SWRConfiguration) {
  return useSWR('accounting-pending-approvals', () => api.getAccountingPendingApprovals(), config);
}

export function useExchangeRates(config?: SWRConfiguration) {
  return useSWR('accounting-exchange-rates', () => api.getExchangeRates(), config);
}

export function useExchangeRatesLatest(config?: SWRConfiguration) {
  return useSWR('accounting-exchange-rates-latest', () => api.getLatestExchangeRates(), config);
}

export function useAccountingControls(config?: SWRConfiguration) {
  return useSWR('accounting-controls', () => api.getAccountingControls(), config);
}

export function useAuditLog(params?: { doctype?: string; document_id?: number | string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['accounting-audit-log', params], () => api.getAuditLog(params), config);
}

export function useFxRevaluationHistory(params?: { limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['fx-revaluation-history', params], () => api.getFxRevaluationHistory(params), config);
}

export function useAccountingControlMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateControls: async (payload: any) => {
      const res = await api.updateAccountingControls(payload);
      await mutate('accounting-controls');
      return res;
    },
  };
}

export function useAccountingWorkflowMutations() {
  const { mutate } = useSWRConfig();
  return {
    createWorkflow: async (payload: any) => {
      const res = await api.createAccountingWorkflow(payload);
      await mutate('accounting-workflows');
      return res;
    },
    updateWorkflow: async (id: number | string, payload: any) => {
      const res = await api.updateAccountingWorkflow(id, payload);
      await mutate('accounting-workflows');
      return res;
    },
    deleteWorkflow: async (id: number | string) => {
      await api.deleteAccountingWorkflow(id);
      await mutate('accounting-workflows');
    },
    addWorkflowStep: async (id: number | string, payload: any) => {
      const res = await api.addAccountingWorkflowStep(id, payload);
      await mutate('accounting-workflows');
      return res;
    },
  };
}

export function useFiscalPeriodMutations() {
  const { mutate } = useSWRConfig();
  return {
    closePeriod: async (id: number | string) => {
      await api.closeFiscalPeriod(id);
      await mutate('accounting-fiscal-periods');
    },
    reopenPeriod: async (id: number | string) => {
      await api.reopenFiscalPeriod(id);
      await mutate('accounting-fiscal-periods');
    },
    generateClosingEntries: async (id: number | string) => {
      await api.generateClosingEntries(id);
      await mutate('accounting-fiscal-periods');
    },
    createPeriods: async (payload: { fiscal_year: string; frequency?: string }) => {
      const res = await api.createAccountingFiscalPeriods(payload);
      await mutate('accounting-fiscal-periods');
      return res;
    },
  };
}

export function useFxRevaluationMutations() {
  const { mutate } = useSWRConfig();
  return {
    preview: async (payload: any) => {
      const res = await api.previewFxRevaluation(payload);
      await mutate('fx-revaluation-history');
      return res;
    },
    apply: async (payload: any) => {
      const res = await api.applyFxRevaluation(payload);
      await mutate('fx-revaluation-history');
      return res;
    },
  };
}

export function useCustomerCreditMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateLimit: async (customerId: number, payload: any) => {
      const res = await api.updateAccountingCustomerCreditLimit(customerId, payload);
      await mutate(['accounting-customer-credit', customerId]);
      return res;
    },
    updateHold: async (customerId: number, payload: any) => {
      const res = await api.updateAccountingCustomerCreditHold(customerId, payload);
      await mutate(['accounting-customer-credit', customerId]);
      return res;
    },
    writeOffInvoice: async (invoiceId: number, payload: any) => api.writeOffAccountingInvoice(invoiceId, payload),
    waiveInvoice: async (invoiceId: number, payload: any) => api.waiveAccountingInvoice(invoiceId, payload),
    sendDunning: async (payload: any) => api.sendAccountingDunning(payload),
  };
}

export function useLandedCostVouchers(params?: Record<string, any>, config?: SWRConfiguration) {
  return useSWR(['inventory-landed-cost-vouchers', params], () => api.getLandedCostVouchers(params), config);
}

export function useLandedCostVoucherDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['inventory-landed-cost-voucher-detail', id] : null, () => api.getLandedCostVoucherDetail(id as number), config);
}

export function useLandedCostVoucherMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: any) => {
      const res = await api.createLandedCostVoucher(payload);
      await mutate('inventory-landed-cost-vouchers');
      return res;
    },
    update: async (id: number | string, payload: any) => {
      const res = await api.updateLandedCostVoucher(id, payload);
      await Promise.all([
        mutate('inventory-landed-cost-vouchers'),
        mutate(['inventory-landed-cost-voucher-detail', id]),
      ]);
      return res;
    },
    submit: async (id: number | string) => {
      const res = await api.submitLandedCostVoucher(id);
      await Promise.all([
        mutate('inventory-landed-cost-vouchers'),
        mutate(['inventory-landed-cost-voucher-detail', id]),
      ]);
      return res;
    },
  };
}

export function useInventoryValuation(params?: Record<string, any>, config?: SWRConfiguration) {
  return useSWR(['inventory-valuation', params], () => api.getInventoryValuation(params), config);
}

export function useInventoryValuationDetail(itemCode: string | null, params?: Record<string, any>, config?: SWRConfiguration) {
  return useSWR(
    itemCode ? ['inventory-valuation-detail', itemCode, params] as const : null,
    ([, code, valuationParams]) => api.getInventoryValuationDetail(code, valuationParams),
    config
  );
}

// Notifications
export function useNotifications(params?: { limit?: number; offset?: number; unread_only?: boolean }, config?: SWRConfiguration) {
  return useSWR(['notifications', params], () => api.getNotifications(params), { refreshInterval: 30000, ...config });
}

export function useNotificationPreferences(config?: SWRConfiguration) {
  return useSWR('notification-preferences', () => api.getNotificationPreferences(), config);
}

export function useNotificationMutations() {
  const { mutate } = useSWRConfig();
  return {
    markRead: async (id: number | string) => {
      await api.markNotificationRead(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'notifications');
    },
    markAllRead: async () => {
      await api.markAllNotificationsRead();
      await mutate((key) => Array.isArray(key) && key[0] === 'notifications');
    },
    updatePreferences: async (payload: any) => {
      const res = await api.updateNotificationPreferences(payload);
      await mutate('notification-preferences');
      return res;
    },
  };
}

// Cache metadata / exports status
export function useAccountingCacheMetadata(config?: SWRConfiguration) {
  return useSWR('accounting-cache-metadata', () => api.getAccountingCacheMetadata(), { revalidateOnFocus: false, ...config });
}

export function useReportsCacheMetadata(config?: SWRConfiguration) {
  return useSWR('reports-cache-metadata', () => api.getReportsCacheMetadata(), { revalidateOnFocus: false, ...config });
}

export function useAccountingExportStatus(config?: SWRConfiguration) {
  return useSWR('accounting-export-status', () => api.getAccountingExportStatus(), { revalidateOnFocus: false, ...config });
}
export function useExchangeRateMutations() {
  const { mutate } = useSWRConfig();
  return {
    createRate: async (payload: any) => {
      const res = await api.createExchangeRate(payload);
      await Promise.all([mutate('accounting-exchange-rates'), mutate('accounting-exchange-rates-latest')]);
      return res;
    },
    updateRate: async (id: number | string, payload: any) => {
      const res = await api.updateExchangeRate(id, payload);
      await Promise.all([mutate('accounting-exchange-rates'), mutate('accounting-exchange-rates-latest')]);
      return res;
    },
  };
}

export function useJournalEntryAdminMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: any) => {
      const res = await api.createJournalEntry(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-journal-entries');
      return res;
    },
    submit: async (id: number | string) => {
      await api.submitJournalEntry(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-journal-entries');
    },
    approve: async (id: number | string) => {
      await api.approveJournalEntry(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-journal-entries');
    },
    reject: async (id: number | string) => {
      await api.rejectJournalEntry(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-journal-entries');
    },
    post: async (id: number | string) => {
      await api.postJournalEntry(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'accounting-journal-entries');
    },
  };
}

export function usePurchasingOrderMutations() {
  const { mutate } = useSWRConfig();
  return {
    createOrder: async (payload: PurchasingOrderPayload) => {
      const res = await api.createPurchasingOrder(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-orders');
      return res;
    },
    updateOrder: async (id: number, payload: PurchasingOrderPayload) => {
      const res = await api.updatePurchasingOrder(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-orders');
      await mutate(['purchasing-order-detail', id]);
      return res;
    },
    deleteOrder: async (id: number, soft = true) => {
      await api.deletePurchasingOrder(id, soft);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-orders');
    },
  };
}

export function usePurchasingDebitNoteMutations() {
  const { mutate } = useSWRConfig();
  return {
    createDebitNote: async (payload: PurchasingDebitNotePayload) => {
      const res = await api.createPurchasingDebitNote(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-debit-notes');
      return res;
    },
    updateDebitNote: async (id: number, payload: PurchasingDebitNotePayload) => {
      const res = await api.updatePurchasingDebitNote(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-debit-notes');
      await mutate(['purchasing-debit-note-detail', id]);
      return res;
    },
    deleteDebitNote: async (id: number, soft = true) => {
      await api.deletePurchasingDebitNote(id, soft);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-debit-notes');
    },
  };
}

export function usePurchasingExpenses(
  params?: {
    account?: string;
    cost_center?: string;
    expense_type?: string;
    employee_id?: number;
    project_id?: number;
    status?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    search?: string;
    sort_by?: 'posting_date' | 'expense_date' | 'total_claimed_amount' | 'employee_name';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-expenses', params],
    () => api.getPurchasingExpenses(params),
    config
  );
}

export function usePurchasingExpenseDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-expense-detail', id] as const : null,
    ([, expenseId]) => api.getPurchasingExpenseDetail(expenseId),
    config
  );
}

export function usePurchasingExpenseTypes(
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-expense-types', params],
    () => api.getPurchasingExpenseTypes(params),
    config
  );
}

// ERPNext Expense Claims
export function useERPNextExpenses(
  params?: {
    employee_id?: number;
    project_id?: number;
    status?: string;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['erpnext-expenses', params],
    () => api.getERPNextExpenses(params),
    config
  );
}

export function useERPNextExpenseDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['erpnext-expense-detail', id] as const : null,
    ([, expenseId]) => api.getERPNextExpenseDetail(expenseId),
    config
  );
}

export function usePurchasingAging(
  params?: { as_of_date?: string; supplier?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(['purchasing-aging', params], () => api.getPurchasingAging(params), config);
}

export function usePurchasingBySupplier(
  params?: { start_date?: string; end_date?: string; limit?: number; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-by-supplier', params],
    () => api.getPurchasingBySupplier(params),
    config
  );
}

export function usePurchasingByCostCenter(
  params?: { start_date?: string; end_date?: string; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-by-cost-center', params],
    () => api.getPurchasingByCostCenter(params),
    config
  );
}

export function usePurchasingExpenseTrend(
  params?: { months?: number; interval?: 'month' | 'week'; currency?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['purchasing-expense-trend', params],
    () => api.getPurchasingExpenseTrend(params),
    config
  );
}

// Inventory mutations
export function useInventoryItemMutations() {
  const { mutate } = useSWRConfig();
  return {
    createItem: async (payload: InventoryItemPayload) => {
      const res = await api.createInventoryItem(payload);
      await mutate('inventory-items');
      return res;
    },
    updateItem: async (id: number | string, payload: Partial<InventoryItemPayload>) => {
      const res = await api.updateInventoryItem(id, payload);
      await mutate('inventory-items');
      return res;
    },
    deleteItem: async (id: number | string) => {
      await api.deleteInventoryItem(id);
      await mutate('inventory-items');
    },
  };
}

export function useInventoryWarehouseMutations() {
  const { mutate } = useSWRConfig();
  return {
    createWarehouse: async (payload: InventoryWarehousePayload) => {
      const res = await api.createInventoryWarehouse(payload);
      await mutate('inventory-warehouses');
      return res;
    },
    updateWarehouse: async (id: number | string, payload: Partial<InventoryWarehousePayload>) => {
      const res = await api.updateInventoryWarehouse(id, payload);
      await mutate('inventory-warehouses');
      return res;
    },
    deleteWarehouse: async (id: number | string) => {
      await api.deleteInventoryWarehouse(id);
      await mutate('inventory-warehouses');
    },
  };
}

export function useInventoryStockEntryCreate() {
  return {
    createStockEntry: async (payload: InventoryStockEntryPayload) => api.createInventoryStockEntry(payload),
  };
}

// Reports Domain Hooks
export function useReportsRevenueSummary(config?: SWRConfiguration) {
  return useSWR('reports-revenue-summary', () => api.getReportsRevenueSummary(), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useReportsRevenueTrend(config?: SWRConfiguration) {
  return useSWR<ReportsRevenueTrendPoint[]>('reports-revenue-trend', () => api.getReportsRevenueTrend(), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useReportsRevenueByCustomer(config?: SWRConfiguration) {
  return useSWR('reports-revenue-by-customer', () => api.getReportsRevenueByCustomer(), config);
}

export function useReportsRevenueByProduct(config?: SWRConfiguration) {
  return useSWR('reports-revenue-by-product', () => api.getReportsRevenueByProduct(), config);
}

export function useReportsExpensesSummary(config?: SWRConfiguration) {
  return useSWR('reports-expenses-summary', () => api.getReportsExpensesSummary(), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useReportsExpensesTrend(config?: SWRConfiguration) {
  return useSWR<ReportsExpenseTrendPoint[]>('reports-expenses-trend', () => api.getReportsExpensesTrend(), config);
}

export function useReportsExpensesByCategory(config?: SWRConfiguration) {
  return useSWR('reports-expenses-by-category', () => api.getReportsExpensesByCategory(), config);
}

export function useReportsExpensesByVendor(config?: SWRConfiguration) {
  return useSWR('reports-expenses-by-vendor', () => api.getReportsExpensesByVendor(), config);
}

export function useReportsProfitabilityMargins(config?: SWRConfiguration) {
  return useSWR('reports-profitability-margins', () => api.getReportsProfitabilityMargins(), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useReportsProfitabilityTrend(config?: SWRConfiguration) {
  return useSWR<ReportsProfitabilityTrendPoint[]>(
    'reports-profitability-trend',
    () => api.getReportsProfitabilityTrend(),
    config
  );
}

export function useReportsProfitabilityBySegment(config?: SWRConfiguration) {
  return useSWR('reports-profitability-by-segment', () => api.getReportsProfitabilityBySegment(), config);
}

export function useReportsCashPositionSummary(config?: SWRConfiguration) {
  return useSWR('reports-cash-position-summary', () => api.getReportsCashPositionSummary(), {
    dedupingInterval: 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useReportsCashPositionForecast(config?: SWRConfiguration) {
  return useSWR<ReportsCashPositionForecastPoint[]>(
    'reports-cash-position-forecast',
    () => api.getReportsCashPositionForecast(),
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
  );
}

export function useReportsCashPositionRunway(config?: SWRConfiguration) {
  return useSWR('reports-cash-position-runway', () => api.getReportsCashPositionRunway(), {
    dedupingInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    ...config,
  });
}

// HR Analytics
export function useHrAnalyticsOverview(params?: { company?: string }, config?: SWRConfiguration) {
  return useSWR(['hr-analytics-overview', params], () => api.getHrAnalyticsOverview(params), config);
}

export function useHrAnalyticsLeaveTrend(params?: { company?: string; months?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-analytics-leave-trend', params], () => api.getHrAnalyticsLeaveTrend(params), config);
}

export function useHrAnalyticsAttendanceTrend(params?: { company?: string; days?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-analytics-attendance-trend', params], () => api.getHrAnalyticsAttendanceTrend(params), config);
}

export function useHrAnalyticsPayrollSummary(
  params?: { company?: string; department?: string; start_date?: string; end_date?: string; status?: string },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-payroll-summary', params], () => api.getHrAnalyticsPayrollSummary(params), config);
}

export function useHrAnalyticsPayrollTrend(
  params?: { company?: string; department?: string; start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-payroll-trend', params], () => api.getHrAnalyticsPayrollTrend(params), config);
}

export function useHrAnalyticsPayrollComponents(
  params?: { component_type?: string; company?: string; start_date?: string; end_date?: string; limit?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-payroll-components', params], () => api.getHrAnalyticsPayrollComponents(params), config);
}

export function useHrAnalyticsRecruitmentFunnel(
  params?: { company?: string; job_title?: string; start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-recruitment-funnel', params], () => api.getHrAnalyticsRecruitmentFunnel(params), config);
}

export function useHrAnalyticsAppraisalStatus(
  params?: { company?: string; department?: string; start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-appraisal-status', params], () => api.getHrAnalyticsAppraisalStatus(params), config);
}

export function useHrAnalyticsLifecycleEvents(
  params?: { company?: string; start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(['hr-analytics-lifecycle-events', params], () => api.getHrAnalyticsLifecycleEvents(params), config);
}

export function useEmployees(
  params?: { search?: string; department?: string; status?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['employees', params], () => api.getEmployees(params), config);
}

// HR Domain
export function useHrLeaveTypes(
  params?: { search?: string; is_lwp?: boolean; is_carry_forward?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-types', params], () => api.getHrLeaveTypes(params), config);
}

export function useHrLeaveTypeDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-leave-type-detail', id] as const : null,
    ([, leaveTypeId]) => api.getHrLeaveTypeDetail(leaveTypeId),
    config
  );
}

export function useHrHolidayLists(
  params?: { search?: string; company?: string; from_date?: string; to_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-holiday-lists', params], () => api.getHrHolidayLists(params), config);
}

export function useHrHolidayListDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-holiday-list-detail', id] as const : null,
    ([, holidayListId]) => api.getHrHolidayListDetail(holidayListId),
    config
  );
}

export function useHrLeavePolicies(params?: { search?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-leave-policies', params], () => api.getHrLeavePolicies(params), config);
}

export function useHrLeavePolicyDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-leave-policy-detail', id] as const : null,
    ([, leavePolicyId]) => api.getHrLeavePolicyDetail(leavePolicyId),
    config
  );
}

export function useHrLeaveAllocations(
  params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-allocations', params], () => api.getHrLeaveAllocations(params), config);
}

export function useHrLeaveAllocationDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-leave-allocation-detail', id] as const : null,
    ([, allocationId]) => api.getHrLeaveAllocationDetail(allocationId),
    config
  );
}

export function useHrLeaveApplications(
  params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-applications', params], () => api.getHrLeaveApplications(params), config);
}

export function useHrLeaveApplicationDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-leave-application-detail', id] as const : null,
    ([, applicationId]) => api.getHrLeaveApplicationDetail(applicationId),
    config
  );
}

export function useHrLeaveApplicationMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: HrLeaveApplicationPayload) => {
      const res = await api.createHrLeaveApplication(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
      return res;
    },
    update: async (id: number | string, payload: Partial<HrLeaveApplicationPayload>) => {
      const res = await api.updateHrLeaveApplication(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
      await mutate(['hr-leave-application-detail', id]);
      return res;
    },
    approve: async (id: number | string) => {
      await api.approveHrLeaveApplication(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
      await mutate(['hr-leave-application-detail', id]);
    },
    reject: async (id: number | string) => {
      await api.rejectHrLeaveApplication(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
      await mutate(['hr-leave-application-detail', id]);
    },
    cancel: async (id: number | string) => {
      await api.cancelHrLeaveApplication(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
      await mutate(['hr-leave-application-detail', id]);
    },
    bulkApprove: async (application_ids: (number | string)[]) => {
      await api.bulkApproveHrLeaveApplications({ application_ids });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
    },
    bulkReject: async (application_ids: (number | string)[]) => {
      await api.bulkRejectHrLeaveApplications({ application_ids });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-applications');
    },
  };
}

export function useHrLeaveAllocationMutations() {
  const { mutate } = useSWRConfig();
  return {
    bulkCreate: async (payload: { employee_ids: number[]; leave_policy_id: number; from_date: string; to_date: string; company?: string }) => {
      const res = await api.bulkCreateHrLeaveAllocations(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-leave-allocations');
      return res;
    },
  };
}

export function useHrShiftTypes(
  params?: { search?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-shift-types', params], () => api.getHrShiftTypes(params), config);
}

export function useHrShiftTypeDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-shift-type-detail', id] as const : null,
    ([, shiftTypeId]) => api.getHrShiftTypeDetail(shiftTypeId),
    config
  );
}

export function useHrShiftAssignments(
  params?: { employee_id?: number; shift_type_id?: number; start_date?: string; end_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-shift-assignments', params], () => api.getHrShiftAssignments(params), config);
}

export function useHrShiftAssignmentDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-shift-assignment-detail', id] as const : null,
    ([, assignmentId]) => api.getHrShiftAssignmentDetail(assignmentId),
    config
  );
}

export function useHrAttendances(
  params?: { employee_id?: number; status?: string; attendance_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-attendances', params], () => api.getHrAttendances(params), config);
}

export function useHrAttendanceDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-attendance-detail', id] as const : null,
    ([, attendanceId]) => api.getHrAttendanceDetail(attendanceId),
    config
  );
}

export function useHrAttendanceMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: HrAttendancePayload) => {
      const res = await api.createHrAttendance(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendances');
      return res;
    },
    update: async (id: number | string, payload: Partial<HrAttendancePayload>) => {
      const res = await api.updateHrAttendance(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendances');
      await mutate(['hr-attendance-detail', id]);
      return res;
    },
    checkIn: async (id: number | string, payload?: { latitude?: number; longitude?: number; device_info?: string }) => {
      const res = await api.checkInHrAttendance(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendances');
      await mutate(['hr-attendance-detail', id]);
      return res;
    },
    checkOut: async (id: number | string, payload?: { latitude?: number; longitude?: number }) => {
      const res = await api.checkOutHrAttendance(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendances');
      await mutate(['hr-attendance-detail', id]);
      return res;
    },
    bulkMark: async (payload: { employee_ids: (number | string)[]; attendance_date: string; status: string }) => {
      await api.bulkMarkAttendance(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendances');
    },
  };
}

export function useHrAttendanceRequests(
  params?: { employee_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-attendance-requests', params], () => api.getHrAttendanceRequests(params), config);
}

export function useHrAttendanceRequestDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-attendance-request-detail', id] as const : null,
    ([, requestId]) => api.getHrAttendanceRequestDetail(requestId),
    config
  );
}

export function useHrAttendanceRequestMutations() {
  const { mutate } = useSWRConfig();
  return {
    approve: async (id: number | string) => {
      await api.approveHrAttendanceRequest(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendance-requests');
      await mutate(['hr-attendance-request-detail', id]);
    },
    reject: async (id: number | string) => {
      await api.rejectHrAttendanceRequest(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendance-requests');
      await mutate(['hr-attendance-request-detail', id]);
    },
    bulkApprove: async (request_ids: (number | string)[]) => {
      await api.bulkApproveHrAttendanceRequests({ request_ids });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendance-requests');
    },
    bulkReject: async (request_ids: (number | string)[]) => {
      await api.bulkRejectHrAttendanceRequests({ request_ids });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-attendance-requests');
    },
  };
}

export function useHrJobOpenings(
  params?: { status?: string; company?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-job-openings', params], () => api.getHrJobOpenings(params), config);
}

export function useHrJobOpeningDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-job-opening-detail', id] as const : null,
    ([, jobOpeningId]) => api.getHrJobOpeningDetail(jobOpeningId),
    config
  );
}

export function useHrJobOpeningMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: HrJobOpeningPayload) => {
      const res = await api.createHrJobOpening(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-openings');
      return res;
    },
    update: async (id: number | string, payload: Partial<HrJobOpeningPayload>) => {
      const res = await api.updateHrJobOpening(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-openings');
      await mutate(['hr-job-opening-detail', id]);
      return res;
    },
    delete: async (id: number | string) => {
      await api.deleteHrJobOpening(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-openings');
    },
  };
}

export function useHrJobApplicants(
  params?: { status?: string; job_title?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-job-applicants', params], () => api.getHrJobApplicants(params), config);
}

export function useHrJobApplicantDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-job-applicant-detail', id] as const : null,
    ([, applicantId]) => api.getHrJobApplicantDetail(applicantId),
    config
  );
}

export function useHrJobApplicantMutations() {
  const { mutate } = useSWRConfig();
  return {
    screen: async (id: number | string) => {
      await api.screenHrJobApplicant(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      await mutate(['hr-job-applicant-detail', id]);
    },
    scheduleInterview: async (id: number | string, payload: { interview_date: string; interviewer: string; location?: string; notes?: string }) => {
      await api.scheduleInterviewForHrJobApplicant(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      await mutate(['hr-job-applicant-detail', id]);
    },
    makeOffer: async (id: number | string, payload: { offer_id: number | string }) => {
      await api.makeOfferForHrJobApplicant(id, payload);
      await mutate((key) => Array.isArray(key) && (key[0] === 'hr-job-applicants' || key[0] === 'hr-job-offers'));
      await mutate(['hr-job-applicant-detail', id]);
    },
    withdraw: async (id: number | string) => {
      await api.withdrawHrJobApplicant(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      await mutate(['hr-job-applicant-detail', id]);
    },
  };
}

export function useHrJobOffers(
  params?: { status?: string; company?: string; job_applicant?: string; offer_date_from?: string; offer_date_to?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-job-offers', params], () => api.getHrJobOffers(params), config);
}

export function useHrJobOfferDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-job-offer-detail', id] as const : null,
    ([, offerId]) => api.getHrJobOfferDetail(offerId),
    config
  );
}

export function useHrInterviews(
  params?: { job_applicant_id?: number; status?: string; interviewer?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-interviews', params], () => api.getHrInterviews(params), config);
}

export function useHrInterviewDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-interview-detail', id] as const : null,
    ([, interviewId]) => api.getHrInterviewDetail(interviewId),
    config
  );
}

export function useHrInterviewMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: HrInterviewPayload) => {
      const res = await api.createHrInterview(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      return res;
    },
    update: async (id: number | string, payload: Partial<HrInterviewPayload>) => {
      const res = await api.updateHrInterview(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      return res;
    },
    complete: async (id: number | string, payload: { feedback?: string; rating?: number; result?: string }) => {
      const res = await api.completeHrInterview(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
      return res;
    },
    cancel: async (id: number | string) => {
      await api.cancelHrInterview(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
    },
    markNoShow: async (id: number | string) => {
      await api.markNoShowHrInterview(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-applicants');
    },
  };
}

export function useHrJobOfferMutations() {
  const { mutate } = useSWRConfig();
  return {
    send: async (id: number | string) => {
      await api.sendHrJobOffer(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-offers');
      await mutate(['hr-job-offer-detail', id]);
    },
    void: async (id: number | string, payload: { void_reason: string; voided_at?: string }) => {
      await api.voidHrJobOffer(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-offers');
      await mutate(['hr-job-offer-detail', id]);
    },
    accept: async (id: number | string) => {
      await api.acceptHrJobOffer(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-offers');
      await mutate(['hr-job-offer-detail', id]);
    },
    reject: async (id: number | string) => {
      await api.rejectHrJobOffer(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-offers');
      await mutate(['hr-job-offer-detail', id]);
    },
    bulkSend: async (offer_ids: (number | string)[], delivery_method?: string) => {
      await api.bulkSendHrJobOffers({ offer_ids, delivery_method });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-job-offers');
    },
  };
}

export function useHrSalaryComponents(
  params?: { component_type?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-components', params], () => api.getHrSalaryComponents(params), config);
}

export function useHrSalaryComponentDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-salary-component-detail', id] as const : null,
    ([, componentId]) => api.getHrSalaryComponentDetail(componentId),
    config
  );
}

export function useHrSalaryStructures(
  params?: { company?: string; is_active?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-structures', params], () => api.getHrSalaryStructures(params), config);
}

export function useHrSalaryStructureDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-salary-structure-detail', id] as const : null,
    ([, structureId]) => api.getHrSalaryStructureDetail(structureId),
    config
  );
}

export function useHrSalaryStructureAssignments(
  params?: { employee_id?: number; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-structure-assignments', params], () => api.getHrSalaryStructureAssignments(params), config);
}

export function useHrSalaryStructureAssignmentDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-salary-structure-assignment-detail', id] as const : null,
    ([, assignmentId]) => api.getHrSalaryStructureAssignmentDetail(assignmentId),
    config
  );
}

export function useHrPayrollEntries(
  params?: { company?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-payroll-entries', params], () => api.getHrPayrollEntries(params), config);
}

export function useHrPayrollEntryDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-payroll-entry-detail', id] as const : null,
    ([, payrollEntryId]) => api.getHrPayrollEntryDetail(payrollEntryId),
    config
  );
}

export function useHrPayrollEntryMutations() {
  const { mutate } = useSWRConfig();
  return {
    generateSlips: async (
      id: number | string,
      payload: { company: string; department?: string | null; branch?: string | null; designation?: string | null; start_date: string; end_date: string; regenerate?: boolean }
    ) => {
      await api.generateHrPayrollSlips(id, payload);
      await mutate((key) => Array.isArray(key) && (key[0] === 'hr-payroll-entries' || key[0] === 'hr-salary-slips'));
      await mutate(['hr-payroll-entry-detail', id]);
    },
    regenerateSlips: async (id: number | string, payload: { overwrite_drafts?: boolean }) => {
      await api.regenerateHrPayrollSlips(id, payload);
      await mutate((key) => Array.isArray(key) && (key[0] === 'hr-payroll-entries' || key[0] === 'hr-salary-slips'));
      await mutate(['hr-payroll-entry-detail', id]);
    },
  };
}

export function useHrSalarySlips(
  params?: { employee_id?: number; status?: string; start_date?: string; end_date?: string; company?: string; payroll_entry?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-slips', params], () => api.getHrSalarySlips(params), config);
}

export function useHrSalarySlipDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-salary-slip-detail', id] as const : null,
    ([, salarySlipId]) => api.getHrSalarySlipDetail(salarySlipId),
    config
  );
}

export function useHrSalarySlipMutations() {
  const { mutate } = useSWRConfig();
  return {
    markPaid: async (id: number | string, payload: { payment_reference?: string; payment_mode?: string; paid_at?: string }) => {
      await api.markHrSalarySlipPaid(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-salary-slips');
      await mutate(['hr-salary-slip-detail', id]);
    },
    void: async (id: number | string, payload: { void_reason: string; voided_at?: string }) => {
      await api.voidHrSalarySlip(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-salary-slips');
      await mutate(['hr-salary-slip-detail', id]);
    },
    payoutPayrollEntry: async (entryId: number | string, payload: import('@/lib/api').HrPayrollPayoutRequest) => {
      const res = await api.initiateHrPayrollPayouts(entryId, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-salary-slips');
      return res;
    },
    handoffPayrollEntry: async (entryId: number | string, payload: import('@/lib/api').HrPayrollPayoutRequest) => {
      const res = await api.handoffHrPayrollToBooks(entryId, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-salary-slips');
      return res;
    },
    exportRegister: async (params?: { employee_id?: number; status?: string; start_date?: string; end_date?: string; company?: string; payroll_entry?: string }) => {
      return api.exportHrSalarySlipRegister(params);
    },
  };
}

export function useHrTrainingPrograms(params?: { search?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-training-programs', params], () => api.getHrTrainingPrograms(params), config);
}

export function useHrTrainingProgramDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-training-program-detail', id] as const : null,
    ([, programId]) => api.getHrTrainingProgramDetail(programId),
    config
  );
}

export function useHrTrainingEvents(
  params?: { status?: string; company?: string; start_date?: string; end_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-training-events', params], () => api.getHrTrainingEvents(params), config);
}

export function useHrTrainingEventDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-training-event-detail', id] as const : null,
    ([, eventId]) => api.getHrTrainingEventDetail(eventId),
    config
  );
}

export function useHrTrainingEventMutations() {
  const { mutate } = useSWRConfig();
  return {
    enroll: async (id: number | string, employee_ids: (number | string)[]) => {
      await api.enrollHrTrainingEvent(id, { employee_ids });
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-training-events');
      await mutate(['hr-training-event-detail', id]);
    },
    complete: async (id: number | string) => {
      await api.completeHrTrainingEvent(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-training-events');
      await mutate(['hr-training-event-detail', id]);
    },
    update: async (id: number | string, payload: Partial<HrTrainingEventPayload>) => {
      const res = await api.updateHrTrainingEvent(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-training-events');
      await mutate(['hr-training-event-detail', id]);
      return res;
    },
  };
}

export function useHrTrainingResults(
  params?: { employee_id?: number; training_event?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-training-results', params], () => api.getHrTrainingResults(params), config);
}

export function useHrTrainingResultDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-training-result-detail', id] as const : null,
    ([, resultId]) => api.getHrTrainingResultDetail(resultId),
    config
  );
}

export function useHrTrainingResultMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (payload: HrTrainingResultPayload) => {
      const res = await api.createHrTrainingResult(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-training-results');
      return res;
    },
  };
}

export function useHrAppraisalTemplates(
  params?: { company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-appraisal-templates', params], () => api.getHrAppraisalTemplates(params), config);
}

export function useHrAppraisalTemplateDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-appraisal-template-detail', id] as const : null,
    ([, templateId]) => api.getHrAppraisalTemplateDetail(templateId),
    config
  );
}

export function useHrAppraisals(
  params?: { employee_id?: number; status?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-appraisals', params], () => api.getHrAppraisals(params), config);
}

export function useHrAppraisalDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-appraisal-detail', id] as const : null,
    ([, appraisalId]) => api.getHrAppraisalDetail(appraisalId),
    config
  );
}

export function useHrAppraisalMutations() {
  const { mutate } = useSWRConfig();
  return {
    submit: async (id: number | string) => {
      await api.submitHrAppraisal(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-appraisals');
      await mutate(['hr-appraisal-detail', id]);
    },
    review: async (id: number | string) => {
      await api.reviewHrAppraisal(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-appraisals');
      await mutate(['hr-appraisal-detail', id]);
    },
    close: async (id: number | string) => {
      await api.closeHrAppraisal(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-appraisals');
      await mutate(['hr-appraisal-detail', id]);
    },
  };
}

export function useHrEmployeeOnboardings(
  params?: { employee_id?: number; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-employee-onboardings', params], () => api.getHrEmployeeOnboardings(params), config);
}

export function useHrEmployeeOnboardingDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-employee-onboarding-detail', id] as const : null,
    ([, onboardingId]) => api.getHrEmployeeOnboardingDetail(onboardingId),
    config
  );
}

export function useHrEmployeeSeparations(
  params?: { employee_id?: number; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-employee-separations', params], () => api.getHrEmployeeSeparations(params), config);
}

export function useHrEmployeeSeparationDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-employee-separation-detail', id] as const : null,
    ([, separationId]) => api.getHrEmployeeSeparationDetail(separationId),
    config
  );
}

export function useHrEmployeePromotions(
  params?: { employee_id?: number; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-employee-promotions', params], () => api.getHrEmployeePromotions(params), config);
}

export function useHrEmployeePromotionDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-employee-promotion-detail', id] as const : null,
    ([, promotionId]) => api.getHrEmployeePromotionDetail(promotionId),
    config
  );
}

export function useHrEmployeeTransfers(
  params?: { employee_id?: number; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-employee-transfers', params], () => api.getHrEmployeeTransfers(params), config);
}

export function useHrEmployeeTransferDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-employee-transfer-detail', id] as const : null,
    ([, transferId]) => api.getHrEmployeeTransferDetail(transferId),
    config
  );
}

export function useHrLifecycleMutations() {
  const { mutate } = useSWRConfig();
  const refresh = (keyName: string) => mutate((key) => Array.isArray(key) && key[0] === keyName);
  return {
    updateOnboardingStatus: async (id: number | string, status: string) => {
      await api.updateHrEmployeeOnboarding(id, { status });
      await refresh('hr-employee-onboardings');
      await mutate(['hr-employee-onboarding-detail', id]);
    },
    updateSeparationStatus: async (id: number | string, status: string) => {
      await api.updateHrEmployeeSeparation(id, { status });
      await refresh('hr-employee-separations');
      await mutate(['hr-employee-separation-detail', id]);
    },
    updatePromotionStatus: async (id: number | string, status: string) => {
      await api.updateHrEmployeePromotion(id, { status });
      await refresh('hr-employee-promotions');
      await mutate(['hr-employee-promotion-detail', id]);
    },
    updateTransferStatus: async (id: number | string, status: string) => {
      await api.updateHrEmployeeTransfer(id, { status });
      await refresh('hr-employee-transfers');
      await mutate(['hr-employee-transfer-detail', id]);
    },
  };
}

// Customer write mutations (local-only)
export function useCustomerMutations() {
  const { mutate } = useSWRConfig();
  return {
    createCustomer: async (payload: CustomerWritePayload) => {
      const res = await api.createCustomer(payload);
      await mutate('customers');
      return res;
    },
    updateCustomer: async (id: number, payload: CustomerWritePayload) => {
      const res = await api.updateCustomer(id, payload);
      await mutate('customers');
      await mutate(['finance-customer-detail', id]);
      return res;
    },
    deleteCustomer: async (id: number, soft = true) => {
      await api.deleteCustomer(id, soft);
      await mutate('customers');
    },
  };
}

export function useCustomerSubscriptionMutations() {
  const { mutate } = useSWRConfig();
  return {
    createSubscription: async (payload: CustomerSubscriptionPayload) => {
      const res = await api.createCustomerSubscription(payload);
      await mutate('customers');
      return res;
    },
    updateSubscription: async (id: number, payload: CustomerSubscriptionPayload) => {
      const res = await api.updateCustomerSubscription(id, payload);
      await mutate('customers');
      return res;
    },
    deleteSubscription: async (id: number, soft = true) => {
      await api.deleteCustomerSubscription(id, soft);
      await mutate('customers');
    },
  };
}

export function useCustomerInvoiceMutations() {
  const { mutate } = useSWRConfig();
  return {
    createInvoice: async (payload: CustomerInvoicePayload) => {
      const res = await api.createCustomerInvoice(payload);
      await mutate('customers');
      return res;
    },
    updateInvoice: async (id: number, payload: CustomerInvoicePayload) => {
      const res = await api.updateCustomerInvoice(id, payload);
      await mutate('customers');
      return res;
    },
    deleteInvoice: async (id: number, soft = true) => {
      await api.deleteCustomerInvoice(id, soft);
      await mutate('customers');
    },
  };
}

export function useCustomerPaymentMutations() {
  const { mutate } = useSWRConfig();
  return {
    createPayment: async (payload: CustomerPaymentPayload) => {
      const res = await api.createCustomerPayment(payload);
      await mutate('customers');
      return res;
    },
    updatePayment: async (id: number, payload: CustomerPaymentPayload) => {
      const res = await api.updateCustomerPayment(id, payload);
      await mutate('customers');
      return res;
    },
    deletePayment: async (id: number, soft = true) => {
      await api.deleteCustomerPayment(id, soft);
      await mutate('customers');
    },
  };
}

// ============================================================================
// BOOKS SETTINGS HOOKS
// ============================================================================

export function useBooksSettings(params?: { company?: string }) {
  return useSWR(
    ['books-settings', params?.company],
    () => api.getBooksSettings(params),
    { revalidateOnFocus: false }
  );
}

export function useNumberFormats(params?: { company?: string; document_type?: string; is_active?: boolean }) {
  return useSWR(
    ['number-formats', params?.company, params?.document_type, params?.is_active],
    () => api.getNumberFormats(params),
    { revalidateOnFocus: false }
  );
}

export function useCurrencies(params?: { is_enabled?: boolean }) {
  return useSWR(
    ['currencies', params?.is_enabled],
    () => api.getCurrencies(params),
    { revalidateOnFocus: false }
  );
}

export function useBooksSettingsMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateSettings: async (body: Parameters<typeof api.updateBooksSettings>[0], company?: string) => {
      const res = await api.updateBooksSettings(body, company);
      await mutate((key) => Array.isArray(key) && key[0] === 'books-settings');
      return res;
    },
    seedDefaults: async () => {
      const res = await api.seedBooksDefaults();
      await mutate((key) => Array.isArray(key) && (key[0] === 'books-settings' || key[0] === 'number-formats' || key[0] === 'currencies'));
      return res;
    },
  };
}

export function useNumberFormatMutations() {
  const { mutate } = useSWRConfig();
  return {
    createFormat: async (body: Parameters<typeof api.createNumberFormat>[0]) => {
      const res = await api.createNumberFormat(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'number-formats');
      return res;
    },
    updateFormat: async (id: number, body: Parameters<typeof api.updateNumberFormat>[1]) => {
      const res = await api.updateNumberFormat(id, body);
      await mutate((key) => Array.isArray(key) && key[0] === 'number-formats');
      return res;
    },
    deleteFormat: async (id: number) => {
      await api.deleteNumberFormat(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'number-formats');
    },
    previewFormat: async (body: Parameters<typeof api.previewNumberFormat>[0]) => {
      return api.previewNumberFormat(body);
    },
    resetSequence: async (id: number, newStartingNumber: number) => {
      const res = await api.resetNumberSequence(id, { new_starting_number: newStartingNumber });
      await mutate((key) => Array.isArray(key) && key[0] === 'number-formats');
      return res;
    },
  };
}

export function useCurrencyMutations() {
  const { mutate } = useSWRConfig();
  return {
    createCurrency: async (body: Parameters<typeof api.createCurrency>[0]) => {
      const res = await api.createCurrency(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'currencies');
      return res;
    },
    updateCurrency: async (code: string, body: Parameters<typeof api.updateCurrency>[1]) => {
      const res = await api.updateCurrency(code, body);
      await mutate((key) => Array.isArray(key) && key[0] === 'currencies');
      return res;
    },
    formatAmount: async (amount: number, currencyCode: string, showSymbol?: boolean) => {
      return api.formatAmount({ amount, currency_code: currencyCode, show_symbol: showSymbol });
    },
  };
}

// ============================================================================
// HR SETTINGS HOOKS
// ============================================================================

export function useHRSettings(params?: { company?: string }) {
  return useSWR(
    ['hr-settings', params?.company],
    () => api.getHRSettings(params),
    { revalidateOnFocus: false }
  );
}

export function useHolidayCalendars(params?: { company?: string; year?: number; is_active?: boolean }) {
  return useSWR(
    ['holiday-calendars', params?.company, params?.year, params?.is_active],
    () => api.getHolidayCalendars(params),
    { revalidateOnFocus: false }
  );
}

export function useSalaryBands(params?: { company?: string; is_active?: boolean }) {
  return useSWR(
    ['salary-bands', params?.company, params?.is_active],
    () => api.getSalaryBands(params),
    { revalidateOnFocus: false }
  );
}

export function useHRSettingsMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateSettings: async (body: Parameters<typeof api.updateHRSettings>[0], company?: string) => {
      const res = await api.updateHRSettings(body, company);
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-settings');
      return res;
    },
    seedDefaults: async () => {
      const res = await api.seedHRDefaults();
      await mutate((key) => Array.isArray(key) && key[0] === 'hr-settings');
      return res;
    },
  };
}

// ============================================================================
// FLEET MANAGEMENT HOOKS
// ============================================================================

export function useFleetVehicles(
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
    make?: string;
    model?: string;
    fuel_type?: string;
    employee_id?: number;
    is_active?: boolean;
    sort_by?: 'license_plate' | 'make' | 'model' | 'acquisition_date' | 'vehicle_value' | 'odometer_value';
    sort_order?: 'asc' | 'desc';
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['fleet-vehicles', params],
    () => api.getVehicles(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetVehicle(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['fleet-vehicle', id] : null,
    () => api.getVehicle(id!),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetSummary(config?: SWRConfiguration) {
  return useSWR(
    ['fleet-summary'],
    () => api.getVehicleSummary(),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetInsuranceExpiring(days = 30, config?: SWRConfiguration) {
  return useSWR(
    ['fleet-insurance-expiring', days],
    () => api.getVehiclesInsuranceExpiring(days),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetMakes(config?: SWRConfiguration) {
  return useSWR(
    ['fleet-makes'],
    () => api.getVehicleMakes(),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetFuelTypes(config?: SWRConfiguration) {
  return useSWR(
    ['fleet-fuel-types'],
    () => api.getFuelTypes(),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetVehiclesByDriver(employeeId: number | null, config?: SWRConfiguration) {
  return useSWR(
    employeeId ? ['fleet-vehicles-by-driver', employeeId] : null,
    () => api.getVehiclesByDriver(employeeId!),
    { revalidateOnFocus: false, ...config }
  );
}

export function useFleetMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateVehicle: async (id: number | string, body: Parameters<typeof api.updateVehicle>[1]) => {
      const res = await api.updateVehicle(id, body);
      await mutate((key) => Array.isArray(key) && (key[0] === 'fleet-vehicles' || key[0] === 'fleet-vehicle' || key[0] === 'fleet-summary'));
      return res;
    },
  };
}

// ============================================================================
// SUPPORT SETTINGS HOOKS
// ============================================================================

export function useSupportSettings(params?: { company?: string }) {
  return useSWR(
    ['support-settings', params?.company],
    () => api.getSupportSettings(params),
    { revalidateOnFocus: false }
  );
}

export function useSupportQueues(params?: { company?: string; is_active?: boolean; include_system?: boolean }) {
  return useSWR(
    ['support-queues', params?.company, params?.is_active, params?.include_system],
    () => api.getSupportQueues(params),
    { revalidateOnFocus: false }
  );
}

export function useEscalationPolicies(params?: { company?: string; is_active?: boolean }) {
  return useSWR(
    ['escalation-policies', params?.company, params?.is_active],
    () => api.getEscalationPolicies(params),
    { revalidateOnFocus: false }
  );
}

export function useSupportSettingsMutations() {
  const { mutate } = useSWRConfig();
  return {
    updateSettings: async (body: Parameters<typeof api.updateSupportSettings>[0], company?: string) => {
      const res = await api.updateSupportSettings(body, company);
      await mutate((key) => Array.isArray(key) && key[0] === 'support-settings');
      return res;
    },
    seedDefaults: async () => {
      const res = await api.seedSupportDefaults();
      await mutate((key) => Array.isArray(key) && (key[0] === 'support-settings' || key[0] === 'support-queues'));
      return res;
    },
  };
}

// ==========================================
// Payment Gateway Integration Hooks
// ==========================================

export function useGatewayPayments(
  params?: { status?: string; provider?: string; customer_id?: number; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    ['gateway-payments', params?.status, params?.provider, params?.customer_id, params?.limit, params?.offset],
    () => api.getGatewayPayments(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useGatewayPayment(reference: string | null, config?: SWRConfiguration) {
  return useSWR(
    reference ? ['gateway-payment', reference] as const : null,
    ([, paymentRef]) => api.getGatewayPayment(paymentRef),
    config
  );
}

export function useGatewayTransfers(
  params?: { status?: string; transfer_type?: string; provider?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    ['gateway-transfers', params?.status, params?.transfer_type, params?.provider, params?.limit, params?.offset],
    () => api.getGatewayTransfers(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useGatewayTransfer(reference: string | null, config?: SWRConfiguration) {
  return useSWR(
    reference ? ['gateway-transfer', reference] as const : null,
    ([, transferRef]) => api.getGatewayTransfer(transferRef),
    config
  );
}

export function useBanks(params?: { country?: string; provider?: string }, config?: SWRConfiguration) {
  return useSWR(
    ['banks', params?.country, params?.provider],
    () => api.getBanks(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useOpenBankingConnections(
  params?: { customer_id?: number; provider?: string; status?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['open-banking-connections', params?.customer_id, params?.provider, params?.status],
    () => api.getOpenBankingConnections(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useOpenBankingConnection(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['open-banking-connection', id] as const : null,
    ([, connectionId]) => api.getOpenBankingConnection(connectionId),
    config
  );
}

export function useOpenBankingTransactions(
  id: number | null,
  params?: { start_date?: string; end_date?: string; limit?: number },
  config?: SWRConfiguration
) {
  const key = id ? (['open-banking-transactions', id, params?.start_date, params?.end_date, params?.limit] as const) : null;
  return useSWR(
    key,
    key ? ([, connectionId]) => api.getOpenBankingTransactions(connectionId, params) : null,
    config
  );
}

export function useWebhookEvents(
  params?: { provider?: string; event_type?: string; status?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(
    ['webhook-events', params?.provider, params?.event_type, params?.status, params?.limit, params?.offset],
    () => api.getWebhookEvents(params),
    { revalidateOnFocus: false, ...config }
  );
}

export function useGatewayMutations() {
  const { mutate } = useSWRConfig();
  return {
    initializePayment: async (body: Parameters<typeof api.initializePayment>[0]) => {
      const res = await api.initializePayment(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'gateway-payments');
      return res;
    },
    verifyPayment: async (reference: string) => {
      const res = await api.verifyPayment(reference);
      await mutate((key) => Array.isArray(key) && (key[0] === 'gateway-payments' || key[0] === 'gateway-payment'));
      return res;
    },
    refundPayment: async (reference: string, amount?: number) => {
      const res = await api.refundPayment(reference, amount);
      await mutate((key) => Array.isArray(key) && (key[0] === 'gateway-payments' || key[0] === 'gateway-payment'));
      return res;
    },
    initiateTransfer: async (body: Parameters<typeof api.initiateTransfer>[0]) => {
      const res = await api.initiateTransfer(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'gateway-transfers');
      return res;
    },
    verifyTransfer: async (reference: string) => {
      const res = await api.verifyTransfer(reference);
      await mutate((key) => Array.isArray(key) && (key[0] === 'gateway-transfers' || key[0] === 'gateway-transfer'));
      return res;
    },
    payPayrollTransfers: async (payload: { transfer_ids: number[]; provider?: string }) => {
      const res = await api.payPayrollTransfers(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'gateway-transfers');
      return res;
    },
    resolveAccount: async (body: Parameters<typeof api.resolveAccount>[0], provider?: string) => {
      return api.resolveAccount(body, provider);
    },
    unlinkOpenBankingAccount: async (id: number) => {
      const res = await api.unlinkOpenBankingAccount(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'open-banking-connections');
      return res;
    },
  };
}

// Admin Settings
export function useSettingsGroups(config?: SWRConfiguration) {
  return useSWR('settings-groups', () => api.getSettingsGroups(), config);
}

export function useSettings(group: string | null, config?: SWRConfiguration) {
  return useSWR(
    group ? ['settings', group] as const : null,
    ([, groupName]) => api.getSettings(groupName),
    config
  );
}

export function useSettingsSchema(group: string | null, config?: SWRConfiguration) {
  return useSWR(
    group ? ['settings-schema', group] as const : null,
    ([, groupName]) => api.getSettingsSchema(groupName),
    config
  );
}

export function useSettingsAuditLog(
  params?: { group?: string; skip?: number; limit?: number },
  config?: SWRConfiguration
) {
  return useSWR(['settings-audit', params], () => api.getSettingsAuditLog(params), config);
}

export function useSettingsMutations() {
  const { mutate } = useSWRConfig();
  return {
    update: async (group: string, data: Record<string, unknown>) => {
      const res = await api.updateSettings(group, data);
      await mutate(['settings', group]);
      await mutate((key) => Array.isArray(key) && key[0] === 'settings-audit');
      return res;
    },
    test: async (group: string, data: Record<string, unknown>) => {
      return api.testSettings(group, data);
    },
    getTestStatus: async (jobId: string) => {
      return api.getSettingsTestStatus(jobId);
    },
  };
}

// Inventory Domain Hooks
export function useInventoryItems(
  params?: { item_group?: string; warehouse?: string; has_stock?: boolean; search?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-items', params], () => api.getInventoryItems(params), config);
}

export function useInventoryItemDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['inventory-item-detail', id] as const : null,
    ([, itemId]) => api.getInventoryItemDetail(itemId),
    config
  );
}

export function useInventoryWarehouses(
  params?: { include_disabled?: boolean; is_group?: boolean; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-warehouses', params], () => api.getInventoryWarehouses(params), config);
}

export function useInventoryWarehouseDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['inventory-warehouse-detail', id] as const : null,
    ([, warehouseId]) => api.getInventoryWarehouseDetail(warehouseId),
    config
  );
}

export function useInventoryStockEntries(
  params?: { stock_entry_type?: string; from_warehouse?: string; to_warehouse?: string; start_date?: string; end_date?: string; docstatus?: number; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-stock-entries', params], () => api.getInventoryStockEntries(params), config);
}

export function useInventoryStockEntryDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['inventory-stock-entry-detail', id] as const : null,
    ([, entryId]) => api.getInventoryStockEntryDetail(entryId),
    config
  );
}

export function useInventoryStockLedger(
  params?: { item_code?: string; warehouse?: string; voucher_type?: string; voucher_no?: string; start_date?: string; end_date?: string; include_cancelled?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-stock-ledger', params], () => api.getInventoryStockLedger(params), config);
}

export function useInventoryStockSummary(
  params?: { warehouse?: string; item_group?: string },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-stock-summary', params], () => api.getInventoryStockSummary(params), config);
}

export function useInventoryMutations() {
  const { mutate } = useSWRConfig();
  return {
    createItem: async (body: InventoryItemPayload) => {
      const res = await api.createInventoryItem(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-items');
      return res;
    },
    updateItem: async (id: number | string, body: Partial<InventoryItemPayload>) => {
      const res = await api.updateInventoryItem(id, body);
      await mutate(['inventory-item-detail', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-items');
      return res;
    },
    deleteItem: async (id: number | string) => {
      await api.deleteInventoryItem(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-items');
    },
    createWarehouse: async (body: InventoryWarehousePayload) => {
      const res = await api.createInventoryWarehouse(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-warehouses');
      return res;
    },
    updateWarehouse: async (id: number | string, body: Partial<InventoryWarehousePayload>) => {
      const res = await api.updateInventoryWarehouse(id, body);
      await mutate(['inventory-warehouse-detail', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-warehouses');
      return res;
    },
    deleteWarehouse: async (id: number | string) => {
      await api.deleteInventoryWarehouse(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-warehouses');
    },
    createStockEntry: async (body: InventoryStockEntryPayload) => {
      const res = await api.createInventoryStockEntry(body);
      await mutate((key) => Array.isArray(key) && (key[0] === 'inventory-stock-entries' || key[0] === 'inventory-stock-ledger' || key[0] === 'inventory-items'));
      return res;
    },
    updateStockEntry: async (id: number | string, body: { posting_date?: string; remarks?: string; docstatus?: number }) => {
      const res = await api.updateInventoryStockEntry(id, body);
      await mutate(['inventory-stock-entry-detail', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-stock-entries');
      return res;
    },
    deleteStockEntry: async (id: number | string) => {
      await api.deleteInventoryStockEntry(id);
      await mutate((key) => Array.isArray(key) && (key[0] === 'inventory-stock-entries' || key[0] === 'inventory-stock-ledger'));
    },
    postToGL: async (id: number | string, params?: { inventory_account?: string; expense_account?: string }) => {
      const res = await api.postStockEntryToGL(id, params);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-stock-entries');
      return res;
    },
  };
}

// Inventory - Reorder Alerts
export function useInventoryReorderAlerts(
  params?: { limit?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-reorder-alerts', params], () => api.getInventoryReorderAlerts(params), config);
}

// Inventory - Transfer Requests
export function useInventoryTransfers(
  params?: { status?: string; from_warehouse?: string; to_warehouse?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-transfers', params], () => api.getInventoryTransfers(params), config);
}

export function useInventoryTransferMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (body: Parameters<typeof api.createInventoryTransfer>[0]) => {
      const res = await api.createInventoryTransfer(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-transfers');
      return res;
    },
    submit: async (id: number | string) => {
      const res = await api.submitInventoryTransfer(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-transfers');
      return res;
    },
    approve: async (id: number | string) => {
      const res = await api.approveInventoryTransfer(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-transfers');
      return res;
    },
    reject: async (id: number | string, reason: string) => {
      const res = await api.rejectInventoryTransfer(id, reason);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-transfers');
      return res;
    },
    execute: async (id: number | string) => {
      const res = await api.executeInventoryTransfer(id);
      await mutate((key) => Array.isArray(key) && (key[0] === 'inventory-transfers' || key[0] === 'inventory-stock-entries'));
      return res;
    },
  };
}

// Inventory - Batches
export function useInventoryBatches(
  params?: { item_code?: string; include_disabled?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-batches', params], () => api.getInventoryBatches(params), config);
}

export function useInventoryBatchMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (body: Parameters<typeof api.createInventoryBatch>[0]) => {
      const res = await api.createInventoryBatch(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-batches');
      return res;
    },
  };
}

// Inventory - Serial Numbers
export function useInventorySerials(
  params?: { item_code?: string; warehouse?: string; status?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['inventory-serials', params], () => api.getInventorySerials(params), config);
}

export function useInventorySerialMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (body: Parameters<typeof api.createInventorySerial>[0]) => {
      const res = await api.createInventorySerial(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'inventory-serials');
      return res;
    },
  };
}

// Asset Management Hooks
export function useAssets(
  params?: { status?: string; category?: string; location?: string; custodian?: string; department?: string; search?: string; min_value?: number; max_value?: number; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['assets', params], () => api.getAssets(params), config);
}

export function useAsset(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['asset', id] as const : null,
    ([, assetId]) => api.getAsset(assetId),
    config
  );
}

export function useAssetsSummary(config?: SWRConfiguration) {
  return useSWR('assets-summary', () => api.getAssetsSummary(), config);
}

export function useAssetCategories(
  params?: { limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['asset-categories', params], () => api.getAssetCategories(params), config);
}

export function useDepreciationSchedule(
  params?: { asset_id?: number; finance_book?: string; from_date?: string; to_date?: string; pending_only?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['depreciation-schedule', params], () => api.getDepreciationSchedule(params), config);
}

export function usePendingDepreciation(asOfDate?: string, config?: SWRConfiguration) {
  return useSWR(['pending-depreciation', asOfDate], () => api.getPendingDepreciation(asOfDate), config);
}

export function useMaintenanceDue(config?: SWRConfiguration) {
  return useSWR('maintenance-due', () => api.getMaintenanceDue(), config);
}

export function useWarrantyExpiring(days?: number, config?: SWRConfiguration) {
  return useSWR(['warranty-expiring', days], () => api.getWarrantyExpiring(days), config);
}

export function useInsuranceExpiring(days?: number, config?: SWRConfiguration) {
  return useSWR(['insurance-expiring', days], () => api.getInsuranceExpiring(days), config);
}

export function useAssetMutations() {
  const { mutate } = useSWRConfig();
  return {
    createAsset: async (body: Parameters<typeof api.createAsset>[0]) => {
      const res = await api.createAsset(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'assets');
      await mutate('assets-summary');
      return res;
    },
    updateAsset: async (id: number | string, body: Parameters<typeof api.updateAsset>[1]) => {
      const res = await api.updateAsset(id, body);
      await mutate(['asset', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'assets');
      return res;
    },
    submitAsset: async (id: number | string) => {
      const res = await api.submitAsset(id);
      await mutate(['asset', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'assets');
      await mutate('assets-summary');
      return res;
    },
    scrapAsset: async (id: number | string, scrapDate?: string) => {
      const res = await api.scrapAsset(id, scrapDate);
      await mutate(['asset', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'assets');
      await mutate('assets-summary');
      return res;
    },
    markForMaintenance: async (id: number | string) => {
      const res = await api.markForMaintenance(id);
      await mutate(['asset', id]);
      await mutate('maintenance-due');
      await mutate('assets-summary');
      return res;
    },
    completeMaintenance: async (id: number | string) => {
      const res = await api.completeMaintenance(id);
      await mutate(['asset', id]);
      await mutate('maintenance-due');
      await mutate('assets-summary');
      return res;
    },
  };
}

export function useAssetCategoryMutations() {
  const { mutate } = useSWRConfig();
  return {
    create: async (body: Parameters<typeof api.createAssetCategory>[0]) => {
      const res = await api.createAssetCategory(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'asset-categories');
      return res;
    },
  };
}

// ============= CRM HOOKS =============

// Leads
export function useLeads(
  params?: Parameters<typeof api.getLeads>[0],
  config?: SWRConfiguration
) {
  return useSWR(['leads', params], () => api.getLeads(params), config);
}

export function useLead(id: number | string | undefined, config?: SWRConfiguration) {
  return useSWR(id ? ['lead', id] : null, () => api.getLead(id!), config);
}

export function useLeadsSummary(config?: SWRConfiguration) {
  return useSWR('leads-summary', () => api.getLeadsSummary(), config);
}

export function useLeadMutations() {
  const { mutate } = useSWRConfig();
  return {
    createLead: async (body: Parameters<typeof api.createLead>[0]) => {
      const res = await api.createLead(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'leads');
      await mutate('leads-summary');
      return res;
    },
    updateLead: async (id: number | string, body: Parameters<typeof api.updateLead>[1]) => {
      const res = await api.updateLead(id, body);
      await mutate(['lead', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'leads');
      return res;
    },
    qualifyLead: async (id: number | string) => {
      const res = await api.qualifyLead(id);
      await mutate(['lead', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'leads');
      await mutate('leads-summary');
      return res;
    },
    disqualifyLead: async (id: number | string, reason?: string) => {
      const res = await api.disqualifyLead(id, reason);
      await mutate(['lead', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'leads');
      await mutate('leads-summary');
      return res;
    },
    convertLead: async (id: number | string, body: Parameters<typeof api.convertLead>[1]) => {
      const res = await api.convertLead(id, body);
      await mutate(['lead', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'leads');
      await mutate('leads-summary');
      await mutate((key) => Array.isArray(key) && key[0] === 'customers');
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      // Invalidate pipeline caches when conversion creates an opportunity
      await mutate('pipeline-summary');
      await mutate('pipeline-view');
      await mutate((key) => Array.isArray(key) && key[0] === 'kanban-view');
      return res;
    },
  };
}

// Opportunities
export function useOpportunities(
  params?: Parameters<typeof api.getOpportunities>[0],
  config?: SWRConfiguration
) {
  return useSWR(['opportunities', params], () => api.getOpportunities(params), config);
}

export function useOpportunity(id: number | string | undefined, config?: SWRConfiguration) {
  return useSWR(id ? ['opportunity', id] : null, () => api.getOpportunity(id!), config);
}

export function usePipelineSummary(config?: SWRConfiguration) {
  return useSWR('pipeline-summary', () => api.getPipelineSummary(), config);
}

export function useOpportunityMutations() {
  const { mutate } = useSWRConfig();
  return {
    createOpportunity: async (body: Parameters<typeof api.createOpportunity>[0]) => {
      const res = await api.createOpportunity(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      await mutate('pipeline-summary');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
    updateOpportunity: async (id: number | string, body: Parameters<typeof api.updateOpportunity>[1]) => {
      const res = await api.updateOpportunity(id, body);
      await mutate(['opportunity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
    moveStage: async (id: number | string, stageId: number) => {
      const res = await api.moveOpportunityStage(id, stageId);
      await mutate(['opportunity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      await mutate('pipeline-summary');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
    markWon: async (id: number | string, actualCloseDate?: string) => {
      const res = await api.markOpportunityWon(id, actualCloseDate);
      await mutate(['opportunity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      await mutate('pipeline-summary');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
    markLost: async (id: number | string, lostReason?: string, competitor?: string) => {
      const res = await api.markOpportunityLost(id, lostReason, competitor);
      await mutate(['opportunity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'opportunities');
      await mutate('pipeline-summary');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
  };
}

// Pipeline
export function usePipelineStages(includeInactive?: boolean, config?: SWRConfiguration) {
  return useSWR(['pipeline-stages', includeInactive], () => api.getPipelineStages(includeInactive), config);
}

export function usePipelineView(config?: SWRConfiguration) {
  return useSWR('pipeline-view', () => api.getPipelineView(), config);
}

export function useKanbanView(ownerId?: number, config?: SWRConfiguration) {
  return useSWR(['kanban-view', ownerId], () => api.getKanbanView(ownerId), config);
}

export function usePipelineStageMutations() {
  const { mutate } = useSWRConfig();
  return {
    createStage: async (body: Parameters<typeof api.createPipelineStage>[0]) => {
      const res = await api.createPipelineStage(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'pipeline-stages');
      await mutate('pipeline-view');
      return res;
    },
    updateStage: async (id: number | string, body: Parameters<typeof api.updatePipelineStage>[1]) => {
      const res = await api.updatePipelineStage(id, body);
      await mutate((key) => Array.isArray(key) && key[0] === 'pipeline-stages');
      await mutate('pipeline-view');
      return res;
    },
    reorderStages: async (stageIds: number[]) => {
      const res = await api.reorderPipelineStages(stageIds);
      await mutate((key) => Array.isArray(key) && key[0] === 'pipeline-stages');
      await mutate('pipeline-view');
      await mutate('kanban-view');
      return res;
    },
    deleteStage: async (id: number | string) => {
      const res = await api.deletePipelineStage(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'pipeline-stages');
      await mutate('pipeline-view');
      return res;
    },
  };
}

// Activities
export function useActivities(
  params?: Parameters<typeof api.getActivities>[0],
  config?: SWRConfiguration
) {
  return useSWR(['activities', params], () => api.getActivities(params), config);
}

export function useActivity(id: number | string | undefined, config?: SWRConfiguration) {
  return useSWR(id ? ['activity', id] : null, () => api.getActivity(id!), config);
}

export function useActivityTimeline(
  params?: Parameters<typeof api.getActivityTimeline>[0],
  config?: SWRConfiguration
) {
  return useSWR(['activity-timeline', params], () => api.getActivityTimeline(params), config);
}

export function useUpcomingActivities(limit?: number, config?: SWRConfiguration) {
  return useSWR(['upcoming-activities', limit], () => api.getUpcomingActivities(limit), config);
}

export function useOverdueActivities(config?: SWRConfiguration) {
  return useSWR('overdue-activities', () => api.getOverdueActivities(), config);
}

export function useActivityMutations() {
  const { mutate } = useSWRConfig();
  return {
    createActivity: async (body: Parameters<typeof api.createActivity>[0]) => {
      const res = await api.createActivity(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      await mutate((key) => Array.isArray(key) && key[0] === 'upcoming-activities');
      return res;
    },
    updateActivity: async (id: number | string, body: Parameters<typeof api.updateActivity>[1]) => {
      const res = await api.updateActivity(id, body);
      await mutate(['activity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      return res;
    },
    completeActivity: async (id: number | string, notes?: string) => {
      const res = await api.completeActivity(id, notes);
      await mutate(['activity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      await mutate((key) => Array.isArray(key) && key[0] === 'upcoming-activities');
      await mutate('overdue-activities');
      return res;
    },
    cancelActivity: async (id: number | string) => {
      const res = await api.cancelActivity(id);
      await mutate(['activity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      await mutate((key) => Array.isArray(key) && key[0] === 'upcoming-activities');
      return res;
    },
    rescheduleActivity: async (id: number | string, scheduledAt: string) => {
      const res = await api.rescheduleActivity(id, scheduledAt);
      await mutate(['activity', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      await mutate((key) => Array.isArray(key) && key[0] === 'upcoming-activities');
      await mutate('overdue-activities');
      return res;
    },
    deleteActivity: async (id: number | string) => {
      const res = await api.deleteActivity(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'activities');
      await mutate((key) => Array.isArray(key) && key[0] === 'activity-timeline');
      return res;
    },
  };
}

// Contacts
export function useContacts(
  params?: Parameters<typeof api.getContacts>[0],
  config?: SWRConfiguration
) {
  return useSWR(['contacts', params], () => api.getContacts(params), config);
}

export function useContact(id: number | string | undefined, config?: SWRConfiguration) {
  return useSWR(id ? ['contact', id] : null, () => api.getContact(id!), config);
}

export function useCustomerContacts(customerId: number | undefined, config?: SWRConfiguration) {
  return useSWR(
    customerId ? ['customer-contacts', customerId] : null,
    () => api.getCustomerContacts(customerId!),
    config
  );
}

export function useLeadContacts(leadId: number | undefined, config?: SWRConfiguration) {
  return useSWR(
    leadId ? ['lead-contacts', leadId] : null,
    () => api.getLeadContacts(leadId!),
    config
  );
}

export function useContactMutations() {
  const { mutate } = useSWRConfig();
  return {
    createContact: async (body: Parameters<typeof api.createContact>[0]) => {
      const res = await api.createContact(body);
      await mutate((key) => Array.isArray(key) && key[0] === 'contacts');
      if (body.customer_id) await mutate(['customer-contacts', body.customer_id]);
      if (body.lead_id) await mutate(['lead-contacts', body.lead_id]);
      return res;
    },
    updateContact: async (id: number | string, body: Parameters<typeof api.updateContact>[1]) => {
      const res = await api.updateContact(id, body);
      await mutate(['contact', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'customer-contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'lead-contacts');
      return res;
    },
    setPrimaryContact: async (id: number | string) => {
      const res = await api.setPrimaryContact(id);
      await mutate(['contact', id]);
      await mutate((key) => Array.isArray(key) && key[0] === 'contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'customer-contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'lead-contacts');
      return res;
    },
    deleteContact: async (id: number | string) => {
      const res = await api.deleteContact(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'customer-contacts');
      await mutate((key) => Array.isArray(key) && key[0] === 'lead-contacts');
      return res;
    },
  };
}

// Lead Sources & Campaigns
export function useLeadSources(config?: SWRConfiguration) {
  return useSWR('lead-sources', () => api.getLeadSources(), config);
}

export function useCampaigns(
  params?: Parameters<typeof api.getCampaigns>[0],
  config?: SWRConfiguration
) {
  return useSWR(['campaigns', params], () => api.getCampaigns(params), config);
}

// =============================================================================
// UNIFIED CONTACTS API HOOKS
// =============================================================================

export interface UnifiedContactsParams {
  page?: number;
  page_size?: number;
  search?: string;
  contact_type?: 'lead' | 'prospect' | 'customer' | 'churned' | 'person';
  category?: 'residential' | 'business' | 'enterprise' | 'government' | 'non_profit';
  status?: 'active' | 'inactive' | 'suspended' | 'do_not_contact';
  qualification?: 'unqualified' | 'cold' | 'warm' | 'hot' | 'qualified';
  owner_id?: number;
  territory?: string;
  city?: string;
  state?: string;
  source?: string;
  is_organization?: boolean;
  has_outstanding?: boolean;
  tag?: string;
  quality_issue?: 'missing_email' | 'missing_phone' | 'missing_address' | 'missing_name' | 'invalid_email';
  sort_by?: 'name' | 'created_at' | 'last_contact_date' | 'mrr' | 'lead_score';
  sort_order?: 'asc' | 'desc';
}

export interface UnifiedContact {
  id: number;
  name: string;
  contact_type: string;
  status: string;
  is_organization?: boolean | null;
  is_primary_contact?: boolean | null;
  is_billing_contact?: boolean | null;
  is_decision_maker?: boolean | null;
  designation?: string | null;
  department?: string | null;
  company_name?: string | null;
  lead_qualification?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
  website?: string | null;
  linkedin_url?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  mrr?: number | null;
  total_revenue?: number | null;
  outstanding_balance?: number | null;
  credit_limit?: number | null;
  account_number?: string | null;
  notes?: string | null;
  category?: string | null;
  territory?: string | null;
  source?: string | null;
  lead_score?: number | null;
  tags?: string[];
  cancellation_date?: string | null;
  churn_reason?: string | null;
  created_at?: string;
  first_contact_date?: string | null;
  qualified_date?: string | null;
  conversion_date?: string | null;
  last_contact_date?: string | null;
  total_conversations?: number;
  total_tickets?: number;
  total_orders?: number;
  total_invoices?: number;
  email_opt_in?: boolean;
  sms_opt_in?: boolean;
  whatsapp_opt_in?: boolean;
  phone_opt_in?: boolean;
}

export interface UnifiedContactsResponse {
  items: UnifiedContact[];
  total: number;
  total_pages?: number;
  page?: number;
  page_size?: number;
}

export interface UnifiedContactsDashboard {
  overview?: {
    total_contacts?: number;
    leads?: number;
    prospects?: number;
    customers?: number;
  };
  status_distribution?: {
    active?: number;
    inactive?: number;
    churned?: number;
  };
  financials?: {
    total_mrr?: number;
    avg_mrr?: number;
  };
  period_metrics?: {
    new_contacts?: number;
    new_contacts_change?: number;
    total_engagements?: number;
    total_engagements_change?: number;
  };
}

export interface UnifiedContactsFunnel {
  funnel?: {
    leads_created?: number;
    prospects_qualified?: number;
    customers_converted?: number;
  };
  conversion_rates?: {
    lead_to_prospect?: number;
    overall?: number;
  };
}

export function useUnifiedContacts(params?: UnifiedContactsParams, config?: SWRConfiguration) {
  return useSWR(
    ['unified-contacts', params],
    async () => {
      const queryParams = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            queryParams.append(key, String(value));
          }
        });
      }
      const queryString = queryParams.toString();
      const endpoint = queryString ? `/contacts?${queryString}` : '/contacts';
      return apiFetch<UnifiedContactsResponse>(endpoint);
    },
    config
  );
}

export function useUnifiedContact(id: number | string | undefined, config?: SWRConfiguration) {
  return useSWR(
    id ? ['unified-contact', id] : null,
    () => apiFetch<UnifiedContact>(`/contacts/${id}`),
    config
  );
}

export function useUnifiedContactLeads(params?: UnifiedContactsParams, config?: SWRConfiguration) {
  return useSWR(
    ['unified-contacts-leads', params],
    async () => {
      const queryParams = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            queryParams.append(key, String(value));
          }
        });
      }
      const queryString = queryParams.toString();
      const endpoint = queryString ? `/contacts/leads?${queryString}` : '/contacts/leads';
      return apiFetch<UnifiedContactsResponse>(endpoint);
    },
    config
  );
}

export function useUnifiedContactCustomers(params?: UnifiedContactsParams, config?: SWRConfiguration) {
  return useSWR(
    ['unified-contacts-customers', params],
    async () => {
      const queryParams = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            queryParams.append(key, String(value));
          }
        });
      }
      const queryString = queryParams.toString();
      const endpoint = queryString ? `/contacts/customers?${queryString}` : '/contacts/customers';
      return apiFetch<UnifiedContactsResponse>(endpoint);
    },
    config
  );
}

export function useUnifiedContactsDashboard(periodDays = 30, config?: SWRConfiguration) {
  return useSWR(
    ['unified-contacts-dashboard', periodDays],
    () => apiFetch<UnifiedContactsDashboard>(`/contacts/analytics/dashboard?period_days=${periodDays}`),
    config
  );
}

export function useUnifiedContactsFunnel(periodDays = 30, ownerId?: number, config?: SWRConfiguration) {
  return useSWR(
    ['unified-contacts-funnel', periodDays, ownerId],
    async () => {
      const params = new URLSearchParams({ period_days: String(periodDays) });
      if (ownerId) params.append('owner_id', String(ownerId));
      return apiFetch<UnifiedContactsFunnel>(`/contacts/analytics/funnel?${params.toString()}`);
    },
    config
  );
}

export function useUnifiedContactMutations() {
  const { mutate } = useSWRConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const run = async <T>(fn: () => Promise<T>): Promise<T> => {
    setIsLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (err: any) {
      const e = err instanceof Error ? err : new Error(err?.message || 'Request failed');
      setError(e);
      throw e;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    isLoading,
    error,
    createContact: async (body: Record<string, unknown>) => {
      return run(async () => {
        const result = await apiFetch('/contacts', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    updateContact: async (id: number | string, body: Record<string, unknown>) => {
      return run(async () => {
        const result = await apiFetch(`/contacts/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        await mutate(['unified-contact', id]);
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    deleteContact: async (id: number | string, hard = false) => {
      return run(async () => {
        const result = await apiFetch(`/contacts/${id}?hard=${hard}`, {
          method: 'DELETE',
        });
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    qualifyLead: async (id: number | string, qualification: string, leadScore?: number) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/qualify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ qualification, lead_score: leadScore }),
        });
        if (!response.ok) throw new Error('Failed to qualify lead');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    convertToCustomer: async (id: number | string, body?: Record<string, unknown>) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/convert-to-customer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body || {}),
        });
        if (!response.ok) throw new Error('Failed to convert to customer');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    markChurned: async (id: number | string, reason: string, notes?: string) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/mark-churned`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason, notes }),
        });
        if (!response.ok) throw new Error('Failed to mark churned');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    assignOwner: async (id: number | string, ownerId: number, notes?: string) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/assign`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_id: ownerId, notes }),
        });
        if (!response.ok) throw new Error('Failed to assign owner');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        await mutate((key) => Array.isArray(key) && typeof key[0] === 'string' && key[0].startsWith('unified-contacts'));
        return result;
      });
    },

    addTags: async (id: number | string, tags: string[]) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/tags/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tags),
        });
        if (!response.ok) throw new Error('Failed to add tags');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        return result;
      });
    },

    removeTags: async (id: number | string, tags: string[]) => {
      return run(async () => {
        const response = await fetch(`/api/contacts/${id}/tags/remove`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tags),
        });
        if (!response.ok) throw new Error('Failed to remove tags');
        const result = await response.json();
        await mutate(['unified-contact', id]);
        return result;
      });
    },
  };
}

// =============================================================================
// Platform Status Hooks
// =============================================================================

export interface PlatformLicense {
  configured: boolean;
  status: 'valid' | 'invalid' | 'expired' | 'unknown';
  message: string;
  in_grace_period: boolean;
  grace_period_hours: number;
}

export interface PlatformFeatureFlag {
  name: string;
  enabled: boolean;
  description: string;
  category: string;
}

export interface PlatformFeatureFlags {
  flags: PlatformFeatureFlag[];
  source: 'env' | 'platform';
  last_refresh: string | null;
  platform_precedence: boolean;
}

export interface PlatformStatus {
  platform_configured: boolean;
  platform_url: string | null;
  instance_id: string | null;
  tenant_id: string | null;
  license: PlatformLicense;
  feature_flags: PlatformFeatureFlags;
  otel_enabled: boolean;
  environment: string;
}

export interface PlatformConfig {
  environment: string;
  debug: boolean;
  otel_enabled: boolean;
  platform_url: string | null;
  version: string | null;
}

export interface EntitlementsResponse {
  license_status: string;
  in_grace_period: boolean;
  entitlements?: Record<string, any> | null;
  feature_flags: Record<string, boolean>;
}

async function fetchPlatformApi<T>(endpoint: string): Promise<T> {
  return fetchApi<T>(`/platform${endpoint}`);
}

async function fetchEntitlements<T>(): Promise<T> {
  return fetchApi<T>('/entitlements');
}

export function usePlatformStatus(config?: SWRConfiguration) {
  return useSWR<PlatformStatus>('platform-status', () => fetchPlatformApi('/status'), {
    refreshInterval: 60000, // Refresh every minute
    ...config,
  });
}

export function usePlatformLicense(config?: SWRConfiguration) {
  return useSWR<PlatformLicense>('platform-license', () => fetchPlatformApi('/license'), config);
}

export function usePlatformFeatureFlags(config?: SWRConfiguration) {
  return useSWR<PlatformFeatureFlags>('platform-feature-flags', () => fetchPlatformApi('/feature-flags'), config);
}

export function usePlatformConfig(config?: SWRConfiguration) {
  return useSWR<PlatformConfig>('platform-config', () => fetchPlatformApi('/config'), config);
}

export function useEntitlements(config?: SWRConfiguration) {
  return useSWR<EntitlementsResponse>('entitlements', () => fetchEntitlements(), config);
}

// Non-hook export for triggering sync
export async function triggerSync(source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) {
  return api.triggerSync(source, fullSync);
}

// =============================================================================
// CONSOLIDATED DASHBOARD HOOKS (Single Payload - Performance Optimized)
// =============================================================================

/**
 * Consolidated Sales Dashboard (13 API calls → 1)
 * Returns: Finance metrics, aging, revenue trend, recent transactions, CRM data
 */
export function useConsolidatedSalesDashboard(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['consolidated-sales-dashboard', currency],
    () => dashboardsApi.getSalesDashboard(currency),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Purchasing Dashboard (8 API calls → 1)
 * Returns: AP metrics, aging, top suppliers, recent bills/payments/orders
 */
export function useConsolidatedPurchasingDashboard(
  currency?: string,
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['consolidated-purchasing-dashboard', currency, params],
    () => dashboardsApi.getPurchasingDashboard(currency, params),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Support Dashboard (7 API calls → 1)
 * Returns: Ticket metrics, volume trend, SLA performance, queue health
 */
export function useConsolidatedSupportDashboard(
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    ['consolidated-support-dashboard', params],
    () => dashboardsApi.getSupportDashboard(params),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Field Service Dashboard (2 API calls → 1)
 * Returns: Today's metrics, order schedule, status breakdown
 */
export function useConsolidatedFieldServiceDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-field-service-dashboard',
    () => dashboardsApi.getFieldServiceDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Accounting Dashboard (11 API calls → 1)
 * Returns: Balance sheet, income statement, bank accounts, AR/AP, ratios
 */
export function useConsolidatedAccountingDashboard(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['consolidated-accounting-dashboard', currency],
    () => dashboardsApi.getAccountingDashboard(currency),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated HR Dashboard (11 API calls → 1)
 * Returns: Employee summary, leave, attendance, payroll, recruitment, training, onboarding
 */
export function useConsolidatedHRDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-hr-dashboard',
    () => dashboardsApi.getHRDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Inventory Dashboard (3 API calls → 1)
 * Returns: Stock summary, warehouse breakdown, recent entries
 */
export function useConsolidatedInventoryDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-inventory-dashboard',
    () => dashboardsApi.getInventoryDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Assets Dashboard (5 API calls → 1)
 * Returns: Asset totals, status, depreciation, maintenance, warranty, insurance
 */
export function useConsolidatedAssetsDashboard(daysAhead?: number, config?: SWRConfiguration) {
  return useSWR(
    ['consolidated-assets-dashboard', daysAhead],
    () => dashboardsApi.getAssetsDashboard(daysAhead),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Expenses Dashboard (2 API calls → 1)
 * Returns: Expense claims, cash advances, trends
 */
export function useConsolidatedExpensesDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-expenses-dashboard',
    () => dashboardsApi.getExpensesDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Projects Dashboard (2 API calls → 1)
 * Returns: Project counts, tasks, financials, recent projects
 */
export function useConsolidatedProjectsDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-projects-dashboard',
    () => dashboardsApi.getProjectsDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Inbox Dashboard (3 API calls → 1)
 * Returns: Conversation counts, channels, priorities, recent
 */
export function useConsolidatedInboxDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-inbox-dashboard',
    () => dashboardsApi.getInboxDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Contacts Dashboard
 * Returns: Contact counts, sources, activities
 */
export function useConsolidatedContactsDashboard(config?: SWRConfiguration) {
  return useSWR(
    'consolidated-contacts-dashboard',
    () => dashboardsApi.getContactsDashboard(),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

/**
 * Consolidated Customers Dashboard
 * Returns: Customer counts, billing, subscriptions
 */
export function useConsolidatedCustomersDashboard(currency?: string, config?: SWRConfiguration) {
  return useSWR(
    ['consolidated-customers-dashboard', currency],
    () => dashboardsApi.getCustomersDashboard(currency),
    {
      refreshInterval: 60000,
      ...config,
    }
  );
}

export { ApiError, apiFetch };
