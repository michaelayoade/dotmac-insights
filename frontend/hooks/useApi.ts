import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import {
  api,
  ApiError,
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
  PurchasingExpensePayload,
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
} from '@/lib/api';

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
    id ? ['support-ticket-detail', id] : null,
    () => (id ? api.getSupportTicketDetail(id) : null),
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
  return useSWR(id ? ['project-detail', id] : null, () => (id ? api.getProjectDetail(id) : null), config);
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
    id ? ['customer', id] : null,
    () => (id ? api.getCustomer(id) : null),
    config
  );
}

export function useCustomerUsage(
  id: number | null,
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR(
    id ? ['customer-usage', id, params] : null,
    () => (id ? api.getCustomerUsage(id, params) : null),
    config
  );
}

export function useCustomer360(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['customer-360', id] : null,
    () => (id ? api.getCustomer360(id) : null),
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
  return useSWR('customer-segments-insights', () => api.getCustomerSegmentsInsights(), config);
}

export function useCustomerHealthInsights(config?: SWRConfiguration) {
  return useSWR(
    'customer-health-insights',
    () => api.getCustomerHealthInsights(),
    config
  );
}

export function useCustomerCompletenessInsights(config?: SWRConfiguration) {
  return useSWR('customer-completeness-insights', () => api.getCustomerCompletenessInsights(), config);
}

export function useCustomerPlanChanges(months = 6, config?: SWRConfiguration) {
  return useSWR(
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
    table ? ['table-data', table, params] : null,
    () => (table ? api.getTableData(table, params) : null),
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
    entity ? ['data-explorer', entity, params] : null,
    () => entity ? api.exploreEntity(entity, params) : null,
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
    id ? ['finance-invoice-detail', id, currency] : null,
    () => (id ? api.getFinanceInvoiceDetail(id, currency) : null),
    config
  );
}

export function useFinancePaymentDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-payment-detail', id, currency] : null,
    () => (id ? api.getFinancePaymentDetail(id, currency) : null),
    config
  );
}

export function useFinanceCreditNoteDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-credit-note-detail', id, currency] : null,
    () => (id ? api.getFinanceCreditNoteDetail(id, currency) : null),
    config
  );
}

export function useFinanceOrderDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-order-detail', id, currency] : null,
    () => (id ? api.getFinanceOrderDetail(id, currency) : null),
    config
  );
}

export function useFinanceQuotationDetail(id: number | null, currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-quotation-detail', id, currency] : null,
    () => (id ? api.getFinanceQuotationDetail(id, currency) : null),
    config
  );
}

export function useFinanceCustomerDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['finance-customer-detail', id] : null,
    () => (id ? api.getFinanceCustomerDetail(id) : null),
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
    table ? ['table-data-enhanced', table, params] : null,
    () => (table ? api.getTableDataEnhanced(table, params) : null),
    config
  );
}

// Accounting Domain Hooks
export function useAccountingDashboard(currency = 'NGN', config?: SWRConfiguration) {
  return useSWR(['accounting-dashboard', currency], () => api.getAccountingDashboard(currency), {
    refreshInterval: 60000,
    dedupingInterval: 60000,
    revalidateOnFocus: false,
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
    id ? ['accounting-account-detail', id, params] : null,
    () => (id ? api.getAccountingAccountDetail(id, params) : null),
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
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
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
    { dedupingInterval: 5 * 60 * 1000, revalidateOnFocus: false, ...config }
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
  return useSWR(
    ['accounting-general-ledger', params],
    () => api.getAccountingGeneralLedger(params),
    config
  );
}

export function useAccountingCashFlow(startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['accounting-cash-flow', startDate, endDate],
    () => api.getAccountingCashFlow({ start_date: startDate, end_date: endDate }),
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
    id ? ['accounting-journal-entry-detail', id] : null,
    () => (id ? api.getAccountingJournalEntryDetail(id) : null),
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
    id ? ['accounting-purchase-invoice-detail', id, currency] : null,
    () => (id ? api.getAccountingPurchaseInvoiceDetail(id, currency) : null),
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
  return useSWR(['accounting-bank-transactions', params], () => api.getAccountingBankTransactions(params), config);
}

export function useAccountingBankTransactionDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['accounting-bank-transaction-detail', id] : null,
    () => (id ? api.getAccountingBankTransactionDetail(id) : null),
    config
  );
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
    id ? ['purchasing-bill-detail', id] : null,
    () => (id ? api.getPurchasingBillDetail(id) : null),
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
    id ? ['purchasing-order-detail', id] : null,
    () => (id ? api.getPurchasingOrderDetail(id) : null),
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
    id ? ['purchasing-debit-note-detail', id] : null,
    () => (id ? api.getPurchasingDebitNoteDetail(id) : null),
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
  return useSWR(
    id ? ['purchasing-supplier-detail', id] : null,
    () => (id ? api.getPurchasingSupplierDetail(id) : null),
    config
  );
}

export function usePurchasingPaymentDetail(id: number | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['purchasing-payment-detail', id] : null,
    () => (id ? api.getPurchasingPaymentDetail(id) : null),
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
    itemCode ? ['inventory-valuation-detail', itemCode, params] : null,
    () => (itemCode ? api.getInventoryValuationDetail(itemCode, params) : null),
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
    id ? ['purchasing-expense-detail', id] : null,
    () => (id ? api.getPurchasingExpenseDetail(id) : null),
    config
  );
}

export function usePurchasingExpenseMutations() {
  const { mutate } = useSWRConfig();
  return {
    createExpense: async (payload: PurchasingExpensePayload) => {
      const res = await api.createPurchasingExpense(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-expenses');
      return res;
    },
    updateExpense: async (id: number, payload: PurchasingExpensePayload) => {
      const res = await api.updatePurchasingExpense(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-expenses');
      await mutate(['purchasing-expense-detail', id]);
      return res;
    },
    deleteExpense: async (id: number, soft = true) => {
      await api.deletePurchasingExpense(id, soft);
      await mutate((key) => Array.isArray(key) && key[0] === 'purchasing-expenses');
    },
  };
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

// HR Domain
export function useHrLeaveTypes(
  params?: { search?: string; is_lwp?: boolean; is_carry_forward?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-types', params], () => api.getHrLeaveTypes(params), config);
}

export function useHrLeaveTypeDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-leave-type-detail', id] : null, () => (id ? api.getHrLeaveTypeDetail(id) : null), config);
}

export function useHrHolidayLists(
  params?: { search?: string; company?: string; from_date?: string; to_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-holiday-lists', params], () => api.getHrHolidayLists(params), config);
}

export function useHrHolidayListDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-holiday-list-detail', id] : null, () => (id ? api.getHrHolidayListDetail(id) : null), config);
}

export function useHrLeavePolicies(params?: { search?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-leave-policies', params], () => api.getHrLeavePolicies(params), config);
}

export function useHrLeavePolicyDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-leave-policy-detail', id] : null, () => (id ? api.getHrLeavePolicyDetail(id) : null), config);
}

export function useHrLeaveAllocations(
  params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-allocations', params], () => api.getHrLeaveAllocations(params), config);
}

export function useHrLeaveAllocationDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-leave-allocation-detail', id] : null, () => (id ? api.getHrLeaveAllocationDetail(id) : null), config);
}

export function useHrLeaveApplications(
  params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-leave-applications', params], () => api.getHrLeaveApplications(params), config);
}

export function useHrLeaveApplicationDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-leave-application-detail', id] : null, () => (id ? api.getHrLeaveApplicationDetail(id) : null), config);
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
  return useSWR(id ? ['hr-shift-type-detail', id] : null, () => (id ? api.getHrShiftTypeDetail(id) : null), config);
}

export function useHrShiftAssignments(
  params?: { employee_id?: number; shift_type_id?: number; start_date?: string; end_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-shift-assignments', params], () => api.getHrShiftAssignments(params), config);
}

export function useHrShiftAssignmentDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-shift-assignment-detail', id] : null, () => (id ? api.getHrShiftAssignmentDetail(id) : null), config);
}

export function useHrAttendances(
  params?: { employee_id?: number; status?: string; attendance_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-attendances', params], () => api.getHrAttendances(params), config);
}

export function useHrAttendanceDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-attendance-detail', id] : null, () => (id ? api.getHrAttendanceDetail(id) : null), config);
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
  return useSWR(id ? ['hr-attendance-request-detail', id] : null, () => (id ? api.getHrAttendanceRequestDetail(id) : null), config);
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
  return useSWR(id ? ['hr-job-opening-detail', id] : null, () => (id ? api.getHrJobOpeningDetail(id) : null), config);
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
  return useSWR(id ? ['hr-job-applicant-detail', id] : null, () => (id ? api.getHrJobApplicantDetail(id) : null), config);
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
  return useSWR(id ? ['hr-job-offer-detail', id] : null, () => (id ? api.getHrJobOfferDetail(id) : null), config);
}

export function useHrInterviews(
  params?: { job_applicant_id?: number; status?: string; interviewer?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-interviews', params], () => api.getHrInterviews(params), config);
}

export function useHrInterviewDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-interview-detail', id] : null, () => (id ? api.getHrInterviewDetail(id) : null), config);
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
  return useSWR(id ? ['hr-salary-component-detail', id] : null, () => (id ? api.getHrSalaryComponentDetail(id) : null), config);
}

export function useHrSalaryStructures(
  params?: { company?: string; is_active?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-structures', params], () => api.getHrSalaryStructures(params), config);
}

export function useHrSalaryStructureDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-salary-structure-detail', id] : null, () => (id ? api.getHrSalaryStructureDetail(id) : null), config);
}

export function useHrSalaryStructureAssignments(
  params?: { employee_id?: number; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-salary-structure-assignments', params], () => api.getHrSalaryStructureAssignments(params), config);
}

export function useHrSalaryStructureAssignmentDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(
    id ? ['hr-salary-structure-assignment-detail', id] : null,
    () => (id ? api.getHrSalaryStructureAssignmentDetail(id) : null),
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
  return useSWR(id ? ['hr-payroll-entry-detail', id] : null, () => (id ? api.getHrPayrollEntryDetail(id) : null), config);
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
  return useSWR(id ? ['hr-salary-slip-detail', id] : null, () => (id ? api.getHrSalarySlipDetail(id) : null), config);
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
    exportRegister: async (params?: { employee_id?: number; status?: string; start_date?: string; end_date?: string; company?: string; payroll_entry?: string }) => {
      return api.exportHrSalarySlipRegister(params);
    },
  };
}

export function useHrTrainingPrograms(params?: { search?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR(['hr-training-programs', params], () => api.getHrTrainingPrograms(params), config);
}

export function useHrTrainingProgramDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-training-program-detail', id] : null, () => (id ? api.getHrTrainingProgramDetail(id) : null), config);
}

export function useHrTrainingEvents(
  params?: { status?: string; company?: string; start_date?: string; end_date?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR(['hr-training-events', params], () => api.getHrTrainingEvents(params), config);
}

export function useHrTrainingEventDetail(id: number | string | null, config?: SWRConfiguration) {
  return useSWR(id ? ['hr-training-event-detail', id] : null, () => (id ? api.getHrTrainingEventDetail(id) : null), config);
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
  return useSWR(id ? ['hr-training-result-detail', id] : null, () => (id ? api.getHrTrainingResultDetail(id) : null), config);
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
    id ? ['hr-appraisal-template-detail', id] : null,
    () => (id ? api.getHrAppraisalTemplateDetail(id) : null),
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
  return useSWR(id ? ['hr-appraisal-detail', id] : null, () => (id ? api.getHrAppraisalDetail(id) : null), config);
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
    id ? ['hr-employee-onboarding-detail', id] : null,
    () => (id ? api.getHrEmployeeOnboardingDetail(id) : null),
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
    id ? ['hr-employee-separation-detail', id] : null,
    () => (id ? api.getHrEmployeeSeparationDetail(id) : null),
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
    id ? ['hr-employee-promotion-detail', id] : null,
    () => (id ? api.getHrEmployeePromotionDetail(id) : null),
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
    id ? ['hr-employee-transfer-detail', id] : null,
    () => (id ? api.getHrEmployeeTransferDetail(id) : null),
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

// Non-hook export for triggering sync
export async function triggerSync(source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) {
  return api.triggerSync(source, fullSync);
}

export { ApiError };
