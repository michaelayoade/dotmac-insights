/**
 * Support Domain API
 * Includes: Tickets, Agents, Teams, SLA, Automation, Routing, KB, Canned Responses, CSAT
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Support Metrics
export interface SupportMetrics {
  period_days: number;
  total_conversations: number;
  open: number;
  resolved: number;
  resolution_rate: number;
  avg_first_response_hours: number;
  avg_resolution_hours: number;
  by_channel: Record<string, number>;
}

// Ticket Types
export interface SupportTicketComment {
  id: number;
  comment: string | null;
  comment_type: string | null;
  commented_by: string | null;
  commented_by_name: string | null;
  is_public: boolean;
  comment_date: string | null;
  created_at: string | null;
}

export interface SupportTicketCommentPayload {
  comment?: string | null;
  comment_type?: string | null;
  commented_by?: string | null;
  commented_by_name?: string | null;
  is_public?: boolean;
  comment_date?: string | null;
}

export interface SupportTicketActivity {
  id: number;
  activity_type: string | null;
  activity: string | null;
  owner: string | null;
  from_status?: string | null;
  to_status?: string | null;
  activity_date: string | null;
  created_at: string | null;
}

export interface SupportTicketActivityPayload {
  activity_type?: string | null;
  activity?: string | null;
  owner?: string | null;
  from_status?: string | null;
  to_status?: string | null;
  activity_date?: string | null;
}

export interface SupportTicketCommunication {
  id: number;
  erpnext_id: string | null;
  communication_type: string | null;
  communication_medium: string | null;
  subject: string | null;
  content: string | null;
  sender: string | null;
  sender_full_name: string | null;
  recipients: string | null;
  sent_or_received: string | null;
  communication_date: string | null;
}

// Settings
export type WorkingHoursType =
  | 'FIXED'
  | 'FLEXIBLE'
  | '24_7'
  | 'STANDARD'
  | 'EXTENDED'
  | 'ROUND_THE_CLOCK'
  | 'CUSTOM';
export type DefaultRoutingStrategy =
  | 'ROUND_ROBIN'
  | 'LOAD_BALANCE'
  | 'SKILL_BASED'
  | 'MANUAL'
  | 'LEAST_BUSY'
  | 'LOAD_BALANCED';
export type TicketAutoCloseAction = 'CLOSE' | 'RESOLVE' | 'ARCHIVE' | 'NOTIFY_ONLY';
export type CSATSurveyTrigger = 'ON_RESOLVE' | 'ON_CLOSE' | 'ON_FIRST_RESPONSE' | 'MANUAL' | 'DISABLED';
export type TicketPriorityDefault = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type NotificationChannel = 'EMAIL' | 'SMS' | 'PUSH' | 'SLACK' | 'IN_APP' | 'WEBHOOK';
export type WeeklyScheduleDay = 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
export type SupportWeekDay = WeeklyScheduleDay;

export interface SupportSettingsResponse {
  company?: string | null;
  working_hours_type?: WorkingHoursType;
  timezone?: string | null;
  business_hours?: Array<{
    day: WeeklyScheduleDay;
    start_time: string;
    end_time: string;
    is_closed?: boolean;
  }>;
  weekly_schedule?: Record<WeeklyScheduleDay, { start: string; end: string; closed?: boolean }>;
  working_hours_standard?: { start?: string; end?: string; days?: WeeklyScheduleDay[] };
  default_routing_strategy?: DefaultRoutingStrategy;
  allow_agent_auto_assign?: boolean;
  max_tickets_per_agent?: number;
  rebalance_threshold_percent?: number;
  default_priority?: TicketPriorityDefault;
  default_ticket_type?: string | null;
  allow_customer_priority_selection?: boolean;
  allow_customer_team_selection?: boolean;
  auto_assign_enabled?: boolean;
  auto_close_enabled?: boolean;
  auto_close_action?: TicketAutoCloseAction;
  auto_close_hours?: number;
  auto_close_resolved_days?: number;
  auto_close_resolution?: string | null;
  auto_close_notify_customer?: boolean;
  allow_customer_reopen?: boolean;
  reopen_window_days?: number;
  max_reopens_allowed?: number;
  escalation_enabled?: boolean;
  escalation_notify_manager?: boolean;
  idle_escalation_enabled?: boolean;
  idle_hours_before_escalation?: number;
  reopen_escalation_enabled?: boolean;
  reopen_count_for_escalation?: number;
  archive_closed_tickets_days?: number;
  delete_archived_tickets_days?: number;
  csat_enabled?: boolean;
  csat_survey_trigger?: CSATSurveyTrigger;
  csat_trigger?: CSATSurveyTrigger;
  csat_delay_hours?: number;
  csat_reminder_enabled?: boolean;
  csat_reminder_days?: number;
  csat_survey_expiry_days?: number;
  ticket_priority_default?: TicketPriorityDefault;
  notification_channels?: NotificationChannel[];
  notify_assigned_agent?: boolean;
  notify_team_on_unassigned?: boolean;
  notify_customer_on_status_change?: boolean;
  notify_customer_on_reply?: boolean;
  unassigned_warning_minutes?: number;
  queue_refresh_seconds?: number;
  overdue_highlight_enabled?: boolean;
  portal_enabled?: boolean;
  portal_ticket_creation_enabled?: boolean;
  portal_show_ticket_history?: boolean;
  portal_show_knowledge_base?: boolean;
  portal_show_faq?: boolean;
  portal_require_login?: boolean;
  kb_enabled?: boolean;
  kb_public_access?: boolean;
  kb_suggest_articles_on_create?: boolean;
  kb_track_article_helpfulness?: boolean;
  ticket_id_prefix?: string;
  ticket_id_min_digits?: number;
  date_format?: string;
  time_format?: string;
  notification_channel_settings?: NotificationChannel[];
  email_to_ticket_enabled?: boolean;
  email_reply_to_address?: string | null;
  sync_to_erpnext?: boolean;
  sync_to_splynx?: boolean;
  sync_to_chatwoot?: boolean;
  sla_include_holidays?: boolean;
  sla_include_weekends?: boolean;
  default_first_response_hours?: number;
  default_resolution_hours?: number;
  sla_warning_threshold_percent?: number;
}

export type SupportSettingsUpdate = Partial<SupportSettingsResponse>;

export interface SupportTicketCommunicationPayload {
  communication_type?: string | null;
  communication_medium?: string | null;
  subject?: string | null;
  content?: string | null;
  sender?: string | null;
  sender_full_name?: string | null;
  recipients?: string | null;
  sent_or_received?: string | null;
  communication_date?: string | null;
}

export interface SupportTicketDependency {
  id: number;
  depends_on_ticket_id: number | null;
  depends_on_erpnext_id: string | null;
  depends_on_subject: string | null;
  depends_on_status: string | null;
}

export interface SupportTicketDependencyPayload {
  depends_on_ticket_id?: number | null;
  depends_on_erpnext_id?: string | null;
  depends_on_subject?: string | null;
  depends_on_status?: string | null;
}

export interface SupportTicketExpense {
  id: number;
  erpnext_id: string | null;
  expense_type: string | null;
  description: string | null;
  total_claimed_amount: number;
  total_sanctioned_amount: number | null;
  status: string | null;
  expense_date: string | null;
}

export interface SupportTicketDetail {
  id: number;
  ticket_number: string | null;
  subject: string | null;
  status: string | null;
  priority?: string | null;
  [key: string]: unknown;
  comments?: SupportTicketComment[];
  activities?: SupportTicketActivity[];
  communications?: SupportTicketCommunication[];
  depends_on?: SupportTicketDependency[];
  expenses?: SupportTicketExpense[];
}

export interface SupportTicketPayload {
  subject: string;
  description?: string | null;
  status?: 'open' | 'replied' | 'resolved' | 'closed' | 'on_hold';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  ticket_type?: string | null;
  issue_type?: string | null;
  customer_id?: number | null;
  project_id?: number | null;
  assigned_to?: string | null;
  assigned_employee_id?: number | null;
  resolution_by?: string | null;
  response_by?: string | null;
  resolution_team?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  customer_name?: string | null;
  region?: string | null;
  base_station?: string | null;
}

export interface SupportTicketAssigneePayload {
  agent_id?: number | null;
  team_id?: number | null;
  member_id?: number | null;
  employee_id?: number | null;
  assigned_to?: string | null;
}

export interface SupportTicketSlaPayload {
  response_by?: string | null;
  resolution_by?: string | null;
  reason?: string | null;
}

export interface SupportTicketListItem {
  id: number;
  ticket_number: string | null;
  subject: string | null;
  status: string | null;
  priority: string | null;
  ticket_type?: string | null;
  assigned_to?: string | null;
  assigned_employee_id?: number | null;
  resolution_by?: string | null;
  response_by?: string | null;
  created_at?: string | null;
  modified_at?: string | null;
}

export interface SupportTicketListResponse {
  tickets: SupportTicketListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupportTicketListParams {
  start?: string;
  end?: string;
  team_id?: number;
  agent?: string;
  ticket_type?: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  status?: string;
  limit?: number;
  offset?: number;
}

export interface SupportTicketCreateResponse {
  id: number;
  ticket_number: string;
}

// Overview Types
export interface SupportOverviewRequest {
  start?: string;
  end?: string;
  team_id?: number;
  agent?: string;
  ticket_type?: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  limit_overdue?: number;
  offset_overdue?: number;
}

export interface SupportOverviewResponse {
  summary: {
    total: number;
    open: number;
    replied: number;
    resolved: number;
    closed: number;
    on_hold: number;
    sla_attainment_pct: number;
    avg_response_hours: number;
    avg_resolution_hours: number;
    overdue: number;
    unassigned: number;
  };
  by_priority: Array<{
    priority: string;
    open: number;
    total: number;
    sla_breach_pct: number;
  }>;
  by_type: Array<{
    ticket_type: string;
    open: number;
    total: number;
    avg_resolution_hours: number;
  }>;
  volume_trend: Array<{
    period: string;
    opened: number;
    resolved: number;
    closed: number;
    sla_attainment_pct: number;
  }>;
  resolution_trend: Array<{
    period: string;
    p50_hours: number;
    p75_hours: number;
    p90_hours: number;
  }>;
  backlog_age: Array<{ bucket: string; count: number }>;
  agent_performance: Array<{
    agent: string;
    open: number;
    resolved: number;
    avg_resolution_hours: number;
    sla_attainment_pct: number;
    csat_avg?: number;
  }>;
  team_performance: Array<{
    team: string;
    open: number;
    resolved: number;
    sla_attainment_pct: number;
    avg_resolution_hours: number;
  }>;
  csat: {
    avg_score: number;
    response_rate_pct: number;
    trend: Array<{ period: string; avg_score: number; responses: number }>;
  };
  top_drivers: Array<{ label: string; count: number; share_pct: number }>;
  overdue_detail: Array<{
    id: number;
    ticket_number: string | null;
    priority: string | null;
    assigned_to: string | null;
    resolution_by: string | null;
    age_hours: number;
  }>;
}

export interface SupportDashboardResponse {
  tickets: {
    total: number;
    open: number;
    resolved: number;
    closed: number;
    on_hold: number;
  };
  by_priority: Record<string, number>;
  sla: { met: number; breached: number; attainment_rate: number };
  metrics: {
    avg_resolution_hours: number;
    overdue_tickets: number;
    unassigned_tickets: number;
  };
  conversations: { total: number; open: number; resolved: number };
}

// Agent Types
export interface SupportAgent {
  id: number;
  email: string | null;
  display_name?: string | null;
  employee_id?: number | null;
  team_id?: number | null;
  status?: string | null;
  domains?: Record<string, boolean>;
  skills?: Record<string, number>;
  channel_caps?: Record<string, boolean>;
  routing_weight?: number | null;
  capacity?: number | null;
  is_active?: boolean;
}

export interface SupportAgentPayload {
  employee_id?: number | null;
  email?: string | null;
  display_name?: string | null;
  domains?: Record<string, boolean>;
  skills?: Record<string, number>;
  channel_caps?: Record<string, boolean>;
  routing_weight?: number | null;
  capacity?: number | null;
  is_active?: boolean;
}

// Team Types
export interface SupportTeam {
  id: number;
  team_name: string;
  description?: string | null;
  assignment_rule?: string | null;
  ignore_restrictions?: boolean;
  domain?: string | null;
  is_active?: boolean;
  members?: SupportTeamMember[];
}

export interface SupportTeamMember {
  id: number;
  agent_id: number | null;
  role?: string | null;
  user?: string | null;
  user_name?: string | null;
  employee_id?: number | null;
  team_id?: number;
}

export interface SupportTeamPayload {
  team_name?: string;
  description?: string | null;
  assignment_rule?: string | null;
  domain?: string | null;
  is_active?: boolean;
  ignore_restrictions?: boolean;
}

export interface SupportTeamMemberPayload {
  agent_id: number;
  role?: string | null;
}

// Analytics Types
export interface SupportVolumeTrend {
  year: number;
  month: number;
  period: string;
  total: number;
  resolved: number;
  closed: number;
  resolution_rate: number;
}

export interface SupportResolutionTimeTrend {
  year: number;
  month: number;
  period: string;
  avg_resolution_hours: number;
  ticket_count: number;
}

export interface SupportCategoryBreakdown {
  by_ticket_type: {
    type: string;
    count: number;
    resolved: number;
    resolution_rate: number;
  }[];
  by_issue_type: { type: string; count: number }[];
}

export interface SupportSlaPerformanceTrend {
  year: number;
  month: number;
  period: string;
  met: number;
  breached: number;
  total: number;
  attainment_rate: number;
}

export interface SupportPatterns {
  peak_hours: { hour: number; count: number }[];
  peak_days: { day: string; day_num: number; count: number }[];
  by_region: { region: string; count: number }[];
}

export interface SupportAgentPerformanceInsights {
  by_assignee: {
    assignee: string;
    total_tickets: number;
    resolved: number;
    resolution_rate: number;
    avg_resolution_hours: number;
  }[];
}

// CSAT Types
export interface SupportCsatSurvey {
  id: number;
  name: string;
  survey_type?: string;
  trigger?: string;
  is_active: boolean;
}

export interface SupportCsatSummary {
  average_rating: number;
  total_responses: number;
  response_rate: number;
}

export interface SupportCsatAgentPerformance {
  agent_id: number;
  agent_name: string;
  response_count: number;
  avg_rating: number;
  satisfaction_pct: number;
}

export interface SupportCsatTrend {
  period: string;
  avg_rating: number;
  response_count: number;
}

// Automation Types
export interface SupportAutomationRule {
  id: number;
  name: string;
  description?: string | null;
  trigger: string;
  is_active: boolean;
  conditions?: unknown[];
  actions?: unknown[];
}

export interface SupportAutomationLog {
  id: number;
  rule_id?: number | null;
  ticket_id?: number | null;
  trigger?: string | null;
  success?: boolean;
  run_at?: string | null;
  message?: string | null;
  rule_name?: string | null;
  executed_at?: string | null;
  ticket_number?: string | null;
  error_message?: string | null;
}

export interface SupportAutomationLogList {
  data: SupportAutomationLog[];
  total?: number;
}

export interface SupportAutomationLogSummary {
  total_executions?: number;
  successful_executions?: number;
  success_rate?: number;
}

export interface SupportAutomationReference {
  triggers: { value: string; label: string }[];
  action_types: { value: string; label: string }[];
  operators: { value: string; label: string }[];
}

// SLA Types
export interface SupportCalendar {
  id: number;
  name: string;
  description?: string | null;
  calendar_type?: string | null;
  is_active?: boolean;
  timezone?: string | null;
  holidays?: Array<{ name?: string; date?: string }>;
}

export interface SupportSlaPolicy {
  id: number;
  name: string;
  description?: string | null;
  is_active?: boolean;
  conditions?: unknown[];
  targets?: unknown[];
  priority?: string | null;
}

export interface SupportSlaBreachSummary {
  total?: number;
  breached?: number;
  on_time?: number;
  currently_overdue?: number;
  total_breaches?: number;
  by_target_type?: Record<string, number>;
}

// Routing Types
export interface SupportRoutingRule {
  id: number;
  name: string;
  description?: string | null;
  is_active?: boolean;
  strategy?: string | null;
  team_id?: number | null;
  priority?: number | null;
}

export interface SupportQueueHealth {
  queue: string;
  pending: number;
  sla_breaches?: number;
  currently_overdue?: number;
  unassigned_tickets?: number;
  avg_wait_hours?: number;
  total_agents?: number;
  total_capacity?: number;
  total_load?: number;
  overall_utilization_pct?: number;
}

export interface SupportAgentWorkload {
  agent_id: number;
  agent_name?: string | null;
  email?: string | null;
  open_tickets: number;
  pending?: number;
  overdue?: number;
  current_load?: number;
  capacity?: number;
  routing_weight?: number;
  utilization_pct?: number;
  is_available?: boolean;
  team_name?: string | null;
}

// Knowledge Base Types
export interface SupportKbCategory {
  id: number;
  name: string;
  parent_id?: number | null;
  status?: string | null;
  description?: string | null;
}

export interface SupportKbArticle {
  id: number;
  title: string;
  status?: string | null;
  category_id?: number | null;
  description?: string | null;
}

export interface SupportKbArticleList {
  items: SupportKbArticle[];
  data?: SupportKbArticle[];
  total?: number;
}

// Canned Responses
export interface SupportCannedResponse {
  id: number;
  title: string;
  category?: string | null;
  content?: string | null;
}

export interface SupportCannedResponseList {
  items: SupportCannedResponse[];
  data?: SupportCannedResponse[];
  total?: number;
}

// =============================================================================
// API
// =============================================================================

export const supportApi = {
  // =========================================================================
  // DASHBOARD & OVERVIEW
  // =========================================================================

  getDashboard: () => fetchApi<SupportDashboardResponse>('/support/dashboard'),

  getOverview: (params?: SupportOverviewRequest) =>
    fetchApi<SupportOverviewResponse>('/support/analytics/overview', {
      params: params as Record<string, unknown>,
    }),

  getMetrics: (days = 30) =>
    fetchApi<SupportMetrics>('/analytics/support/metrics', { params: { days } }),

  // =========================================================================
  // TICKETS
  // =========================================================================

  getTickets: (params?: SupportTicketListParams) =>
    fetchApi<SupportTicketListResponse>('/support/tickets', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getTicketDetail: (id: number | string) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}`),

  createTicket: (body: SupportTicketPayload) =>
    fetchApi<SupportTicketCreateResponse>('/support/tickets', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateTicket: (id: number | string, body: Partial<SupportTicketPayload>) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteTicket: (id: number | string) =>
    fetchApi<void>(`/support/tickets/${id}`, { method: 'DELETE' }),

  assignTicket: (id: number | string, body: SupportTicketAssigneePayload) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}/assignee`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  overrideTicketSla: (id: number | string, body: SupportTicketSlaPayload) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}/sla`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // =========================================================================
  // TICKET COMMENTS
  // =========================================================================

  createTicketComment: (
    ticketId: number | string,
    body: SupportTicketCommentPayload
  ) =>
    fetchApi<SupportTicketComment>(`/support/tickets/${ticketId}/comments`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateTicketComment: (
    ticketId: number | string,
    commentId: number,
    body: SupportTicketCommentPayload
  ) =>
    fetchApi<SupportTicketComment>(
      `/support/tickets/${ticketId}/comments/${commentId}`,
      { method: 'PATCH', body: JSON.stringify(body) }
    ),

  deleteTicketComment: (ticketId: number | string, commentId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/comments/${commentId}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // TICKET ACTIVITIES
  // =========================================================================

  createTicketActivity: (
    ticketId: number | string,
    body: SupportTicketActivityPayload
  ) =>
    fetchApi<SupportTicketActivity>(`/support/tickets/${ticketId}/activities`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateTicketActivity: (
    ticketId: number | string,
    activityId: number,
    body: SupportTicketActivityPayload
  ) =>
    fetchApi<SupportTicketActivity>(
      `/support/tickets/${ticketId}/activities/${activityId}`,
      { method: 'PATCH', body: JSON.stringify(body) }
    ),

  deleteTicketActivity: (ticketId: number | string, activityId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/activities/${activityId}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // TICKET COMMUNICATIONS
  // =========================================================================

  createTicketCommunication: (
    ticketId: number | string,
    body: SupportTicketCommunicationPayload
  ) =>
    fetchApi<SupportTicketCommunication>(
      `/support/tickets/${ticketId}/communications`,
      { method: 'POST', body: JSON.stringify(body) }
    ),

  updateTicketCommunication: (
    ticketId: number | string,
    communicationId: number,
    body: SupportTicketCommunicationPayload
  ) =>
    fetchApi<SupportTicketCommunication>(
      `/support/tickets/${ticketId}/communications/${communicationId}`,
      { method: 'PATCH', body: JSON.stringify(body) }
    ),

  deleteTicketCommunication: (
    ticketId: number | string,
    communicationId: number
  ) =>
    fetchApi<void>(
      `/support/tickets/${ticketId}/communications/${communicationId}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // TICKET DEPENDENCIES
  // =========================================================================

  createTicketDependency: (
    ticketId: number | string,
    body: SupportTicketDependencyPayload
  ) =>
    fetchApi<SupportTicketDependency>(
      `/support/tickets/${ticketId}/depends-on`,
      { method: 'POST', body: JSON.stringify(body) }
    ),

  updateTicketDependency: (
    ticketId: number | string,
    dependencyId: number,
    body: SupportTicketDependencyPayload
  ) =>
    fetchApi<SupportTicketDependency>(
      `/support/tickets/${ticketId}/depends-on/${dependencyId}`,
      { method: 'PATCH', body: JSON.stringify(body) }
    ),

  deleteTicketDependency: (ticketId: number | string, dependencyId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/depends-on/${dependencyId}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // AGENTS
  // =========================================================================

  getAgents: (team_id?: number, domain?: string) =>
    fetchApi<{ agents: SupportAgent[] }>('/support/agents', {
      params: { team_id, domain },
    }),

  createAgent: (body: SupportAgentPayload) =>
    fetchApi<SupportAgent>('/support/agents', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateAgent: (id: number, body: SupportAgentPayload) =>
    fetchApi<SupportAgent>(`/support/agents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteAgent: (id: number) =>
    fetchApi<void>(`/support/agents/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // TEAMS
  // =========================================================================

  getTeams: (domain?: string) =>
    fetchApi<{ teams: SupportTeam[] }>('/support/teams', {
      params: domain ? { domain } : undefined,
    }),

  createTeam: (body: SupportTeamPayload & { team_name: string }) =>
    fetchApi<SupportTeam>('/support/teams', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateTeam: (id: number, body: SupportTeamPayload) =>
    fetchApi<SupportTeam>(`/support/teams/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteTeam: (id: number) =>
    fetchApi<void>(`/support/teams/${id}`, { method: 'DELETE' }),

  addTeamMember: (teamId: number, body: SupportTeamMemberPayload) =>
    fetchApi<SupportTeamMember>(`/support/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteTeamMember: (teamId: number, memberId: number) =>
    fetchApi<void>(`/support/teams/${teamId}/members/${memberId}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // ANALYTICS
  // =========================================================================

  getAnalyticsVolumeTrend: (params?: { months?: number }) =>
    fetchApi<SupportVolumeTrend[]>('/support/analytics/volume-trend', {
      params,
    }),

  getAnalyticsResolutionTime: (params?: { months?: number }) =>
    fetchApi<SupportResolutionTimeTrend[]>('/support/analytics/resolution-time', {
      params,
    }),

  getAnalyticsByCategory: (params?: { days?: number }) =>
    fetchApi<SupportCategoryBreakdown>('/support/analytics/by-category', {
      params,
    }),

  getAnalyticsSlaPerformance: (params?: { months?: number }) =>
    fetchApi<SupportSlaPerformanceTrend[]>('/support/analytics/sla-performance', {
      params,
    }),

  // =========================================================================
  // INSIGHTS
  // =========================================================================

  getInsightsPatterns: (params?: { days?: number }) =>
    fetchApi<SupportPatterns>('/support/insights/patterns', { params }),

  getInsightsAgentPerformance: (params?: { days?: number }) =>
    fetchApi<SupportAgentPerformanceInsights>(
      '/support/insights/agent-performance',
      { params }
    ),

  // =========================================================================
  // CSAT
  // =========================================================================

  getCsatSurveys: (params?: { active_only?: boolean }) =>
    fetchApi<SupportCsatSurvey[]>('/support/csat/surveys', { params }),

  getCsatSummary: (params?: { days?: number }) =>
    fetchApi<SupportCsatSummary>('/support/csat/analytics/summary', { params }),

  getCsatAgentPerformance: (params?: { days?: number }) =>
    fetchApi<SupportCsatAgentPerformance[]>('/support/csat/analytics/by-agent', {
      params,
    }),

  getCsatTrends: (params?: { months?: number }) =>
    fetchApi<SupportCsatTrend[]>('/support/csat/analytics/trends', { params }),

  // =========================================================================
  // AUTOMATION
  // =========================================================================

  getAutomationRules: (params?: { trigger?: string; active_only?: boolean }) =>
    fetchApi<SupportAutomationRule[]>('/support/automation/rules', { params }),

  getAutomationReference: () =>
    fetchApi<SupportAutomationReference>('/support/automation/reference'),

  getAutomationLogs: (params?: {
    rule_id?: number;
    ticket_id?: number;
    trigger?: string;
    success?: boolean;
    days?: number;
    limit?: number;
    offset?: number;
  }) => fetchApi<SupportAutomationLogList>('/support/automation/logs', { params }),

  getAutomationLogsSummary: (params?: { days?: number }) =>
    fetchApi<SupportAutomationLogSummary>('/support/automation/logs/summary', {
      params,
    }),

  // =========================================================================
  // SLA
  // =========================================================================

  getSlaCalendars: (params?: { active_only?: boolean }) =>
    fetchApi<SupportCalendar[]>('/support/sla/calendars', { params }),

  getSlaPolicies: (params?: { active_only?: boolean }) =>
    fetchApi<SupportSlaPolicy[]>('/support/sla/policies', { params }),

  getSlaBreachesSummary: (params?: { days?: number }) =>
    fetchApi<SupportSlaBreachSummary>('/support/sla/breaches/summary', {
      params,
    }),

  // =========================================================================
  // ROUTING
  // =========================================================================

  getRoutingRules: (params?: { team_id?: number; active_only?: boolean }) =>
    fetchApi<SupportRoutingRule[]>('/support/routing/rules', { params }),

  getRoutingQueueHealth: () =>
    fetchApi<SupportQueueHealth>('/support/routing/queue-health'),

  getRoutingWorkload: (team_id?: number) =>
    fetchApi<SupportAgentWorkload[]>('/support/routing/agent-workload', {
      params: team_id ? { team_id } : undefined,
    }),

  // =========================================================================
  // KNOWLEDGE BASE
  // =========================================================================

  getKbCategories: (params?: {
    parent_id?: number;
    include_inactive?: boolean;
  }) => fetchApi<SupportKbCategory[]>('/support/kb/categories', { params }),

  getKbArticles: (params?: {
    category_id?: number;
    status?: string;
    visibility?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<SupportKbArticleList>('/support/kb/articles', { params }),

  // =========================================================================
  // CANNED RESPONSES
  // =========================================================================

  getCannedResponses: (params?: {
    scope?: string;
    category?: string;
    team_id?: number;
    search?: string;
    include_inactive?: boolean;
    limit?: number;
    offset?: number;
  }) => fetchApi<SupportCannedResponseList>('/support/canned-responses', { params }),

  getCannedCategories: () =>
    fetchApi<string[]>('/support/canned-responses/categories'),

  // =========================================================================
  // SETTINGS
  // =========================================================================

  getSettings: (params?: { company?: string }) =>
    fetchApi<SupportSettingsResponse>('/support/settings', { params }),

  updateSettings: (body: SupportSettingsUpdate, company?: string) =>
    fetchApi<SupportSettingsResponse>('/support/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
      params: company ? { company } : undefined,
    }),

  seedDefaults: () =>
    fetchApi<{ message: string; id: number }>('/support/settings/seed-defaults', {
      method: 'POST',
    }),
};

export default supportApi;
