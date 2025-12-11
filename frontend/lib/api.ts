const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// Auth event types for global handling
type AuthEventType = 'unauthorized' | 'forbidden' | 'token_expired';
type AuthEventHandler = (event: AuthEventType, message?: string) => void;

let authEventHandler: AuthEventHandler | null = null;

/**
 * Register a global auth event handler for 401/403 responses.
 * This should be called once in the app root to handle auth state globally.
 */
export function onAuthError(handler: AuthEventHandler): () => void {
  authEventHandler = handler;
  return () => {
    authEventHandler = null;
  };
}

/**
 * Clear the stored access token and trigger re-authentication.
 */
export function clearAuthToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('dotmac_access_token');
  }
}

/**
 * Set the access token for API calls.
 */
export function setAuthToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('dotmac_access_token', token);
  }
}

/**
 * Check if user has a valid auth token stored.
 */
export function hasAuthToken(): boolean {
  if (typeof window !== 'undefined') {
    return !!localStorage.getItem('dotmac_access_token');
  }
  return false;
}

function getAccessToken(): string {
  if (typeof window !== 'undefined') {
    // Client-side: only use stored user token
    const token = localStorage.getItem('dotmac_access_token');
    if (token) return token;

    // Fallback: allow NEXT_PUBLIC_SERVICE_TOKEN when set (primarily for local/dev)
    if (process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
      return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
    }
    return '';
  }
  // Server-side fallback for SSR/exports
  if (process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
    return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
  }
  return '';
}

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE}/api${endpoint}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const accessToken = getAccessToken();

  const response = await fetch(url, {
    ...fetchOptions,
    // Don't include credentials for cross-origin requests with Bearer token
    // CORS with credentials: 'include' requires specific origin header, not wildcard '*'
    credentials: accessToken ? 'omit' : 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const errorMessage = error.detail || `HTTP ${response.status}`;

    // Handle authentication errors globally
    if (response.status === 401) {
      clearAuthToken();
      if (authEventHandler) {
        authEventHandler('unauthorized', errorMessage);
      }
      throw new ApiError(response.status, 'Authentication required. Please sign in.');
    }

    if (response.status === 403) {
      if (authEventHandler) {
        authEventHandler('forbidden', errorMessage);
      }
      throw new ApiError(response.status, 'Access denied. You do not have permission to access this resource.');
    }

    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

// API Types
export interface OverviewData {
  customers: {
    total: number;
    active: number;
    churned: number;
    churn_rate: number;
  };
  revenue: {
    mrr: number;
    outstanding: number;
    overdue_invoices: number;
    currency: string | null;
  };
  support: {
    open_tickets: number;
  };
  operations: {
    pop_count: number;
  };
}

export interface PopPerformance {
  id: number;
  name: string;
  code: string | null;
  city: string | null;
  total_customers: number;
  active_customers: number;
  churned_customers: number;
  churn_rate: number;
  mrr: number;
  open_tickets: number;
  outstanding: number;
  currency: string | null;
}

export interface RevenueTrend {
  year: number;
  month: number;
  period: string;
  revenue: number;
  total: number; // alias for revenue
  payment_count: number;
}

export interface ChurnTrend {
  year: number;
  month: number;
  period: string;
  churned: number;
  churned_count?: number; // legacy
}

// Customer Domain Types (spec-aligned)
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
    invoices?: { total_invoiced?: number; outstanding?: number; overdue_count?: number; overdue_amount?: number };
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
    usage_30d?: { total_upload_gb?: number; total_download_gb?: number; customers_with_data?: number };
  };
  support?: {
    tickets?: { total?: number; open?: number; closed?: number; created_last_30d?: number };
    customers_with_open_tickets?: number;
  };
  projects?: { total?: number; active?: number; completed?: number };
  crm?: { conversations?: { total?: number; open?: number; created_last_30d?: number } };
  generated_at?: string;
  // Legacy fields (fallback)
  total_customers?: number;
  by_status?: { active: number; blocked?: number; suspended?: number; cancelled?: number; inactive?: number; pending?: number; new?: number };
  activity_30d?: { new_signups: number; churned: number; net_change: number };
  health?: { with_overdue_invoices: number; with_open_tickets: number };
  billing_health?: {
    blocking_in_3_days?: number;
    blocking_in_7_days?: number;
    mrr_at_risk_7d?: number;
    negative_deposit?: number;
  };
}

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
  dates?: { signup?: string | null; activation?: string | null; cancellation?: string | null; contract_end?: string | null; last_online?: string | null };
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
  summary?: { total_subscriptions?: number; active_subscriptions?: number; total_mrr?: number };
  usage_30d?: { upload_gb: number; download_gb: number; total_gb: number; days_with_data: number };
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
  ip_addresses?: Array<{ id: number; ip: string; hostname?: string | null; status: string; is_used?: boolean; last_check?: string | null }>;
  routers?: Array<{ id: number; name: string; ip?: string | null; location?: string | null; model?: string | null; status: string }>;
}

export interface Customer360Support {
  summary?: { total_tickets?: number; open_tickets?: number; replied_tickets?: number; closed_tickets?: number };
  tickets?: Array<{
    id: number;
    subject: string;
    status: string;
    priority: string;
    assigned_to?: string | null;
    created_at?: string | null;
    recent_messages?: Array<{ id: number; message: string; author?: string | null; created_at?: string | null }>;
  }>;
}

export interface Customer360Projects {
  summary?: { total_projects?: number; active_projects?: number; completed_projects?: number };
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
  summary?: { total_conversations?: number; open_conversations?: number; total_notes?: number };
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
  by_city: Array<{ city: string | null; count: number; mrr?: number; state?: string | null }>;
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
  bucket: string; // e.g. "0", "1-2", "3-5", "6+"
  customer_count: number;
  avg_tickets?: number;
}

export interface CustomerDataQualityOutreach {
  missing_contacts: {
    by_pop: Array<{ pop_id: number | null; pop_name?: string | null; missing_email: number; missing_phone: number; total: number }>;
    by_plan: Array<{ plan_name: string; missing_email: number; missing_phone: number; total: number }>;
    by_type: Array<{ customer_type: string; missing_email: number; missing_phone: number; total: number }>;
  };
  linkage_gaps: Array<{ customer_type: string; missing_splynx: number; missing_erpnext: number; missing_chatwoot: number }>;
}

export interface CustomerRevenueOverdue {
  by_pop: Array<{ pop_id: number | null; pop_name?: string | null; customers_with_overdue: number; total_overdue: number; currency?: string | null }>;
  by_plan: Array<{ plan_name: string; customers_with_overdue: number; total_overdue: number; currency?: string | null }>;
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
  by_location?: Array<{ pop_id?: number | null; pop_name?: string | null; customer_count: number; mrr?: number }>;
  service_health?: {
    no_recent_usage?: Array<{ name: string; mrr: number; last_seen?: string | null }>;
    low_usage?: Array<{ name: string; mrr: number; last_seen?: string | null }>;
    inactive_7_days?: Array<{ name: string; mrr: number; last_seen?: string | null }>;
  };
  payment_risk?: {
    blocking_soon?: number;
    overdue_invoices?: number;
    negative_deposit?: number;
    mrr_at_risk?: number;
  };
  top_customers?: Array<{ customer_id?: number; name: string; mrr: number; last_seen?: string | null; status?: string | null }>;
  support_concerns?: Array<{ customer_id?: number; name: string; ticket_count: number; mrr?: number }>;
}

export interface CustomerPaymentTimeliness {
  window_days: number;
  by_type: Array<{ customer_type: string; early: number; on_time: number; late: number; on_time_rate: number }>;
  by_plan: Array<{ plan_name: string; early: number; on_time: number; late: number; on_time_rate: number }>;
}

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
  fill_rate?: number; // fallback naming used by some responses
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

export interface InvoiceAging {
  total_outstanding: number;
  aging: {
    current: { count: number; amount: number };
    '1_30_days': { count: number; amount: number };
    '31_60_days': { count: number; amount: number };
    '61_90_days': { count: number; amount: number };
    over_90_days: { count: number; amount: number };
  };
}

export interface PlanDistribution {
  plan_name: string;
  customer_count: number;
  mrr: number;
}

// Backend returns flat map: { splynx: {...}, erpnext: {...}, chatwoot: {...} }
export interface SyncSourceStatus {
  last_sync: string | null;
  status: string;
  entity_type?: string;
  records_created?: number;
  records_updated?: number;
  duration_seconds?: number;
  error?: string | null;
}

export interface SyncStatus {
  splynx?: SyncSourceStatus;
  erpnext?: SyncSourceStatus;
  chatwoot?: SyncSourceStatus;
  [key: string]: SyncSourceStatus | undefined;
}

export interface TableInfo {
  [table: string]: {
    count: number;
    columns: string[];
  };
}

export interface EnhancedTableInfo {
  name: string;
  count: number;
  columns: string[];
  date_columns: string[];
  category: string;
  category_label: string;
}

export interface TablesResponse {
  tables: Record<string, EnhancedTableInfo>;
  categories: Record<string, string>;
  by_category: Record<string, EnhancedTableInfo[]>;
  total_tables: number;
  total_records: number;
}

export interface ExploreTableResponse {
  table: string;
  total: number;
  limit: number;
  offset: number;
  date_columns: string[];
  columns: string[];
  filters_applied: {
    date_column?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  };
  data: Record<string, unknown>[];
}

export interface DataQuality {
  customers: {
    total: number;
    completeness: {
      has_email: number;
      has_phone: number;
      has_pop: number;
    };
    linkage: {
      linked_to_splynx: number;
      linked_to_erpnext: number;
      linked_to_chatwoot: number;
    };
    quality_score: number;
  };
  invoices: {
    total: number;
    linked_to_customer: number;
    unlinked: number;
  };
  conversations: {
    total: number;
    linked_to_customer: number;
    unlinked: number;
  };
  summary: {
    total_records: number;
    last_sync_check: string;
  };
}

// API Functions
export const api = {
  // Overview & Analytics
  getOverview: (currency?: string) =>
    fetchApi<OverviewData>('/analytics/overview', { params: { currency } }),

  getRevenueTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<RevenueTrend[]>('/analytics/revenue/trend', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getChurnTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<ChurnTrend[]>('/analytics/churn/trend', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getPopPerformance: (currency?: string) =>
    fetchApi<PopPerformance[]>('/analytics/pop/performance', { params: { currency } }),

  getSupportMetrics: (days = 30) =>
    fetchApi<SupportMetrics>('/analytics/support/metrics', { params: { days } }),

  getInvoiceAging: () =>
    fetchApi<InvoiceAging>('/analytics/invoices/aging'),

  getPlanDistribution: (currency?: string) =>
    fetchApi<PlanDistribution[]>('/analytics/customers/by-plan', { params: { currency } }),

  // Customers - Domain Router
  getCustomerDashboard: () =>
    fetchApi<CustomerDashboard>('/customers/dashboard'),

  getCustomers: (params?: {
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
  }) =>
    fetchApi<CustomerListResponse>('/customers', { params }),

  getCustomer: (id: number) =>
    fetchApi<CustomerDetail>(`/customers/${id}`),

  getCustomerUsage: (id: number, params?: { start_date?: string; end_date?: string }) =>
    fetchApi<CustomerUsageResponse>(`/customers/${id}/usage`, { params }),

  getCustomer360: (id: number) =>
    fetchApi<Customer360Response>(`/customers/360/${id}`),

  getBlockedCustomers: (params?: {
    min_days_blocked?: number;
    max_days_blocked?: number;
    pop_id?: number;
    plan?: string;
    min_mrr?: number;
    sort_by?: 'mrr' | 'days_blocked' | 'tenure';
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<{ data?: BlockedCustomer[]; items?: BlockedCustomer[]; total: number; limit: number; offset: number }>(
      '/customers/blocked',
      { params }
    ),

  // Customer Analytics
  getBlockedAnalytics: () =>
    fetchApi<any>('/customers/analytics/blocked'),

  getActiveAnalytics: () =>
    fetchApi<ActiveAnalyticsResponse>('/customers/analytics/active'),

  getCustomerSignupTrend: (params?: { start_date?: string; end_date?: string; interval?: 'month' | 'week'; months?: number }) =>
    fetchApi<CustomerSignupTrendResponse>('/customers/analytics/signup-trend', { params }),

  getCustomerCohort: (months = 12) =>
    fetchApi<CustomerCohortResponse>('/customers/analytics/cohort', { params: { months } }),

  getCustomersByPlan: () =>
    fetchApi<CustomerByPlanItem[]>('/customers/analytics/by-plan'),

  getCustomersByType: () =>
    fetchApi<CustomerByTypeResponse>('/customers/analytics/by-type'),

  getCustomersByLocation: (limit?: number) =>
    fetchApi<CustomerByLocationResponse>('/customers/analytics/by-location', { params: { limit } }),

  getCustomersByPop: () =>
    fetchApi<CustomerByPop[]>('/customers/analytics/by-pop'),

  getCustomersByRouter: (popId?: number) =>
    fetchApi<CustomerByRouter[]>('/customers/analytics/by-router', { params: { pop_id: popId } }),

  getCustomersByTicketVolume: (days = 30) =>
    fetchApi<CustomerTicketVolumeBucket[]>('/customers/analytics/by-ticket-volume', { params: { days } }),

  getCustomerDataQualityOutreach: () =>
    fetchApi<CustomerDataQualityOutreach>('/customers/analytics/data-quality/outreach'),

  getCustomerRevenueOverdue: (popId?: number, planName?: string) =>
    fetchApi<CustomerRevenueOverdue>('/customers/analytics/revenue/overdue', { params: { pop_id: popId, plan_name: planName } }),

  getCustomerPaymentTimeliness: (days = 30) =>
    fetchApi<CustomerPaymentTimeliness>('/customers/analytics/revenue/payment-timeliness', { params: { days } }),

  // Customer Insights
  getCustomerSegmentsInsights: () =>
    fetchApi<CustomerSegmentsInsightsResponse>('/customers/insights/segments'),

  getCustomerHealthInsights: () =>
    fetchApi<CustomerHealthInsightsResponse>('/customers/insights/health'),

  getCustomerCompletenessInsights: () =>
    fetchApi<CustomerCompletenessResponse>('/customers/insights/completeness'),

  getCustomerPlanChanges: (months = 6) =>
    fetchApi<CustomerPlanChangesResponse>('/customers/insights/plan-changes', { params: { months } }),

  // Sync
  getSyncStatus: () =>
    fetchApi<SyncStatus>('/sync/status'),

  triggerSync: (source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) =>
    fetchApi<{ message: string }>(`/sync/${source}`, {
      method: 'POST',
      params: { full_sync: fullSync },
    }),

  testConnections: () =>
    fetchApi<Record<string, boolean>>('/sync/test-connections', { method: 'POST' }),

  // Data Explorer
  getTables: () =>
    fetchApi<TableInfo>('/explore/tables'),

  getTablesEnhanced: () =>
    fetchApi<TablesResponse>('/explore/tables'),

  getTableData: (table: string, params?: {
    limit?: number;
    offset?: number;
    order_by?: string;
    order_dir?: 'asc' | 'desc';
  }) =>
    fetchApi<{ table: string; total: number; data: Record<string, unknown>[] }>(
      `/explore/tables/${table}`,
      { params }
    ),

  getTableDataEnhanced: (table: string, params?: {
    limit?: number;
    offset?: number;
    order_by?: string;
    order_dir?: 'asc' | 'desc';
    date_column?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  }) =>
    fetchApi<ExploreTableResponse>(
      `/explore/tables/${table}`,
      { params }
    ),

  exportTableData: async (table: string, format: 'csv' | 'json', params?: {
    date_column?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  }) => {
    const queryParams: Record<string, string | undefined> = {
      format,
      ...params,
    };
    const searchParams = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value);
      }
    });

    const accessToken = getAccessToken();
    const response = await fetch(
      `${API_BASE}/api/explore/tables/${table}/export?${searchParams.toString()}`,
      {
        credentials: accessToken ? 'omit' : 'include',
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      }
    );

    if (!response.ok) {
      throw new ApiError(response.status, `Export failed: ${response.statusText}`);
    }

    return response.blob();
  },

  getTableStats: (table: string) =>
    fetchApi<Record<string, unknown>>(`/explore/tables/${table}/stats`),

  getDataQuality: () =>
    fetchApi<DataQuality>('/explore/data-quality'),

  search: (q: string, limit = 50) =>
    fetchApi<Record<string, unknown[]>>('/explore/search', { params: { q, limit } }),

  // Sync Logs
  getSyncLogs: (limit = 50) =>
    fetchApi<SyncLog[]>('/sync/logs', { params: { limit } }),

  // Churn Risk
  getChurnRisk: (limit = 20) =>
    fetchApi<{ summary: { overdue_customers: number; recent_cancellations_30d: number; suspended_customers: number; high_ticket_customers: number }; customers?: ChurnRiskCustomer[] }>('/insights/churn-risk', { params: { limit } }),

  // Revenue Quality Analytics
  getDSOTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<DSOTrend>('/analytics/revenue/dso', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getRevenueByTerritory: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<TerritoryRevenue[]>('/analytics/revenue/by-territory', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getRevenueCohort: () =>
    fetchApi<CohortData>('/analytics/revenue/cohort'),

  // Collections & Risk Analytics
  getAgingBySegment: () =>
    fetchApi<AgingBySegment>('/analytics/collections/aging-by-segment'),

  getCreditNotesSummary: (months = 12) =>
    fetchApi<CreditNoteSummary>('/analytics/collections/credit-notes', { params: { months } }),

  // Sales Pipeline Analytics
  getSalesPipeline: () =>
    fetchApi<SalesPipeline>('/analytics/sales/pipeline'),

  getQuotationTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<QuotationTrend[]>('/analytics/sales/quotation-trend', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  // Support/SLA Analytics
  getSLAAttainment: (days = 30) =>
    fetchApi<SLAAttainment>('/analytics/support/sla-attainment', { params: { days } }),

  getAgentProductivity: (days = 30) =>
    fetchApi<AgentProductivity[]>('/analytics/support/agent-productivity', { params: { days } }),

  getTicketsByType: (days = 30) =>
    fetchApi<TicketsByType>('/analytics/support/by-type', { params: { days } }),

  // Network/Service Analytics
  getNetworkDeviceStatus: () =>
    fetchApi<NetworkDeviceStatus>('/analytics/network/device-status'),

  getIPUtilization: () =>
    fetchApi<IPUtilization>('/analytics/network/ip-utilization'),

  // Expense/Cost Analytics
  getExpensesByCategory: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<ExpenseByCategory>('/analytics/expenses/by-category', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getExpensesByCostCenter: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<ExpenseByCostCenter>('/analytics/expenses/by-cost-center', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getExpenseTrend: (months = 12, startDate?: string, endDate?: string) =>
    fetchApi<ExpenseTrend[]>('/analytics/expenses/trend', {
      params: { months, start_date: startDate, end_date: endDate }
    }),

  getVendorSpend: (months = 12, limit = 20, startDate?: string, endDate?: string) =>
    fetchApi<VendorSpend>('/analytics/expenses/vendor-spend', {
      params: { months, limit, start_date: startDate, end_date: endDate }
    }),

  // People/Ops Analytics
  getTicketsPerEmployee: (days = 30) =>
    fetchApi<TicketsPerEmployee>('/analytics/people/tickets-per-employee', { params: { days } }),

  getMetricsByDepartment: (days = 30) =>
    fetchApi<DepartmentMetrics[]>('/analytics/people/by-department', { params: { days } }),

  // Deep Insights
  getDataCompleteness: () =>
    fetchApi<DataCompletenessResponse>('/insights/data-completeness'),

  getCustomerSegments: () =>
    fetchApi<CustomerSegmentsResponse>('/insights/customer-segments'),

  getCustomerHealth: (limit = 100, riskLevel?: string) =>
    fetchApi<CustomerHealthResponse>('/insights/customer-health', {
      params: { limit, risk_level: riskLevel }
    }),

  getRelationshipMap: () =>
    fetchApi<RelationshipMapResponse>('/insights/relationship-map'),

  getFinancialInsights: () =>
    fetchApi<FinancialInsightsResponse>('/insights/financial-insights'),

  getOperationalInsights: () =>
    fetchApi<OperationalInsightsResponse>('/insights/operational-insights'),

  getAnomalies: () =>
    fetchApi<AnomaliesResponse>('/insights/anomalies'),

  getDataAvailability: () =>
    fetchApi<DataAvailabilityResponse>('/insights/data-availability'),

// Finance Domain
  getFinanceDashboard: (currency?: string) =>
    fetchApi<FinanceDashboard>('/finance/dashboard', {
      params: { currency }
    }),

  getFinanceInvoices: (params?: {
    status?: string;
    customer_id?: number;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    overdue_only?: boolean;
    search?: string;
    sort_by?: 'invoice_date' | 'due_date' | 'total_amount' | 'amount_paid' | 'customer_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<FinanceInvoiceListResponse>('/finance/invoices', { params }),

  getFinancePayments: (params?: {
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
    sort_by?: 'payment_date' | 'amount' | 'customer_id' | 'invoice_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<FinancePaymentListResponse>('/finance/payments', { params }),

  getFinanceCreditNotes: (params?: {
    customer_id?: number;
    invoice_id?: number;
    start_date?: string;
    end_date?: string;
    currency?: string;
    search?: string;
    sort_by?: 'issue_date' | 'amount' | 'customer_id' | 'invoice_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<FinanceCreditNoteListResponse>('/finance/credit-notes', { params }),

  getFinanceRevenueTrend: (params?: { start_date?: string; end_date?: string; interval?: 'month' | 'week'; currency?: string }) =>
    fetchApi<FinanceRevenueTrend[]>('/finance/analytics/revenue-trend', {
      params
    }),

  getFinanceCollections: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<FinanceCollectionsAnalytics>('/finance/analytics/collections', {
      params
    }),

  getFinanceAging: (params?: { as_of_date?: string; currency?: string }) =>
    fetchApi<FinanceAgingAnalytics>('/finance/analytics/aging', { params }),

  getFinanceRevenueBySegment: () =>
    fetchApi<FinanceByCurrencyAnalytics>('/finance/analytics/by-currency'),

  getFinancePaymentBehavior: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<FinancePaymentBehavior>('/finance/insights/payment-behavior', { params }),

  getFinanceForecasts: (currency?: string) =>
    fetchApi<FinanceForecast>('/finance/insights/forecasts', { params: { currency } }),

  getFinanceInvoiceDetail: (id: number, currency?: string) =>
    fetchApi<FinanceInvoiceDetail>(`/finance/invoices/${id}`, { params: { currency } }),

  getFinancePaymentDetail: (id: number, currency?: string) =>
    fetchApi<FinancePaymentDetail>(`/finance/payments/${id}`, { params: { currency } }),

  getFinanceCreditNoteDetail: (id: number, currency?: string) =>
    fetchApi<FinanceCreditNoteDetail>(`/finance/credit-notes/${id}`, { params: { currency } }),

  // Accounting Domain
  getAccountingDashboard: () =>
    fetchApi<AccountingDashboard>('/accounting/dashboard'),

  getAccountingChartOfAccounts: (accountType?: string) =>
    fetchApi<AccountingChartOfAccounts>('/accounting/chart-of-accounts', {
      params: { account_type: accountType }
    }),

  getAccountingTrialBalance: (asOfDate?: string) =>
    fetchApi<AccountingTrialBalance>('/accounting/trial-balance', {
      params: { as_of_date: asOfDate }
    }),

  getAccountingBalanceSheet: (asOfDate?: string) =>
    fetchApi<AccountingBalanceSheet>('/accounting/balance-sheet', {
      params: { as_of_date: asOfDate }
    }),

  getAccountingIncomeStatement: (startDate?: string, endDate?: string) =>
    fetchApi<AccountingIncomeStatement>('/accounting/income-statement', {
      params: { start_date: startDate, end_date: endDate }
    }),

  getAccountingGeneralLedger: (params?: {
    account?: string;
    start_date?: string;
    end_date?: string;
    voucher_type?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingGeneralLedgerResponse>('/accounting/general-ledger', { params }),

  getAccountingCashFlow: (startDate?: string, endDate?: string) =>
    fetchApi<AccountingCashFlow>('/accounting/cash-flow', {
      params: { start_date: startDate, end_date: endDate }
    }),

  getAccountingPayables: (params?: {
    supplier_id?: number;
    min_amount?: number;
    limit?: number;
    offset?: number;
    currency?: string;
    aging_bucket?: string;
    search?: string;
  }) =>
    fetchApi<AccountingPayableResponse>('/accounting/accounts-payable', { params }),

  getAccountingReceivables: (params?: {
    customer_id?: number;
    min_amount?: number;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingReceivableResponse>('/accounting/accounts-receivable', { params }),

  getAccountingJournalEntries: (params?: {
    voucher_type?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingJournalEntryListResponse>('/accounting/journal-entries', { params }),

  getAccountingSuppliers: (params?: {
    search?: string;
    supplier_group?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingSupplierListResponse>('/accounting/suppliers', { params }),

  getAccountingBankAccounts: () =>
    fetchApi<AccountingBankAccountListResponse>('/accounting/bank-accounts'),

  getAccountingFiscalYears: () =>
    fetchApi<AccountingFiscalYearListResponse>('/accounting/fiscal-years'),

  getAccountingCostCenters: () =>
    fetchApi<AccountingCostCenterListResponse>('/accounting/cost-centers'),

  // Data Explorer - Query specific entity
  // Uses /explore/tables/{table} for simple queries or /explore/query for filtered queries
  exploreEntity: async (entity: string, params: Record<string, unknown>) => {
    const { limit, offset, fields, ...filters } = params as {
      limit?: number;
      offset?: number;
      fields?: string[];
      [key: string]: unknown;
    };

    const hasFilters = Object.keys(filters).length > 0;

    if (hasFilters) {
      // Use POST /explore/query for filtered queries
      const body: Record<string, unknown> = {
        table: entity,
        limit: limit || 100,
      };

      // Convert filters to backend format
      const backendFilters: Record<string, unknown> = {};
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          backendFilters[key] = value;
        }
      });

      if (Object.keys(backendFilters).length > 0) {
        body.filters = backendFilters;
      }

      const result = await fetchApi<{ total?: number; limit: number; data: Record<string, unknown>[]; grouped: boolean }>(
        '/explore/query',
        {
          method: 'POST',
          body: JSON.stringify(body),
        }
      );

      return {
        entity,
        total: result.total || result.data.length,
        data: result.data,
      };
    } else {
      // Use GET /explore/tables/{table} for simple queries
      const queryParams: Record<string, string | number | boolean | undefined> = {
        limit: limit as number,
        offset: offset as number,
      };

      const result = await fetchApi<{ table: string; total: number; data: Record<string, unknown>[] }>(
        `/explore/tables/${entity}`,
        { params: queryParams }
      );

      return {
        entity: result.table,
        total: result.total,
        data: result.data,
      };
    }
  },
};

// Additional types
export interface SyncLog {
  id: number;
  source: string;
  entity_type: string | null;
  sync_type: string;
  status: string;
  records_fetched: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  duration_seconds: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface ChurnRiskCustomer {
  id: number;
  name: string;
  email: string | null;
  account_number: string | null;
  risk_score: number;
  risk_factors: string[];
  last_payment_date: string | null;
  days_since_payment: number;
  outstanding_amount: number;
  open_tickets: number;
}

// Revenue Quality Types
export interface DSOTrend {
  trend: Array<{
    year: number;
    month: number;
    period: string;
    dso: number;
    invoiced: number;
    outstanding: number;
  }>;
  current_dso: number;
  average_dso: number;
}

export interface TerritoryRevenue {
  territory: string;
  customer_count: number;
  mrr: number;
}

export interface CohortData {
  cohorts: Array<{
    cohort: string;
    total_customers: number;
    active: number;
    churned: number;
    retention_rate: number;
  }>;
  summary: {
    avg_retention: number;
    total_cohorts: number;
  };
}

// Collections Types
export interface AgingBucket {
  count: number;
  amount: number;
}

export interface AgingBySegment {
  by_segment: Record<string, {
    current: AgingBucket;
    '1_30_days': AgingBucket;
    '31_60_days': AgingBucket;
    '61_90_days': AgingBucket;
    over_90_days: AgingBucket;
    total: AgingBucket;
  }>;
  total_outstanding: number;
}

export interface CreditNoteSummary {
  trend: Array<{
    year: number;
    month: number;
    period: string;
    count: number;
    total: number;
  }>;
  by_status: Record<string, { count: number; total: number }>;
  total_issued: number;
}

// Sales Pipeline Types
export interface SalesPipeline {
  quotations: {
    by_status: Record<string, { count: number; value: number }>;
    total: number;
    total_value: number;
  };
  orders: {
    by_status: Record<string, { count: number; value: number }>;
    total: number;
    total_value: number;
  };
  conversion: {
    quotation_to_order_rate: number;
    orders_completed: number;
  };
}

export interface QuotationTrend {
  year: number;
  month: number;
  period: string;
  total: number;
  converted: number;
  lost: number;
  value: number;
  conversion_rate: number;
}

// Support/SLA Types
export interface SLAAttainment {
  period_days: number;
  total_tickets: number;
  sla_attainment: {
    met: number;
    breached: number;
    rate: number;
  };
  avg_response_hours: number;
  avg_resolution_hours: number;
  by_priority: Record<string, number>;
}

export interface AgentProductivity {
  employee_id: number;
  name: string;
  department: string | null;
  total_tickets: number;
  resolved: number;
  closed: number;
  resolution_rate: number;
  avg_resolution_hours: number;
}

export interface TicketsByType {
  by_type: Array<{
    type: string;
    count: number;
    resolved: number;
    resolution_rate: number;
  }>;
  total: number;
}

// Network Types
export interface NetworkDeviceStatus {
  summary: {
    total: number;
    up: number;
    down: number;
    unknown: number;
    uptime_percent: number;
  };
  by_location: Array<{
    location_id: number;
    total: number;
    up: number;
    down: number;
  }>;
}

export interface IPUtilization {
  networks: Array<{
    network: string;
    title: string | null;
    type: string | null;
    capacity: number;
    used: number;
    available: number;
    utilization_percent: number;
  }>;
  summary: {
    total_networks: number;
    total_capacity: number;
    total_used: number;
    total_available: number;
    overall_utilization: number;
  };
}

// Expense Types
export interface ExpenseByCategory {
  by_category: Array<{
    category: string;
    count: number;
    total: number;
  }>;
  total_expenses: number;
}

export interface ExpenseByCostCenter {
  by_cost_center: Array<{
    cost_center: string;
    count: number;
    total: number;
  }>;
  total_expenses: number;
}

export interface ExpenseTrend {
  year: number;
  month: number;
  period: string;
  count: number;
  total: number;
}

export interface VendorSpend {
  vendors: Array<{
    supplier: string | null;
    supplier_name: string | null;
    invoice_count: number;
    total_spend: number;
    outstanding: number;
  }>;
  total_spend: number;
}

// People/Ops Types
export interface TicketsPerEmployee {
  by_employee: Array<{
    employee_id: number;
    name: string;
    department: string | null;
    total_tickets: number;
    resolved: number;
    open: number;
  }>;
  summary: {
    total_tickets: number;
    active_employees: number;
    avg_tickets_per_employee: number;
  };
}

export interface DepartmentMetrics {
  department: string;
  employee_count: number;
  ticket_count: number;
  expense_total: number;
}

// Deep Insights Types
export interface FieldCompleteness {
  field: string;
  filled: number;
  total: number;
  percent: number;
  sample_values?: string[];
}

export interface EntityCompleteness {
  total: number;
  fields: FieldCompleteness[];
  overall_score: number;
}

export interface DataCompletenessResponse {
  entities: Record<string, EntityCompleteness>;
  recommendations: string[];
  priority_fields: string[];
}

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

export interface EntityRelationship {
  entity: string;
  total: number;
  linked: number;
  orphaned: number;
  link_rate: number;
}

export interface RelationshipMapResponse {
  entities: EntityRelationship[];
  data_quality: {
    overall_linkage_rate: number;
    strong_links: string[];
    weak_links: string[];
    missing_links: string[];
  };
  recommendations: string[];
}

export interface FinancialInsightsResponse {
  revenue: {
    total_mrr: number;
    total_invoiced: number;
    total_paid: number;
    total_outstanding: number;
    collection_rate: number;
    by_currency: Record<string, number>;
  };
  aging: {
    current: number;
    past_30: number;
    past_60: number;
    past_90: number;
    over_90: number;
  };
  payment_methods: Record<string, { count: number; amount: number }>;
  trends: {
    avg_payment_delay: number;
    avg_invoice_amount: number;
  };
  recommendations: string[];
}

export interface OperationalInsightsResponse {
  support: {
    total_tickets: number;
    open_tickets: number;
    avg_resolution_hours: number;
    resolution_rate: number;
    by_priority: Record<string, number>;
    by_type: Record<string, number>;
  };
  conversations: {
    total: number;
    open: number;
    resolved: number;
    by_channel: Record<string, number>;
  };
  employees: {
    total: number;
    by_department: Record<string, number>;
    avg_tickets_per_agent: number;
  };
  recommendations: string[];
}

export interface Anomaly {
  type: string;
  severity: string;
  entity: string;
  description: string;
  affected_count: number;
  sample_ids?: number[];
}

export interface AnomaliesResponse {
  anomalies: Anomaly[];
  summary: {
    total_issues: number;
    critical: number;
    warning: number;
    info: number;
  };
  recommendations: string[];
}

export interface DataAvailabilityResponse {
  available: {
    entity: string;
    total: number;
    fields: string[];
    date_range?: {
      earliest: string | null;
      latest: string | null;
    };
  }[];
  gaps: {
    entity: string;
    issue: string;
    recommendation: string;
  }[];
  summary: {
    total_entities: number;
    total_records: number;
    well_populated: number;
    needs_attention: number;
  };
}

// Finance Domain Types
export interface FinanceDashboard {
  currency: string;
  revenue: {
    mrr: number;
    arr: number;
    active_subscriptions?: number;
  };
  collections: {
    last_30_days: number;
    invoiced_30_days: number;
    collection_rate: number;
  };
  outstanding: {
    total: number;
    overdue: number;
  };
  metrics: {
    dso: number;
  };
  invoices_by_status?: Record<string, { count: number; total: number }>;
  period?: {
    start: string;
    end: string;
  };
}

export interface FinanceInvoice {
  id: number;
  invoice_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  total_amount: number;
  amount_paid: number;
  balance: number;
  status: string;
  invoice_date: string | null;
  due_date: string | null;
  days_overdue: number;
  currency: string | null;
  source?: string | null;
  credit_note_id?: number | null;
  credit_note_number?: string | null;
}

export interface FinanceInvoiceDetail extends FinanceInvoice {
  description?: string | null;
  tax_amount?: number;
  paid_date?: string | null;
  category?: string | null;
  credit_note_id?: number | null;
  credit_note_number?: string | null;
  external_ids?: {
    splynx_id?: number | null;
    erpnext_id?: number | null;
  };
  customer?: {
    id: number | null;
    name: string | null;
    email: string | null;
  };
  payments?: Array<{
    id: number;
    amount: number;
    payment_date: string | null;
    payment_method: string | null;
    status: string;
  }>;
}

export interface FinanceInvoiceListResponse {
  data: FinanceInvoice[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinancePayment {
  id: number;
  receipt_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  amount: number;
  currency: string | null;
  payment_method: string | null;
  status: string;
  payment_date: string | null;
  transaction_reference: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
  invoice_id?: number | null;
  source?: string | null;
}

export interface FinancePaymentDetail extends FinancePayment {
  external_ids?: {
    splynx_id?: number | null;
    erpnext_id?: number | null;
  };
  customer?: {
    id: number | null;
    name: string | null;
    email: string | null;
  };
  invoice?: {
    id: number | null;
    invoice_number: string | null;
    total_amount: number | null;
  };
}

export interface FinancePaymentListResponse {
  data: FinancePayment[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinanceCreditNote {
  id: number;
  credit_note_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  amount: number;
  currency: string | null;
  status: string;
  date: string | null;
  reason: string | null;
  invoice_id?: number | null;
  source?: string | null;
}

export interface FinanceCreditNoteDetail extends FinanceCreditNote {
  external_ids?: { splynx_id?: number | null };
  customer?: { id: number | null; name: string | null; email: string | null };
  invoice?: { id: number | null; invoice_number: string | null; total_amount?: number | null };
  description?: string | null;
}

export interface FinanceCreditNoteListResponse {
  data: FinanceCreditNote[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinanceRevenueTrend {
  period: string;
  year: number;
  month: number;
  revenue: number;
  payment_count: number;
}

export interface FinanceCollectionsAnalytics {
  by_method: Array<{
    method: string;
    count: number;
    total: number;
  }>;
  payment_timing: {
    early: number;
    on_time: number;
    late: number;
    total: number;
  };
  daily_totals?: Array<{
    date: string;
    total: number;
    paid?: number;
  }>;
}

export interface FinanceAgingAnalytics {
  currency?: string;
  buckets: Array<{
    bucket: string;
    count: number;
    outstanding: number;
  }>;
  summary: {
    total_outstanding: number;
    at_risk: number;
    at_risk_percent: number;
  };
}

export interface FinanceByCurrencyAnalytics {
  by_currency: Array<{
    currency: string;
    mrr: number;
    arr: number;
    subscription_count: number;
    outstanding: number;
  }>;
}

export interface FinancePaymentBehavior {
  summary: {
    customers_with_payments: number;
    customers_with_overdue: number;
    avg_late_payment_delay_days: number;
  };
  recommendations: Array<{
    priority: string;
    issue: string;
    action: string;
  }>;
}

export interface FinanceForecast {
  currency: string;
  current: {
    mrr: number;
    arr: number;
  };
  activity_30d: {
    new_subscriptions: number;
  };
  projections: {
    month_1: number;
    month_2: number;
    month_3: number;
    quarter_total: number;
  };
  notes?: string | null;
}

// Accounting Domain Types
export interface AccountingAccount {
  id: number;
  account_number: string;
  account_name: string;
  account_type: string;
  parent_account?: string | null;
  balance: number;
  is_group: boolean;
  root_type?: string | null;
  report_type?: string | null;
  currency?: string | null;
}

export interface AccountingChartOfAccounts {
  accounts: AccountingAccount[];
  tree: AccountingAccountTreeNode[];
  total_accounts: number;
}

export interface AccountingAccountTreeNode {
  account_number: string;
  account_name: string;
  account_type: string;
  balance: number;
  is_group: boolean;
  children: AccountingAccountTreeNode[];
}

export interface AccountingTrialBalance {
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  difference: number;
  accounts: Array<{
    account_number: string;
    account_name: string;
    account_type: string;
    debit: number;
    credit: number;
    balance: number;
  }>;
  as_of_date?: string;
}

export interface AccountingBalanceSheet {
  assets: {
    current_assets: Array<{ account: string; balance: number }>;
    fixed_assets: Array<{ account: string; balance: number }>;
    other_assets: Array<{ account: string; balance: number }>;
    total: number;
  };
  liabilities: {
    current_liabilities: Array<{ account: string; balance: number }>;
    long_term_liabilities: Array<{ account: string; balance: number }>;
    total: number;
  };
  equity: {
    items: Array<{ account: string; balance: number }>;
    retained_earnings: number;
    total: number;
  };
  total_liabilities_equity: number;
  is_balanced: boolean;
  as_of_date?: string;
}

export interface AccountingIncomeStatement {
  revenue: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  cost_of_goods_sold: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  gross_profit: number;
  operating_expenses: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  operating_income: number;
  other_income: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  other_expenses: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  net_income: number;
  period?: { start: string; end: string };
}

export interface AccountingGeneralLedgerEntry {
  id: number;
  posting_date: string;
  account: string;
  account_name?: string;
  debit: number;
  credit: number;
  balance: number;
  voucher_type?: string | null;
  voucher_no?: string | null;
  party_type?: string | null;
  party?: string | null;
  remarks?: string | null;
  cost_center?: string | null;
}

export interface AccountingGeneralLedgerResponse {
  entries: AccountingGeneralLedgerEntry[];
  total: number;
  limit: number;
  offset: number;
  summary?: {
    total_debit: number;
    total_credit: number;
    opening_balance?: number;
    closing_balance?: number;
  };
}

export interface AccountingCashFlow {
  operating_activities: {
    items: Array<{ description: string; amount: number }>;
    net: number;
  };
  investing_activities: {
    items: Array<{ description: string; amount: number }>;
    net: number;
  };
  financing_activities: {
    items: Array<{ description: string; amount: number }>;
    net: number;
  };
  net_change_in_cash: number;
  opening_cash: number;
  closing_cash: number;
  period?: { start: string; end: string };
}

export interface AccountingPayable {
  supplier_id: number;
  supplier_name: string;
  total_payable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  invoice_count: number;
  oldest_invoice_date?: string | null;
  currency?: string | null;
}

export interface AccountingPayableResponse {
  total_payable: number;
  total_invoices: number;
  aging: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  suppliers: AccountingPayable[];
  currency?: string;
}

export interface AccountingReceivable {
  customer_id: number;
  customer_name: string;
  total_receivable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  invoice_count: number;
  oldest_invoice_date?: string | null;
  currency?: string | null;
}

export interface AccountingReceivableResponse {
  total_receivable: number;
  total_invoices: number;
  aging: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  customers: AccountingReceivable[];
  currency?: string;
}

export interface AccountingJournalEntry {
  id: number;
  voucher_type: string;
  voucher_no: string;
  posting_date: string;
  total_debit: number;
  total_credit: number;
  user_remark?: string | null;
  is_opening?: boolean;
  docstatus?: number;
  entries?: Array<{
    account: string;
    debit: number;
    credit: number;
    party_type?: string | null;
    party?: string | null;
    cost_center?: string | null;
  }>;
}

export interface AccountingJournalEntryListResponse {
  entries: AccountingJournalEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface AccountingSupplier {
  id: number;
  name: string;
  supplier_name?: string;
  supplier_type?: string | null;
  supplier_group?: string | null;
  country?: string | null;
  default_currency?: string | null;
  payment_terms?: string | null;
  tax_id?: string | null;
  email?: string | null;
  phone?: string | null;
  is_internal?: boolean;
  disabled?: boolean;
  total_outstanding?: number;
  total_invoices?: number;
}

export interface AccountingSupplierListResponse {
  suppliers: AccountingSupplier[];
  total: number;
  limit: number;
  offset: number;
}

export interface AccountingBankAccount {
  id: number;
  name: string;
  account_name: string;
  bank?: string | null;
  account_number?: string | null;
  account_type?: string | null;
  currency?: string | null;
  balance?: number;
  is_default?: boolean;
  is_company_account?: boolean;
  last_integration_date?: string | null;
}

export interface AccountingBankAccountListResponse {
  accounts: AccountingBankAccount[];
  total: number;
}

export interface AccountingFiscalYear {
  id: number;
  name: string;
  year_start_date: string;
  year_end_date: string;
  is_closed: boolean;
  disabled: boolean;
}

export interface AccountingFiscalYearListResponse {
  fiscal_years: AccountingFiscalYear[];
  current_fiscal_year?: AccountingFiscalYear;
  total: number;
}

export interface AccountingCostCenter {
  id: number;
  name: string;
  cost_center_name: string;
  parent_cost_center?: string | null;
  is_group: boolean;
  disabled: boolean;
  company?: string | null;
}

export interface AccountingCostCenterListResponse {
  cost_centers: AccountingCostCenter[];
  total: number;
}

export interface AccountingDashboard {
  summary: {
    total_assets: number;
    total_liabilities: number;
    total_equity: number;
    net_income_ytd: number;
    cash_balance: number;
    accounts_receivable: number;
    accounts_payable: number;
  };
  kpis: {
    current_ratio?: number;
    quick_ratio?: number;
    debt_to_equity?: number;
    gross_margin?: number;
    net_margin?: number;
  };
  recent_transactions?: AccountingGeneralLedgerEntry[];
  period?: { start: string; end: string };
  currency?: string;
}

export { ApiError };
