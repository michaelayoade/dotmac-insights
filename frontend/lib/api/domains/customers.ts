/**
 * Customers Domain API
 * Includes: Customers, Customer 360, Analytics, Insights, Segments, Health
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Customer Dashboard
export interface CustomerDashboard {
  overview: {
    total_customers: number;
    total_mrr?: number;
    by_status: {
      active: number;
      blocked: number;
      inactive: number;
      churned?: number;
      new: number;
    };
    by_type?: Array<{ type: string; count: number; mrr?: number }>;
    growth_30d?: {
      new_signups: number;
      churned: number;
      net_change: number;
    };
  };
  finance?: {
    revenue?: { total_mrr?: number; active_mrr?: number };
    invoices?: {
      total_invoiced?: number;
      outstanding?: number;
      overdue_count?: number;
      overdue_amount?: number;
    };
    billing_health?: {
      blocking_today?: number;
      blocking_in_3_days?: number;
      blocking_in_7_days?: number;
      mrr_at_risk?: number;
      negative_deposit?: number;
    };
  };
  services?: {
    subscriptions?: { total?: number; active?: number; active_mrr?: number };
    usage_30d?: {
      total_upload_gb?: number;
      total_download_gb?: number;
      customers_with_data?: number;
    };
  };
  support?: {
    tickets?: {
      total?: number;
      open?: number;
      closed?: number;
      created_last_30d?: number;
    };
    customers_with_open_tickets?: number;
  };
  projects?: { total?: number; active?: number; completed?: number };
  crm?: {
    conversations?: { total?: number; open?: number; created_last_30d?: number };
  };
  generated_at?: string;
  // Legacy fields (fallback)
  total_customers?: number;
  by_status?: {
    active: number;
    blocked?: number;
    suspended?: number;
    cancelled?: number;
    inactive?: number;
    pending?: number;
    new?: number;
  };
  activity_30d?: { new_signups: number; churned: number; net_change: number };
  health?: { with_overdue_invoices: number; with_open_tickets: number };
  billing_health?: {
    blocking_in_3_days?: number;
    blocking_in_7_days?: number;
    mrr_at_risk_7d?: number;
    negative_deposit?: number;
  };
}

// Core Customer Types
export interface Customer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  phone_secondary?: string | null;
  activation_date?: string | null;
  status: string;
  customer_type: string;
  mrr?: number;
  signup_date: string | null;
  city: string | null;
  state: string | null;
  pop_id?: number | null;
  base_station?: string | null;
  billing_health?: {
    days_until_blocking?: number;
    blocking_date?: string | null;
    deposit_balance?: number;
    overdue_invoices?: number;
    overdue_amount?: number;
  };
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustomerDetail {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  status: string;
  customer_type: string;
  billing_type: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  signup_date: string | null;
  activation_date?: string | null;
  cancellation_date?: string | null;
  mrr?: number;
  labels?: string[];
  invoiced_total?: number;
  paid_total?: number;
  outstanding_balance?: number;
  subscriptions?: Array<{
    id: number;
    plan_name: string;
    price: number;
    status: string;
    start_date: string | null;
    end_date: string | null;
  }>;
  recent_invoices?: Array<{
    id: number;
    invoice_number: string | null;
    total?: number;
    total_amount?: number;
    amount_paid?: number;
    status: string;
    due_date: string | null;
    invoice_date?: string | null;
    days_overdue?: number;
    write_back_status?: string | null;
  }>;
  recent_tickets: Array<{
    id: number;
    subject: string;
    status: string;
    priority: string;
    created_at: string;
  }>;
  recent_conversations?: Array<{
    id: number;
    chatwoot_id: number | null;
    status: string;
    channel: string | null;
    created_at: string | null;
    message_count: number;
  }>;
  billing_health?: {
    days_until_blocking?: number;
    blocking_date?: string | null;
    deposit_balance?: number;
    payment_per_month?: number;
    blocking_in_7_days?: number;
    blocking_in_3_days?: number;
    mrr_at_risk_7d?: number;
    negative_deposit?: number;
  };
  metrics?: {
    total_invoiced: number;
    total_paid: number;
    outstanding: number;
    open_tickets: number;
    total_conversations: number;
  };
}

export interface BlockedCustomer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  pop_id?: number | null;
  customer_type: string;
  plan?: string | null;
  mrr: number;
  signup_date: string | null;
  days_blocked?: number;
  tenure_days?: number;
  billing_health?: {
    days_until_blocking?: number;
    blocking_date?: string | null;
    deposit_balance?: number;
    overdue_invoices?: number;
    overdue_amount?: number;
  };
  payment_history?: Array<{ date: string; amount: number; method?: string | null }>;
  outstanding_balance?: number;
}

export interface BlockedCustomersResponse {
  data?: BlockedCustomer[];
  items?: BlockedCustomer[];
  total: number;
  limit: number;
  offset: number;
}

// Customer Write Payloads
export interface CustomerWritePayload {
  name?: string;
  email?: string | null;
  phone?: string | null;
  customer_type?: 'residential' | 'business' | 'enterprise';
  status?: 'active' | 'inactive' | 'suspended' | 'prospect';
  pop_id?: number | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  mrr?: number | null;
  labels?: string[];
}

export interface CustomerSubscriptionPayload {
  customer_id?: number;
  plan_name?: string;
  status?: 'active' | 'inactive' | 'suspended' | 'expired';
  price?: number;
  currency?: string;
  start_date?: string | null;
  end_date?: string | null;
}

export interface CustomerInvoicePayload {
  customer_id?: number;
  invoice_date?: string | null;
  due_date?: string | null;
  total?: number;
  currency?: string;
  status?: 'pending' | 'overdue' | 'paid' | 'partially_paid' | 'cancelled';
}

export interface CustomerPaymentPayload {
  customer_id?: number;
  amount?: number;
  currency?: string;
  payment_date?: string | null;
  payment_method?: string | null;
  notes?: string | null;
  status?: 'completed' | 'pending' | 'failed' | 'cancelled';
}

// Customer Usage
export interface CustomerUsageTotals {
  upload_bytes: number;
  download_bytes: number;
  upload_gb: number;
  download_gb: number;
  total_gb: number;
}

export interface CustomerUsageDaily {
  date: string;
  upload_bytes: number;
  download_bytes: number;
  upload_gb: number;
  download_gb: number;
  total_gb: number;
}

export interface CustomerUsageBySubscription {
  subscription_id: number;
  plan_name: string;
  upload_gb: number;
  download_gb: number;
  total_gb: number;
  days_with_data: number;
}

export interface CustomerUsageResponse {
  customer_id: number;
  customer_name: string;
  period: { start: string; end: string; days: number };
  totals: CustomerUsageTotals;
  daily: CustomerUsageDaily[];
  by_subscription: CustomerUsageBySubscription[];
}

// Customer 360
export interface Customer360Profile {
  id: number;
  name: string;
  email: string | null;
  billing_email?: string | null;
  phone: string | null;
  phone_secondary?: string | null;
  address: string | null;
  address_2?: string | null;
  city: string | null;
  state: string | null;
  status: string;
  customer_type: string;
  billing_type: string | null;
  account_number?: string | null;
  contract_number?: string | null;
  base_station?: string | null;
  labels?: string[];
  notes?: string | null;
  pop?: { id: number; name: string; location?: string | null };
  dates?: {
    signup?: string | null;
    activation?: string | null;
    cancellation?: string | null;
    contract_end?: string | null;
    last_online?: string | null;
  };
  tenure_days?: number;
  external_ids?: Record<string, string | number | null>;
}

export interface Customer360Finance {
  summary: {
    mrr: number;
    total_invoiced: number;
    total_paid: number;
    outstanding_balance: number;
    overdue_invoices: number;
    overdue_amount: number;
    credit_notes?: number;
    credit_note_total?: number;
    payment_count?: number;
    last_payment_date?: string | null;
  };
  billing_health?: {
    days_until_blocking?: number;
    blocking_date?: string | null;
    deposit_balance?: number;
    payment_per_month?: number;
  };
  recent_invoices?: Array<{
    id: number;
    invoice_number: string | null;
    total_amount: number;
    amount_paid: number;
    balance?: number;
    status: string;
    invoice_date: string | null;
    due_date: string | null;
    days_overdue?: number;
  }>;
  recent_payments?: Array<{
    id: number;
    amount: number;
    payment_date: string | null;
    payment_method: string | null;
    status: string;
    reference: string | null;
  }>;
}

export interface Customer360Services {
  summary?: {
    total_subscriptions?: number;
    active_subscriptions?: number;
    total_mrr?: number;
  };
  usage_30d?: {
    upload_gb: number;
    download_gb: number;
    total_gb: number;
    days_with_data: number;
  };
  subscriptions?: Array<{
    id: number;
    plan_name: string;
    description?: string | null;
    price: number;
    status: string;
    start_date: string | null;
    end_date: string | null;
    download_speed?: string | null;
    upload_speed?: string | null;
    router_id?: number | null;
    ipv4_address?: string | null;
  }>;
}

export interface Customer360Network {
  summary?: { total_ips?: number; active_ips?: number; routers_count?: number };
  ip_addresses?: Array<{
    id: number;
    ip: string;
    hostname?: string | null;
    status: string;
    is_used?: boolean;
    last_check?: string | null;
  }>;
  routers?: Array<{
    id: number;
    name: string;
    ip?: string | null;
    location?: string | null;
    model?: string | null;
    status: string;
  }>;
}

export interface Customer360Support {
  summary?: {
    total_tickets?: number;
    open_tickets?: number;
    replied_tickets?: number;
    closed_tickets?: number;
  };
  tickets?: Array<{
    id: number;
    subject: string;
    status: string;
    priority: string;
    assigned_to?: string | null;
    created_at?: string | null;
    recent_messages?: Array<{
      id: number;
      message: string;
      author?: string | null;
      created_at?: string | null;
    }>;
  }>;
}

export interface Customer360Projects {
  summary?: {
    total_projects?: number;
    active_projects?: number;
    completed_projects?: number;
  };
  projects?: Array<{
    id: number;
    name: string;
    type?: string | null;
    status: string;
    priority?: string | null;
    percent_complete?: number;
    expected_start?: string | null;
    expected_end?: string | null;
    actual_start?: string | null;
    actual_end?: string | null;
    is_overdue?: boolean;
    estimated_cost?: number;
    actual_cost?: number;
  }>;
}

export interface Customer360CRM {
  summary?: {
    total_conversations?: number;
    open_conversations?: number;
    total_notes?: number;
  };
  conversations?: Array<{
    id: number;
    status: string;
    channel: string | null;
    assignee?: string | null;
    message_count?: number;
    created_at?: string | null;
    last_activity?: string | null;
  }>;
  notes?: Array<{
    id: number;
    type?: string | null;
    title?: string | null;
    comment?: string | null;
    is_pinned?: boolean;
    is_done?: boolean;
    created_at?: string | null;
  }>;
}

export interface Customer360TimelineItem {
  type: string;
  date: string;
  title: string;
  description?: string | null;
  status?: string | null;
}

export interface Customer360Response {
  customer_id: number;
  generated_at: string;
  profile: Customer360Profile;
  finance: Customer360Finance;
  services: Customer360Services;
  network?: Customer360Network;
  support?: Customer360Support;
  projects?: Customer360Projects;
  crm?: Customer360CRM;
  timeline?: Customer360TimelineItem[];
}

// Customer Analytics Types
export interface CustomerSignupTrendResponse {
  period: { start: string; end: string };
  interval: 'month' | 'week';
  note?: string;
  data: Array<{
    period: string;
    signups: number;
  }>;
}

export interface CustomerCohortItem {
  cohort: string;
  total_customers: number;
  active?: number;
  churned?: number;
  month_1?: number;
  month_2?: number;
  month_3?: number;
  month_6?: number;
  month_12?: number;
  current_active?: number;
  retention_rate?: number;
}

export interface CustomerCohortResponse {
  period_months?: number;
  cohorts: CustomerCohortItem[];
  summary: {
    avg_retention: number;
    total_cohorts: number;
    total_customers?: number;
    by_status?: {
      active?: number;
      blocked?: number;
      inactive?: number;
      churned?: number;
      new?: number;
    };
  };
}

export interface CustomerByPlanItem {
  plan_name: string;
  customer_count: number;
  subscription_count: number;
  mrr: number;
}

export interface CustomerByType {
  customer_type: string;
  count: number;
  customer_count?: number;
  mrr?: number;
}

export interface CustomerByLocation {
  city: string | null;
  state: string | null;
  customer_count: number;
  mrr?: number;
}

export interface CustomerByTypeResponse {
  by_type: Array<{ type: string; customer_count: number; mrr?: number }>;
  total_active: number;
}

export interface CustomerByLocationResponse {
  by_city: Array<{
    city: string | null;
    count: number;
    mrr?: number;
    state?: string | null;
  }>;
}

export interface CustomerByPop {
  pop_id: number | null;
  pop_name?: string | null;
  customer_count: number;
  mrr?: number;
}

export interface CustomerByRouter {
  router: string;
  pop_id?: number | null;
  customer_count: number;
  mrr?: number;
}

export interface CustomerTicketVolumeBucket {
  bucket: string;
  customer_count: number;
  avg_tickets?: number;
}

export interface CustomerDataQualityOutreach {
  missing_contacts: {
    by_pop: Array<{
      pop_id: number | null;
      pop_name?: string | null;
      missing_email: number;
      missing_phone: number;
      total: number;
    }>;
    by_plan: Array<{
      plan_name: string;
      missing_email: number;
      missing_phone: number;
      total: number;
    }>;
    by_type: Array<{
      customer_type: string;
      missing_email: number;
      missing_phone: number;
      total: number;
    }>;
  };
  linkage_gaps: Array<{
    customer_type: string;
    missing_splynx: number;
    missing_erpnext: number;
    missing_chatwoot: number;
  }>;
}

export interface CustomerRevenueOverdue {
  by_pop: Array<{
    pop_id: number | null;
    pop_name?: string | null;
    customers_with_overdue: number;
    total_overdue: number;
    currency?: string | null;
  }>;
  by_plan: Array<{
    plan_name: string;
    customers_with_overdue: number;
    total_overdue: number;
    currency?: string | null;
  }>;
}

export interface ActiveAnalyticsResponse {
  overview: {
    total_active: number;
    total_mrr: number;
    avg_mrr?: number;
    new_signups?: number;
    by_type?: Array<{ type: string; count: number; mrr?: number }>;
  };
  by_tenure?: Array<{ bucket: string; count: number; mrr?: number }>;
  by_plan?: Array<{ plan_name: string; customer_count: number; mrr: number }>;
  by_location?: Array<{
    pop_id?: number | null;
    pop_name?: string | null;
    customer_count: number;
    mrr?: number;
  }>;
  service_health?: {
    no_recent_usage?: Array<{
      name: string;
      mrr: number;
      last_seen?: string | null;
    }>;
    low_usage?: Array<{
      name: string;
      mrr: number;
      last_seen?: string | null;
    }>;
    inactive_7_days?: Array<{
      name: string;
      mrr: number;
      last_seen?: string | null;
    }>;
  };
  payment_risk?: {
    blocking_soon?: number;
    overdue_invoices?: number;
    negative_deposit?: number;
    mrr_at_risk?: number;
  };
  top_customers?: Array<{
    customer_id?: number;
    name: string;
    mrr: number;
    last_seen?: string | null;
    status?: string | null;
  }>;
  support_concerns?: Array<{
    customer_id?: number;
    name: string;
    ticket_count: number;
    mrr?: number;
  }>;
}

export interface CustomerPaymentTimeliness {
  window_days: number;
  by_type: Array<{
    customer_type: string;
    early: number;
    on_time: number;
    late: number;
    on_time_rate: number;
  }>;
  by_plan: Array<{
    plan_name: string;
    early: number;
    on_time: number;
    late: number;
    on_time_rate: number;
  }>;
}

// Customer Insights Types
export interface CustomerSegmentsInsightsResponse {
  by_status: Array<{ status: string; count: number; total_mrr: number }>;
  by_type: Array<{ type: string; count: number; total_mrr: number }>;
  by_billing: Array<{ billing_type: string; count: number; total_mrr: number }>;
  by_tenure: Array<{ segment: string; count: number }>;
  by_mrr: Array<{ segment: string; count: number }>;
  by_city?: Array<{ city: string | null; count: number; total_mrr: number }>;
}

export interface CustomerHealthInsightsResponse {
  total_active_customers: number;
  payment_behavior: {
    customers_with_overdue: number;
    overdue_rate: number;
    payment_timing: {
      early: number;
      on_time: number;
      late: number;
      on_time_rate: number;
    };
  };
  support_intensity: {
    customers_with_tickets_30d: number;
    high_support_customers: number;
    high_support_rate: number;
  };
  churn_indicators: {
    recently_cancelled_30d: number;
    currently_suspended: number;
    at_risk_total: number;
  };
}

export interface CustomerCompletenessField {
  field: string;
  filled: number;
  total: number;
  percent: number;
  missing: number;
  fill_rate?: number;
}

export interface CustomerCompletenessResponse {
  total_customers: number;
  scores: {
    critical_completeness: number;
    overall_completeness: number;
  };
  fields: Record<string, { count: number; percent: number; missing: number }>;
  system_linkage: Record<string, { count: number; percent: number }>;
  recommendations: Array<{
    priority: 'high' | 'medium' | 'low';
    field: string;
    issue: string;
    action: string;
  }>;
}

export interface CustomerPlanChange {
  customer_id: number;
  from_plan: string;
  to_plan: string;
  price_change: number;
  change_type: 'upgrade' | 'downgrade' | 'lateral';
  date: string;
}

export interface CustomerPlanChangesResponse {
  period_months: number;
  summary: {
    customers_with_plan_changes: number;
    total_changes: number;
    upgrades: number;
    downgrades: number;
    lateral_moves: number;
  };
  revenue_impact: {
    upgrade_mrr_gained: number;
    downgrade_mrr_lost: number;
    net_mrr_change: number;
  };
  rates: {
    upgrade_rate: number;
    downgrade_rate: number;
    upgrade_to_downgrade_ratio: number;
  };
  common_transitions: Array<{
    transition: string;
    count: number;
    type: 'upgrade' | 'downgrade' | 'lateral';
  }>;
  recent_changes: CustomerPlanChange[];
}

// Customer Segments & Health (from /insights endpoints)
export interface CustomerSegment {
  segment: string;
  count: number;
  percentage: number;
  avg_mrr?: number;
  total_mrr?: number;
}

export interface CustomerSegmentsResponse {
  by_status: CustomerSegment[];
  by_type: CustomerSegment[];
  by_billing_type: CustomerSegment[];
  by_tenure: CustomerSegment[];
  by_mrr_tier: CustomerSegment[];
  by_geography: CustomerSegment[];
  by_pop: CustomerSegment[];
  total_customers: number;
}

export interface CustomerHealthRecord {
  customer_id: number;
  customer_name: string;
  email: string | null;
  status: string;
  health_score: number;
  risk_level: string;
  payment_health: {
    days_since_last_payment: number | null;
    outstanding_amount: number;
    overdue_invoices: number;
    payment_regularity: string;
  };
  support_health: {
    open_tickets: number;
    recent_conversations: number;
    avg_resolution_time: number | null;
  };
  engagement: {
    tenure_days: number;
    subscription_count: number;
    mrr: number;
  };
  risk_factors: string[];
  opportunities: string[];
}

export interface CustomerHealthResponse {
  customers: CustomerHealthRecord[];
  summary: {
    total_analyzed: number;
    health_distribution: Record<string, number>;
    at_risk_count: number;
    avg_health_score: number;
  };
  recommendations: string[];
}

// Parameter Types
export interface CustomerListParams {
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
}

export interface BlockedCustomerParams {
  min_days_blocked?: number;
  max_days_blocked?: number;
  pop_id?: number;
  plan?: string;
  min_mrr?: number;
  sort_by?: 'mrr' | 'days_blocked' | 'tenure';
  limit?: number;
  offset?: number;
}

export interface CustomerSignupTrendParams {
  start_date?: string;
  end_date?: string;
  interval?: 'month' | 'week';
  months?: number;
}

// =============================================================================
// API
// =============================================================================

export const customersApi = {
  // =========================================================================
  // CUSTOMERS - CORE
  // =========================================================================

  getDashboard: () => fetchApi<CustomerDashboard>('/customers/dashboard'),

  getCustomers: (params?: CustomerListParams) =>
    fetchApi<CustomerListResponse>('/customers', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getCustomer: (id: number) => fetchApi<CustomerDetail>(`/customers/${id}`),

  getCustomerUsage: (
    id: number,
    params?: { start_date?: string; end_date?: string }
  ) => fetchApi<CustomerUsageResponse>(`/customers/${id}/usage`, { params }),

  getCustomer360: (id: number) =>
    fetchApi<Customer360Response>(`/customers/360/${id}`),

  createCustomer: (payload: CustomerWritePayload) =>
    fetchApi<CustomerDetail>('/customers', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCustomer: (id: number, payload: CustomerWritePayload) =>
    fetchApi<CustomerDetail>(`/customers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteCustomer: (id: number, soft = true) =>
    fetchApi<void>(`/customers/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getBlockedCustomers: (params?: BlockedCustomerParams) =>
    fetchApi<BlockedCustomersResponse>('/customers/blocked', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  // =========================================================================
  // SUBSCRIPTIONS
  // =========================================================================

  createSubscription: (payload: CustomerSubscriptionPayload) =>
    fetchApi('/customers/subscriptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSubscription: (id: number, payload: CustomerSubscriptionPayload) =>
    fetchApi(`/customers/subscriptions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteSubscription: (id: number, soft = true) =>
    fetchApi<void>(
      `/customers/subscriptions/${id}?soft=${soft ? 'true' : 'false'}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // INVOICES
  // =========================================================================

  createInvoice: (payload: CustomerInvoicePayload) =>
    fetchApi('/customers/invoices', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateInvoice: (id: number, payload: CustomerInvoicePayload) =>
    fetchApi(`/customers/invoices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteInvoice: (id: number, soft = true) =>
    fetchApi<void>(
      `/customers/invoices/${id}?soft=${soft ? 'true' : 'false'}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // PAYMENTS
  // =========================================================================

  createPayment: (payload: CustomerPaymentPayload) =>
    fetchApi('/customers/payments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updatePayment: (id: number, payload: CustomerPaymentPayload) =>
    fetchApi(`/customers/payments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deletePayment: (id: number, soft = true) =>
    fetchApi<void>(
      `/customers/payments/${id}?soft=${soft ? 'true' : 'false'}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // ANALYTICS
  // =========================================================================

  getBlockedAnalytics: () =>
    fetchApi<unknown>('/customers/analytics/blocked'),

  getActiveAnalytics: () =>
    fetchApi<ActiveAnalyticsResponse>('/customers/analytics/active'),

  getSignupTrend: (params?: CustomerSignupTrendParams) =>
    fetchApi<CustomerSignupTrendResponse>('/customers/analytics/signup-trend', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getCohort: (months = 12) =>
    fetchApi<CustomerCohortResponse>('/customers/analytics/cohort', {
      params: { months },
    }),

  getByPlan: () =>
    fetchApi<CustomerByPlanItem[]>('/customers/analytics/by-plan'),

  getByType: () =>
    fetchApi<CustomerByTypeResponse>('/customers/analytics/by-type'),

  getByLocation: (limit?: number) =>
    fetchApi<CustomerByLocationResponse>('/customers/analytics/by-location', {
      params: { limit },
    }),

  getByPop: () => fetchApi<CustomerByPop[]>('/customers/analytics/by-pop'),

  getByRouter: (popId?: number) =>
    fetchApi<CustomerByRouter[]>('/customers/analytics/by-router', {
      params: { pop_id: popId },
    }),

  getByTicketVolume: (days = 30) =>
    fetchApi<CustomerTicketVolumeBucket[]>(
      '/customers/analytics/by-ticket-volume',
      { params: { days } }
    ),

  getDataQualityOutreach: () =>
    fetchApi<CustomerDataQualityOutreach>(
      '/customers/analytics/data-quality/outreach'
    ),

  getRevenueOverdue: (popId?: number, planName?: string) =>
    fetchApi<CustomerRevenueOverdue>('/customers/analytics/revenue/overdue', {
      params: { pop_id: popId, plan_name: planName },
    }),

  getPaymentTimeliness: (days = 30) =>
    fetchApi<CustomerPaymentTimeliness>(
      '/customers/analytics/revenue/payment-timeliness',
      { params: { days } }
    ),

  // =========================================================================
  // INSIGHTS
  // =========================================================================

  getSegmentsInsights: () =>
    fetchApi<CustomerSegmentsInsightsResponse>('/customers/insights/segments'),

  getHealthInsights: () =>
    fetchApi<CustomerHealthInsightsResponse>('/customers/insights/health'),

  getCompletenessInsights: () =>
    fetchApi<CustomerCompletenessResponse>('/customers/insights/completeness'),

  getPlanChanges: (months = 6) =>
    fetchApi<CustomerPlanChangesResponse>('/customers/insights/plan-changes', {
      params: { months },
    }),

  // =========================================================================
  // SEGMENTS & HEALTH (from /insights endpoints)
  // =========================================================================

  getSegments: () =>
    fetchApi<CustomerSegmentsResponse>('/insights/customer-segments'),

  getHealth: (limit = 100, riskLevel?: string) =>
    fetchApi<CustomerHealthResponse>('/insights/customer-health', {
      params: { limit, risk_level: riskLevel },
    }),
};

export default customersApi;
