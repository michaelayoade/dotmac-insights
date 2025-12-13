const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export function buildApiUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      url.searchParams.append(key, String(value));
    });
  }
  return url.toString();
}

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
  [key: string]: any;
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

// Projects
export type ProjectStatus = 'open' | 'completed' | 'cancelled' | 'on_hold';
export type ProjectPriority = 'low' | 'medium' | 'high';

export interface ProjectUser {
  user?: string | null;
  full_name?: string | null;
  email?: string | null;
  project_status?: string | null;
  view_attachments?: boolean;
  welcome_email_sent?: boolean;
  idx?: number;
}

export interface ProjectListItem {
  id: number;
  erpnext_id: string | null;
  project_name: string;
  project_type: string | null;
  status: ProjectStatus;
  priority: ProjectPriority | null;
  department: string | null;
  customer_id: number | null;
  percent_complete: number | null;
  expected_start_date: string | null;
  expected_end_date: string | null;
  estimated_costing: number | null;
  total_billed_amount: number | null;
  is_overdue: boolean;
  task_count: number | null;
  created_at: string | null;
  write_back_status?: string | null;
}

export interface ProjectListResponse {
  total: number;
  limit: number;
  offset: number;
  data: ProjectListItem[];
}

export interface ProjectDetail extends ProjectListItem {
  company?: string | null;
  cost_center?: string | null;
  project_manager_id?: number | null;
  project_manager?: string | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  customer?: Record<string, any> | null;
  users?: ProjectUser[];
  tasks?: any[];
  task_stats?: Record<string, any>;
  expenses?: any[];
  time_tracking?: Record<string, any>;
}

export interface ProjectPayload {
  project_name?: string;
  project_type?: string | null;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  department?: string | null;
  company?: string | null;
  cost_center?: string | null;
  customer_id?: number | null;
  project_manager_id?: number | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete?: number | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  estimated_costing?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  total_billed_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  expected_start_date?: string | null;
  expected_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  users?: ProjectUser[];
}

export interface ProjectsDashboard {
  cards: Record<string, number>;
  metrics?: Record<string, any>;
}

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
  by_priority: Array<{ priority: string; open: number; total: number; sla_breach_pct: number }>;
  by_type: Array<{ ticket_type: string; open: number; total: number; avg_resolution_hours: number }>;
  volume_trend: Array<{ period: string; opened: number; resolved: number; closed: number; sla_attainment_pct: number }>;
  resolution_trend: Array<{ period: string; p50_hours: number; p75_hours: number; p90_hours: number }>;
  backlog_age: Array<{ bucket: string; count: number }>;
  agent_performance: Array<{ agent: string; open: number; resolved: number; avg_resolution_hours: number; sla_attainment_pct: number; csat_avg?: number }>;
  team_performance: Array<{ team: string; open: number; resolved: number; sla_attainment_pct: number; avg_resolution_hours: number }>;
  csat: {
    avg_score: number;
    response_rate_pct: number;
    trend: Array<{ period: string; avg_score: number; responses: number }>;
  };
  top_drivers: Array<{ label: string; count: number; share_pct: number }>;
  overdue_detail: Array<{ id: number; ticket_number: string | null; priority: string | null; assigned_to: string | null; resolution_by: string | null; age_hours: number }>;
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
  metrics: { avg_resolution_hours: number; overdue_tickets: number; unassigned_tickets: number };
  conversations: { total: number; open: number; resolved: number };
}

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

  getSupportTicketDetail: (id: number | string) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}`),

  createSupportTicket: (body: SupportTicketPayload) =>
    fetchApi<{ id: number; ticket_number: string }>(`/support/tickets`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTicket: (id: number | string, body: Partial<SupportTicketPayload>) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTicket: (id: number | string) =>
    fetchApi<void>(`/support/tickets/${id}`, {
      method: 'DELETE',
    }),

  getSupportAgents: (team_id?: number, domain?: string) =>
    fetchApi<{ agents: SupportAgent[] }>(`/support/agents`, { params: { team_id, domain } }),

  createSupportAgent: (body: SupportAgentPayload) =>
    fetchApi<SupportAgent>('/support/agents', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportAgent: (id: number, body: SupportAgentPayload) =>
    fetchApi<SupportAgent>(`/support/agents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportAgent: (id: number) =>
    fetchApi<void>(`/support/agents/${id}`, { method: 'DELETE' }),

  getSupportTeams: (domain?: string) =>
    fetchApi<{ teams: SupportTeam[] }>(`/support/teams`, { params: domain ? { domain } : undefined }),

  createSupportTeam: (body: SupportTeamPayload & { team_name: string }) =>
    fetchApi<SupportTeam>(`/support/teams`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTeam: (id: number, body: SupportTeamPayload) =>
    fetchApi<SupportTeam>(`/support/teams/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTeam: (id: number) =>
    fetchApi<void>(`/support/teams/${id}`, { method: 'DELETE' }),

  addSupportTeamMember: (teamId: number, body: SupportTeamMemberPayload) =>
    fetchApi<SupportTeamMember>(`/support/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteSupportTeamMember: (teamId: number, memberId: number) =>
    fetchApi<void>(`/support/teams/${teamId}/members/${memberId}`, { method: 'DELETE' }),

  createSupportTicketComment: (ticketId: number | string, body: SupportTicketCommentPayload) =>
    fetchApi<SupportTicketComment>(`/support/tickets/${ticketId}/comments`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTicketComment: (ticketId: number | string, commentId: number, body: SupportTicketCommentPayload) =>
    fetchApi<SupportTicketComment>(`/support/tickets/${ticketId}/comments/${commentId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTicketComment: (ticketId: number | string, commentId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/comments/${commentId}`, { method: 'DELETE' }),

  createSupportTicketActivity: (ticketId: number | string, body: SupportTicketActivityPayload) =>
    fetchApi<SupportTicketActivity>(`/support/tickets/${ticketId}/activities`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTicketActivity: (ticketId: number | string, activityId: number, body: SupportTicketActivityPayload) =>
    fetchApi<SupportTicketActivity>(`/support/tickets/${ticketId}/activities/${activityId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTicketActivity: (ticketId: number | string, activityId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/activities/${activityId}`, { method: 'DELETE' }),

  createSupportTicketCommunication: (ticketId: number | string, body: SupportTicketCommunicationPayload) =>
    fetchApi<SupportTicketCommunication>(`/support/tickets/${ticketId}/communications`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTicketCommunication: (ticketId: number | string, communicationId: number, body: SupportTicketCommunicationPayload) =>
    fetchApi<SupportTicketCommunication>(`/support/tickets/${ticketId}/communications/${communicationId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTicketCommunication: (ticketId: number | string, communicationId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/communications/${communicationId}`, { method: 'DELETE' }),

  createSupportTicketDependency: (ticketId: number | string, body: SupportTicketDependencyPayload) =>
    fetchApi<SupportTicketDependency>(`/support/tickets/${ticketId}/depends-on`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupportTicketDependency: (ticketId: number | string, dependencyId: number, body: SupportTicketDependencyPayload) =>
    fetchApi<SupportTicketDependency>(`/support/tickets/${ticketId}/depends-on/${dependencyId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupportTicketDependency: (ticketId: number | string, dependencyId: number) =>
    fetchApi<void>(`/support/tickets/${ticketId}/depends-on/${dependencyId}`, { method: 'DELETE' }),

  assignSupportTicket: (ticketId: number | string, body: SupportTicketAssigneePayload) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${ticketId}/assignee`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  overrideSupportTicketSla: (ticketId: number | string, body: SupportTicketSlaPayload) =>
    fetchApi<SupportTicketDetail>(`/support/tickets/${ticketId}/sla`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getSupportTickets: (params?: {
    start?: string;
    end?: string;
    team_id?: number;
    agent?: string;
    ticket_type?: string;
    priority?: 'low' | 'medium' | 'high' | 'urgent';
    status?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<SupportTicketListResponse>('/support/tickets', { params }),

  getSupportOverview: (params?: SupportOverviewRequest) =>
    fetchApi<SupportOverviewResponse>('/support/analytics/overview', { params }),

  getSupportDashboard: () =>
    fetchApi<SupportDashboardResponse>('/support/dashboard'),

  // Projects
  getProjects: (params?: {
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
  }) => fetchApi<ProjectListResponse>('/projects', { params }),

  getProjectDetail: (id: number) => fetchApi<ProjectDetail>(`/projects/${id}`),

  createProject: (body: ProjectPayload & { project_name: string }) =>
    fetchApi<ProjectDetail>('/projects', { method: 'POST', body: JSON.stringify(body) }),

  updateProject: (id: number, body: ProjectPayload) =>
    fetchApi<ProjectDetail>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteProject: (id: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/${id}`, { method: 'DELETE' }),

  getProjectsDashboard: () => fetchApi<ProjectsDashboard>('/projects/dashboard'),

  getProjectsStatusTrend: (months = 12) => fetchApi<any>(`/projects/analytics/status-trend`, { params: { months } }),
  getProjectsTaskDistribution: () => fetchApi<any>('/projects/analytics/task-distribution'),
  getProjectsPerformance: () => fetchApi<any>('/projects/analytics/project-performance'),
  getProjectsDepartmentSummary: (months = 12) =>
    fetchApi<any>('/projects/analytics/department-summary', { params: { months } }),

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

  createCustomer: (payload: CustomerWritePayload) =>
    fetchApi<CustomerDetail>('/customers', { method: 'POST', body: JSON.stringify(payload) }),

  updateCustomer: (id: number, payload: CustomerWritePayload) =>
    fetchApi<CustomerDetail>(`/customers/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteCustomer: (id: number, soft = true) =>
    fetchApi<void>(`/customers/${id}?soft=${soft ? 'true' : 'false'}`, { method: 'DELETE' }),

  // Customer subscriptions
  createCustomerSubscription: (payload: CustomerSubscriptionPayload) =>
    fetchApi('/customers/subscriptions', { method: 'POST', body: JSON.stringify(payload) }),

  updateCustomerSubscription: (id: number, payload: CustomerSubscriptionPayload) =>
    fetchApi(`/customers/subscriptions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteCustomerSubscription: (id: number, soft = true) =>
    fetchApi<void>(`/customers/subscriptions/${id}?soft=${soft ? 'true' : 'false'}`, { method: 'DELETE' }),

  // Customer invoices
  createCustomerInvoice: (payload: CustomerInvoicePayload) =>
    fetchApi('/customers/invoices', { method: 'POST', body: JSON.stringify(payload) }),

  updateCustomerInvoice: (id: number, payload: CustomerInvoicePayload) =>
    fetchApi(`/customers/invoices/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteCustomerInvoice: (id: number, soft = true) =>
    fetchApi<void>(`/customers/invoices/${id}?soft=${soft ? 'true' : 'false'}`, { method: 'DELETE' }),

  // Customer payments
  createCustomerPayment: (payload: CustomerPaymentPayload) =>
    fetchApi('/customers/payments', { method: 'POST', body: JSON.stringify(payload) }),

  updateCustomerPayment: (id: number, payload: CustomerPaymentPayload) =>
    fetchApi(`/customers/payments/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteCustomerPayment: (id: number, soft = true) =>
    fetchApi<void>(`/customers/payments/${id}?soft=${soft ? 'true' : 'false'}`, { method: 'DELETE' }),

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

// Finance Domain (Sales/AR)
  getFinanceDashboard: (currency?: string) =>
    fetchApi<FinanceDashboard>('/v1/sales/dashboard', {
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
    sort_by?: 'invoice_date' | 'total_amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) =>
    fetchApi<FinanceInvoiceListResponse>('/v1/sales/invoices', { params }),

  createFinanceInvoice: (body: FinanceInvoicePayload) =>
    fetchApi<FinanceInvoiceDetail>('/v1/sales/invoices', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinanceInvoice: (id: number, body: FinanceInvoicePayload) =>
    fetchApi<FinanceInvoiceDetail>(`/v1/sales/invoices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFinanceInvoice: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/invoices/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

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
    sort_by?: 'payment_date' | 'amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) =>
    fetchApi<FinancePaymentListResponse>('/v1/sales/payments', { params }),

  createFinancePayment: (body: FinancePaymentPayload) =>
    fetchApi<FinancePaymentDetail>('/v1/sales/payments', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinancePayment: (id: number, body: FinancePaymentPayload) =>
    fetchApi<FinancePaymentDetail>(`/v1/sales/payments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFinancePayment: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/payments/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getFinanceCreditNotes: (params?: {
    customer_id?: number;
    invoice_id?: number;
    start_date?: string;
    end_date?: string;
    currency?: string;
    search?: string;
    status?: string;
    min_amount?: number;
    max_amount?: number;
    sort_by?: 'issue_date' | 'amount' | 'status';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) =>
    fetchApi<FinanceCreditNoteListResponse>('/v1/sales/credit-notes', { params }),

  createFinanceCreditNote: (body: FinanceCreditNotePayload) =>
    fetchApi<FinanceCreditNoteDetail>('/v1/sales/credit-notes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinanceCreditNote: (id: number, body: FinanceCreditNotePayload) =>
    fetchApi<FinanceCreditNoteDetail>(`/v1/sales/credit-notes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFinanceCreditNote: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/credit-notes/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // Accounting admin & controls
  getAccountingFiscalPeriods: () =>
    fetchApi<any[]>('/accounting/fiscal-periods'),

  createAccountingFiscalPeriods: (body: { fiscal_year: string; frequency?: string }) =>
    fetchApi<any>('/accounting/fiscal-periods', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  closeFiscalPeriod: (id: number | string) =>
    fetchApi<any>(`/accounting/fiscal-periods/${id}/close`, { method: 'PATCH' }),

  reopenFiscalPeriod: (id: number | string) =>
    fetchApi<any>(`/accounting/fiscal-periods/${id}/reopen`, { method: 'PATCH' }),

  generateClosingEntries: (id: number | string) =>
    fetchApi<any>(`/accounting/fiscal-periods/${id}/closing-entries`, { method: 'POST' }),

  getAccountingWorkflows: () =>
    fetchApi<any[]>('/accounting/workflows'),

  createAccountingWorkflow: (body: any) =>
    fetchApi<any>('/accounting/workflows', { method: 'POST', body: JSON.stringify(body) }),

  updateAccountingWorkflow: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/workflows/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAccountingWorkflow: (id: number | string) =>
    fetchApi<void>(`/accounting/workflows/${id}`, { method: 'DELETE' }),

  addAccountingWorkflowStep: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/workflows/${id}/steps`, { method: 'POST', body: JSON.stringify(body) }),

  getAccountingPendingApprovals: () =>
    fetchApi<any[]>('/accounting/approvals/pending'),

  getAccountingApprovalStatus: (doctype: string, documentId: number | string) =>
    fetchApi<any>(`/accounting/approvals/${doctype}/${documentId}`),

  submitJournalEntry: (id: number | string) =>
    fetchApi<any>(`/accounting/journal-entries/${id}/submit`, { method: 'POST' }),

  approveJournalEntry: (id: number | string) =>
    fetchApi<any>(`/accounting/journal-entries/${id}/approve`, { method: 'POST' }),

  rejectJournalEntry: (id: number | string) =>
    fetchApi<any>(`/accounting/journal-entries/${id}/reject`, { method: 'POST' }),

  postJournalEntry: (id: number | string) =>
    fetchApi<any>(`/accounting/journal-entries/${id}/post`, { method: 'POST' }),

  createJournalEntry: (body: any) =>
    fetchApi<any>('/accounting/journal-entries', { method: 'POST', body: JSON.stringify(body) }),

  updateJournalEntry: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/journal-entries/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteJournalEntry: (id: number | string) =>
    fetchApi<void>(`/accounting/journal-entries/${id}`, { method: 'DELETE' }),

  createAccount: (body: any) =>
    fetchApi<any>('/accounting/accounts', { method: 'POST', body: JSON.stringify(body) }),

  updateAccount: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAccount: (id: number | string) =>
    fetchApi<void>(`/accounting/accounts/${id}`, { method: 'DELETE' }),

  createAccountingSupplier: (body: any) =>
    fetchApi<any>('/accounting/suppliers', { method: 'POST', body: JSON.stringify(body) }),

  updateAccountingSupplier: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAccountingSupplier: (id: number | string) =>
    fetchApi<void>(`/accounting/suppliers/${id}`, { method: 'DELETE' }),

  getExchangeRates: () =>
    fetchApi<any[]>('/accounting/exchange-rates'),

  getLatestExchangeRates: () =>
    fetchApi<any>('/accounting/exchange-rates/latest'),

  createExchangeRate: (body: any) =>
    fetchApi<any>('/accounting/exchange-rates', { method: 'POST', body: JSON.stringify(body) }),

  updateExchangeRate: (id: number | string, body: any) =>
    fetchApi<any>(`/accounting/exchange-rates/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  getAccountingControls: () =>
    fetchApi<any>('/accounting/controls'),

  updateAccountingControls: (body: any) =>
    fetchApi<any>('/accounting/controls', { method: 'PATCH', body: JSON.stringify(body) }),

  getAuditLog: (params?: { doctype?: string; document_id?: number | string; limit?: number; offset?: number }) =>
    fetchApi<any>('/accounting/audit-log', { params }),

  getAuditLogForDocument: (doctype: string, documentId: number | string) =>
    fetchApi<any>(`/accounting/audit-log/${doctype}/${documentId}`),

  previewFxRevaluation: (body: any) =>
    fetchApi<any>('/accounting/revaluation/preview', { method: 'POST', body: JSON.stringify(body) }),

  applyFxRevaluation: (body: any) =>
    fetchApi<any>('/accounting/revaluation/apply', { method: 'POST', body: JSON.stringify(body) }),

  getFxRevaluationHistory: (params?: { limit?: number; offset?: number }) =>
    fetchApi<any>('/accounting/revaluation/history', { params }),

  getTrialBalanceExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/trial-balance/export', params),

  getBalanceSheetExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/balance-sheet/export', params),

  getIncomeStatementExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/income-statement/export', params),

  getGeneralLedgerExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/general-ledger/export', params),

  getReceivablesAgingExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/receivables-aging/export', params),

  getPayablesAgingExportUrl: (params?: Record<string, string | number | boolean | undefined>) =>
    buildApiUrl('/accounting/payables-aging/export', params),

  // Inventory valuation & landed cost
  getInventoryValuation: (params?: Record<string, string | number | boolean | undefined>) =>
    fetchApi<any>('/inventory/valuation-report', { params }),

  getInventoryValuationDetail: (itemCode: string, params?: Record<string, string | number | boolean | undefined>) =>
    fetchApi<any>(`/inventory/valuation-report/${itemCode}`, { params }),

  createLandedCostVoucher: (body: any) =>
    fetchApi<any>('/inventory/landed-cost-vouchers', { method: 'POST', body: JSON.stringify(body) }),

  getLandedCostVouchers: (params?: Record<string, string | number | boolean | undefined>) =>
    fetchApi<any>('/inventory/landed-cost-vouchers', { params }),

  getLandedCostVoucherDetail: (id: number | string) =>
    fetchApi<any>(`/inventory/landed-cost-vouchers/${id}`),

  updateLandedCostVoucher: (id: number | string, body: any) =>
    fetchApi<any>(`/inventory/landed-cost-vouchers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  submitLandedCostVoucher: (id: number | string) =>
    fetchApi<any>(`/inventory/landed-cost-vouchers/${id}/submit`, { method: 'PATCH' }),

  // Notifications
  getNotifications: (params?: { limit?: number; offset?: number; unread_only?: boolean }) =>
    fetchApi<any>('/v1/notifications', { params }),

  markNotificationRead: (id: number | string) =>
    fetchApi<void>(`/v1/notifications/${id}/read`, { method: 'POST' }),

  markAllNotificationsRead: () =>
    fetchApi<void>('/v1/notifications/read-all', { method: 'POST' }),

  getNotificationPreferences: () =>
    fetchApi<any>('/v1/notifications/preferences'),

  updateNotificationPreferences: (body: any) =>
    fetchApi<any>('/v1/notifications/preferences', { method: 'PATCH', body: JSON.stringify(body) }),

  listWebhooks: () =>
    fetchApi<any[]>('/v1/notifications/webhooks'),

  createWebhook: (body: any) =>
    fetchApi<any>('/v1/notifications/webhooks', { method: 'POST', body: JSON.stringify(body) }),

  getWebhook: (id: number | string) =>
    fetchApi<any>(`/v1/notifications/webhooks/${id}`),

  updateWebhook: (id: number | string, body: any) =>
    fetchApi<any>(`/v1/notifications/webhooks/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteWebhook: (id: number | string) =>
    fetchApi<void>(`/v1/notifications/webhooks/${id}`, { method: 'DELETE' }),

  testWebhook: (id: number | string) =>
    fetchApi<any>(`/v1/notifications/webhooks/${id}/test`, { method: 'POST' }),

  getWebhookDeliveries: (id: number | string, params?: { status?: string; limit?: number; offset?: number }) =>
    fetchApi<any>(`/v1/notifications/webhooks/${id}/deliveries`, { params }),

  retryWebhookDelivery: (deliveryId: number | string) =>
    fetchApi<any>(`/v1/notifications/webhook-deliveries/${deliveryId}/retry`, { method: 'POST' }),

  emitNotificationEvent: (body: any) =>
    fetchApi<any>('/v1/notifications/events', { method: 'POST', body: JSON.stringify(body) }),

  // Cache metadata / export status
  getAccountingCacheMetadata: () =>
    fetchApi<any>('/accounting/cache-metadata'),

  getReportsCacheMetadata: () =>
    fetchApi<any>('/reports/cache-metadata'),

  getAccountingExportStatus: () =>
    fetchApi<any>('/accounting/exports/status'),

  getFinanceRevenueTrend: (params?: { start_date?: string; end_date?: string; interval?: 'month' | 'week'; currency?: string }) =>
    fetchApi<FinanceRevenueTrend[]>('/v1/sales/analytics/revenue-trend', {
      params
    }),

  getFinanceCollections: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<FinanceCollectionsAnalytics>('/v1/sales/analytics/collections', {
      params
    }),

  getFinanceAging: (params?: { currency?: string }) =>
    fetchApi<FinanceAgingAnalytics>('/v1/sales/aging', { params }),

  getFinanceRevenueBySegment: () =>
    fetchApi<FinanceByCurrencyAnalytics>('/v1/sales/analytics/by-currency'),

  getFinancePaymentBehavior: (params?: { currency?: string }) =>
    fetchApi<FinancePaymentBehavior>('/v1/sales/insights/payment-behavior', { params }),

  getFinanceForecasts: (currency?: string) =>
    fetchApi<FinanceForecast>('/v1/sales/insights/forecasts', { params: { currency } }),

  getFinanceInvoiceDetail: (id: number, currency?: string) =>
    fetchApi<FinanceInvoiceDetail>(`/v1/sales/invoices/${id}`, { params: { currency } }),

  getFinancePaymentDetail: (id: number, currency?: string) =>
    fetchApi<FinancePaymentDetail>(`/v1/sales/payments/${id}`, { params: { currency } }),

  getFinanceCreditNoteDetail: (id: number, currency?: string) =>
    fetchApi<FinanceCreditNoteDetail>(`/v1/sales/credit-notes/${id}`, { params: { currency } }),

  // AR credit management & dunning
  getAccountingCustomerCreditStatus: (id: number) =>
    fetchApi<any>(`/accounting/customers/${id}/credit-status`),

  updateAccountingCustomerCreditLimit: (id: number, body: any) =>
    fetchApi<any>(`/accounting/customers/${id}/credit-limit`, { method: 'PATCH', body: JSON.stringify(body) }),

  updateAccountingCustomerCreditHold: (id: number, body: any) =>
    fetchApi<any>(`/accounting/customers/${id}/credit-hold`, { method: 'PATCH', body: JSON.stringify(body) }),

  writeOffAccountingInvoice: (id: number, body: any) =>
    fetchApi<any>(`/accounting/invoices/${id}/write-off`, { method: 'POST', body: JSON.stringify(body) }),

  waiveAccountingInvoice: (id: number, body: any) =>
    fetchApi<any>(`/accounting/invoices/${id}/waive`, { method: 'POST', body: JSON.stringify(body) }),

  getAccountingInvoiceDunningHistory: (id: number) =>
    fetchApi<any>(`/accounting/invoices/${id}/dunning-history`),

  sendAccountingDunning: (body: any) =>
    fetchApi<any>('/accounting/dunning/send', { method: 'POST', body: JSON.stringify(body) }),

  getAccountingDunningQueue: () =>
    fetchApi<any>('/accounting/dunning/queue'),

  getAccountingReceivablesAgingEnhanced: (params?: Record<string, string | number | boolean | undefined>) =>
    fetchApi<any>('/accounting/receivables-aging-enhanced', { params }),

  getFinanceOrders: (params?: {
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
  }) => fetchApi<FinanceOrderListResponse>('/v1/sales/orders', { params }),

  createFinanceOrder: (body: FinanceOrderPayload) =>
    fetchApi<FinanceOrder>(`/v1/sales/orders`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinanceOrder: (id: number, body: FinanceOrderPayload) =>
    fetchApi<FinanceOrder>(`/v1/sales/orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFinanceOrder: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/orders/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getFinanceOrderDetail: (id: number, currency?: string) =>
    fetchApi<FinanceOrder>(`/v1/sales/orders/${id}`, { params: { currency } }),

  getFinanceQuotations: (params?: {
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
  }) => fetchApi<FinanceQuotationListResponse>('/v1/sales/quotations', { params }),

  createFinanceQuotation: (body: FinanceQuotationPayload) =>
    fetchApi<FinanceQuotation>(`/v1/sales/quotations`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinanceQuotation: (id: number, body: FinanceQuotationPayload) =>
    fetchApi<FinanceQuotation>(`/v1/sales/quotations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFinanceQuotation: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/quotations/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getFinanceQuotationDetail: (id: number, currency?: string) =>
    fetchApi<FinanceQuotation>(`/v1/sales/quotations/${id}`, { params: { currency } }),

  getFinanceCustomers: (params?: { search?: string; status?: string; customer_type?: string; limit?: number; offset?: number }) =>
    fetchApi<CustomerListResponse>('/v1/sales/customers', { params }),

  createFinanceCustomer: (body: FinanceCustomerPayload) =>
    fetchApi<CustomerDetail>(`/v1/sales/customers`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateFinanceCustomer: (id: number, body: FinanceCustomerPayload) =>
    fetchApi<CustomerDetail>(`/v1/sales/customers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getFinanceCustomerDetail: (id: number) =>
    fetchApi<CustomerDetail>(`/v1/sales/customers/${id}`),

  // Accounting Domain
  getAccountingDashboard: (currency?: string) =>
    fetchApi<AccountingDashboard>('/v1/accounting/dashboard', { params: { currency } }),

  getAccountingChartOfAccounts: (accountType?: string, params?: { root_type?: string; is_group?: boolean; include_disabled?: boolean; search?: string; limit?: number; offset?: number }) =>
    fetchApi<AccountingChartOfAccounts>('/v1/accounting/accounts', {
      params: { account_type: accountType, ...params }
    }),

  getAccountingAccountDetail: (id: number, params?: { include_ledger?: boolean; start_date?: string; end_date?: string; limit?: number }) =>
    fetchApi<AccountingAccountDetail>(`/v1/accounting/accounts/${id}`, { params }),

  getAccountingTrialBalance: (params?: { fiscal_year?: string; start_date?: string; end_date?: string; currency?: string; drill?: boolean }) =>
    fetchApi<AccountingTrialBalance>('/v1/accounting/trial-balance', { params }),

  getAccountingBalanceSheet: (params?: { fiscal_year?: string; as_of_date?: string; currency?: string; common_size?: boolean }) =>
    fetchApi<AccountingBalanceSheet>('/v1/accounting/balance-sheet', { params }),

  getAccountingIncomeStatement: (params?: {
    fiscal_year?: string;
    start_date?: string;
    end_date?: string;
    currency?: string;
    compare_start?: string;
    compare_end?: string;
    show_ytd?: boolean;
    common_size?: boolean;
    basis?: string;
  }) =>
    fetchApi<AccountingIncomeStatement>('/v1/accounting/income-statement', { params }),

  getAccountingTaxCategories: () =>
    fetchApi<{ tax_categories: AccountingTaxCategory[] }>('/v1/accounting/tax-categories'),

  getAccountingSalesTaxTemplates: () =>
    fetchApi<{ sales_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/sales-tax-templates'),

  getAccountingPurchaseTaxTemplates: () =>
    fetchApi<{ purchase_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/purchase-tax-templates'),

  getAccountingItemTaxTemplates: () =>
    fetchApi<{ item_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/item-tax-templates'),

  getAccountingTaxRules: () =>
    fetchApi<{ tax_rules: AccountingTaxTemplate[] }>('/v1/accounting/tax-rules'),

  getAccountingTaxPayable: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<AccountingTaxSummary>('/v1/accounting/tax-payable', { params }),

  getAccountingTaxReceivable: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<AccountingTaxSummary>('/v1/accounting/tax-receivable', { params }),

  getAccountingGeneralLedger: (params?: {
    account?: string;
    party?: string;
    start_date?: string;
    end_date?: string;
    cost_center?: string;
    fiscal_year?: string;
    currency?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingGeneralLedgerResponse>('/v1/accounting/general-ledger', { params }),

  getAccountingCashFlow: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<AccountingCashFlow>('/v1/accounting/cash-flow', { params }),

  getAccountingPayables: (params?: {
    supplier_id?: number;
    currency?: string;
    as_of_date?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingPayableResponse>('/v1/accounting/accounts-payable', { params }),

  getAccountingReceivables: (params?: {
    customer_id?: number;
    currency?: string;
    as_of_date?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingReceivableResponse>('/v1/accounting/accounts-receivable', { params }),

  getAccountingReceivablesOutstanding: (params?: { currency?: string; top?: number }) =>
    fetchApi<AccountingOutstandingSummary>('/v1/accounting/receivables-outstanding', { params }),

  getAccountingPayablesOutstanding: (params?: { currency?: string; top?: number }) =>
    fetchApi<AccountingOutstandingSummary>('/v1/accounting/payables-outstanding', { params }),

  getAccountingJournalEntries: (params?: {
    voucher_type?: string;
    party?: string;
    cost_center?: string;
    start_date?: string;
    end_date?: string;
    currency?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingJournalEntryListResponse>('/v1/accounting/journal-entries', { params }),

  getAccountingJournalEntryDetail: (id: number) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}`),

  getAccountingSuppliers: (params?: {
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AccountingSupplierListResponse>('/v1/accounting/suppliers', { params }),

  getAccountingBankAccounts: () =>
    fetchApi<AccountingBankAccountListResponse>('/v1/accounting/bank-accounts'),

  getAccountingFiscalYears: () =>
    fetchApi<AccountingFiscalYearListResponse>('/v1/accounting/fiscal-years'),

  getAccountingCostCenters: () =>
    fetchApi<AccountingCostCenterListResponse>('/v1/accounting/cost-centers'),

  getAccountingPurchaseInvoices: (params?: {
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
  }) => fetchApi<AccountingPurchaseInvoiceListResponse>('/v1/accounting/purchase-invoices', { params }),

  getAccountingPurchaseInvoiceDetail: (id: number, currency?: string) =>
    fetchApi<AccountingPurchaseInvoiceDetail>(`/v1/accounting/purchase-invoices/${id}`, { params: { currency } }),

  getAccountingBankTransactions: (params?: {
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
  }) => fetchApi<AccountingBankTransactionListResponse>('/v1/accounting/bank-transactions', { params }),

  getAccountingBankTransactionDetail: (id: number | string) =>
    fetchApi<AccountingBankTransactionDetail>(`/v1/accounting/bank-transactions/${id}`),

  // Purchasing Domain
  getPurchasingDashboard: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<PurchasingDashboard>('/v1/purchasing/dashboard', { params }),

  getPurchasingBills: (params?: {
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
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingBillListResponse>('/v1/purchasing/bills', { params: { ...params, ...paging } });
  },

  getPurchasingBillDetail: (id: number) =>
    fetchApi<PurchasingBillDetail>(`/v1/purchasing/bills/${id}`),

  createPurchasingBill: (body: PurchasingBillPayload) =>
    fetchApi<PurchasingBillDetail>('/v1/purchasing/bills', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePurchasingBill: (id: number, body: PurchasingBillPayload) =>
    fetchApi<PurchasingBillDetail>(`/v1/purchasing/bills/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deletePurchasingBill: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/bills/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getPurchasingPayments: (params?: {
    supplier?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    currency?: string;
    limit?: number;
    offset?: number;
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingPaymentListResponse>('/v1/purchasing/payments', { params: { ...params, ...paging } });
  },

  getPurchasingPaymentDetail: (id: number) =>
    fetchApi<PurchasingPaymentDetail>(`/v1/purchasing/payments/${id}`),

  getPurchasingOrders: (params?: {
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
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingOrderListResponse>('/v1/purchasing/orders', { params: { ...params, ...paging } });
  },

  getPurchasingOrderDetail: (id: number) =>
    fetchApi<PurchasingOrderDetail>(`/v1/purchasing/orders/${id}`),

  createPurchasingOrder: (body: PurchasingOrderPayload) =>
    fetchApi<PurchasingOrderDetail>('/v1/purchasing/orders', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePurchasingOrder: (id: number, body: PurchasingOrderPayload) =>
    fetchApi<PurchasingOrderDetail>(`/v1/purchasing/orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deletePurchasingOrder: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/orders/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getPurchasingDebitNotes: (params?: {
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
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingDebitNoteListResponse>('/v1/purchasing/debit-notes', { params: { ...params, ...paging } });
  },

  getPurchasingDebitNoteDetail: (id: number) =>
    fetchApi<PurchasingDebitNoteDetail>(`/v1/purchasing/debit-notes/${id}`),

  createPurchasingDebitNote: (body: PurchasingDebitNotePayload) =>
    fetchApi<PurchasingDebitNoteDetail>('/v1/purchasing/debit-notes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePurchasingDebitNote: (id: number, body: PurchasingDebitNotePayload) =>
    fetchApi<PurchasingDebitNoteDetail>(`/v1/purchasing/debit-notes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deletePurchasingDebitNote: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/debit-notes/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getPurchasingSuppliers: (params?: {
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
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingSupplierListResponse>('/v1/purchasing/suppliers', { params: { ...params, ...paging } });
  },

  getPurchasingSupplierGroups: () =>
    fetchApi<PurchasingSupplierGroupsResponse>('/v1/purchasing/suppliers/groups'),

  getPurchasingSupplierDetail: (id: number) =>
    fetchApi<PurchasingSupplierDetail>(`/v1/purchasing/suppliers/${id}`),

  getPurchasingExpenses: (params?: {
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
  }) => {
    const paging =
      params && params.limit !== undefined
        ? {
            page_size: params.limit,
            page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
          }
        : {};
    return fetchApi<PurchasingExpenseListResponse>('/v1/purchasing/expenses', { params: { ...params, ...paging } });
  },

  getPurchasingExpenseTypes: (params?: {
    start_date?: string;
    end_date?: string;
  }) => fetchApi<PurchasingExpenseTypesResponse>('/v1/purchasing/expenses/types', { params }),

  getPurchasingExpenseDetail: (id: number) =>
    fetchApi<PurchasingExpenseDetail>(`/v1/purchasing/expenses/${id}`),

  createPurchasingExpense: (body: PurchasingExpensePayload) =>
    fetchApi<PurchasingExpenseDetail>('/v1/purchasing/expenses', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePurchasingExpense: (id: number, body: PurchasingExpensePayload) =>
    fetchApi<PurchasingExpenseDetail>(`/v1/purchasing/expenses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deletePurchasingExpense: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/expenses/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  getPurchasingAging: (params?: {
    as_of_date?: string;
    supplier?: string;
    currency?: string;
  }) => fetchApi<PurchasingAgingResponse>('/v1/purchasing/aging', { params }),

  getPurchasingBySupplier: (params?: {
    start_date?: string;
    end_date?: string;
    limit?: number;
    currency?: string;
  }) => fetchApi<PurchasingBySupplierResponse>('/v1/purchasing/analytics/by-supplier', { params }),

  getPurchasingByCostCenter: (params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }) => fetchApi<PurchasingByCostCenterResponse>('/v1/purchasing/analytics/by-cost-center', { params }),

  getPurchasingExpenseTrend: (params?: {
    months?: number;
    interval?: 'month' | 'week';
    currency?: string;
  }) => fetchApi<PurchasingExpenseTrendResponse>('/v1/purchasing/analytics/expense-trend', { params }),

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

  // Inventory mutations
  createInventoryItem: (body: InventoryItemPayload) =>
    fetchApi(`/v1/inventory/items`, { method: 'POST', body: JSON.stringify(body) }),

  updateInventoryItem: (id: number | string, body: Partial<InventoryItemPayload>) =>
    fetchApi(`/v1/inventory/items/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteInventoryItem: (id: number | string) =>
    fetchApi(`/v1/inventory/items/${id}?soft=true`, { method: 'DELETE' }),

  createInventoryWarehouse: (body: InventoryWarehousePayload) =>
    fetchApi(`/v1/inventory/warehouses`, { method: 'POST', body: JSON.stringify(body) }),

  updateInventoryWarehouse: (id: number | string, body: Partial<InventoryWarehousePayload>) =>
    fetchApi(`/v1/inventory/warehouses/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteInventoryWarehouse: (id: number | string) =>
    fetchApi(`/v1/inventory/warehouses/${id}?soft=true`, { method: 'DELETE' }),

  createInventoryStockEntry: (body: InventoryStockEntryPayload) =>
    fetchApi(`/v1/inventory/stock-entries`, { method: 'POST', body: JSON.stringify(body) }),

  // HR Domain
  getHrLeaveTypes: (params?: { search?: string; is_lwp?: boolean; is_carry_forward?: boolean; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrLeaveType>>('/hr/leave-types', { params }),

  getHrLeaveTypeDetail: (id: number | string) =>
    fetchApi<HrLeaveType>(`/hr/leave-types/${id}`),

  getHrHolidayLists: (params?: { search?: string; company?: string; from_date?: string; to_date?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrHolidayList>>('/hr/holiday-lists', { params }),

  getHrHolidayListDetail: (id: number | string) =>
    fetchApi<HrHolidayList>(`/hr/holiday-lists/${id}`),

  createHrHolidayList: (body: HrHolidayListPayload) =>
    fetchApi<HrHolidayList>('/hr/holiday-lists', { method: 'POST', body: JSON.stringify(body) }),

  updateHrHolidayList: (id: number | string, body: Partial<HrHolidayListPayload>) =>
    fetchApi<HrHolidayList>(`/hr/holiday-lists/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrHolidayList: (id: number | string) =>
    fetchApi<void>(`/hr/holiday-lists/${id}`, { method: 'DELETE' }),

  getHrLeavePolicies: (params?: { search?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrLeavePolicy>>('/hr/leave-policies', { params }),

  getHrLeavePolicyDetail: (id: number | string) =>
    fetchApi<HrLeavePolicy>(`/hr/leave-policies/${id}`),

  createHrLeavePolicy: (body: HrLeavePolicyPayload) =>
    fetchApi<HrLeavePolicy>('/hr/leave-policies', { method: 'POST', body: JSON.stringify(body) }),

  updateHrLeavePolicy: (id: number | string, body: Partial<HrLeavePolicyPayload>) =>
    fetchApi<HrLeavePolicy>(`/hr/leave-policies/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrLeavePolicy: (id: number | string) =>
    fetchApi<void>(`/hr/leave-policies/${id}`, { method: 'DELETE' }),

  getHrLeaveAllocations: (params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrLeaveAllocation>>('/hr/leave-allocations', { params }),

  getHrLeaveAllocationDetail: (id: number | string) =>
    fetchApi<HrLeaveAllocation>(`/hr/leave-allocations/${id}`),

  createHrLeaveAllocation: (body: HrLeaveAllocationPayload) =>
    fetchApi<HrLeaveAllocation>('/hr/leave-allocations', { method: 'POST', body: JSON.stringify(body) }),

  updateHrLeaveAllocation: (id: number | string, body: Partial<HrLeaveAllocationPayload>) =>
    fetchApi<HrLeaveAllocation>(`/hr/leave-allocations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrLeaveAllocation: (id: number | string) =>
    fetchApi<void>(`/hr/leave-allocations/${id}`, { method: 'DELETE' }),

  getHrLeaveApplications: (params?: { employee_id?: number; leave_type_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrLeaveApplication>>('/hr/leave-applications', { params }),

  getHrLeaveApplicationDetail: (id: number | string) =>
    fetchApi<HrLeaveApplication>(`/hr/leave-applications/${id}`),

  createHrLeaveApplication: (body: HrLeaveApplicationPayload) =>
    fetchApi<HrLeaveApplication>('/hr/leave-applications', { method: 'POST', body: JSON.stringify(body) }),

  updateHrLeaveApplication: (id: number | string, body: Partial<HrLeaveApplicationPayload>) =>
    fetchApi<HrLeaveApplication>(`/hr/leave-applications/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}`, { method: 'DELETE' }),

  bulkCreateHrLeaveAllocations: (body: { employee_ids: number[]; leave_policy_id: number; from_date: string; to_date: string; company?: string }) =>
    fetchApi<{ created: number; employee_ids: number[] }>('/hr/leave-allocations/bulk', { method: 'POST', body: JSON.stringify(body) }),

  approveHrLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/approve`, { method: 'POST' }),

  rejectHrLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/reject`, { method: 'POST' }),

  cancelHrLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/cancel`, { method: 'POST' }),

  bulkApproveHrLeaveApplications: (body: { application_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/leave-applications/bulk/approve', { method: 'POST', body: JSON.stringify(body) }),

  bulkRejectHrLeaveApplications: (body: { application_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/leave-applications/bulk/reject', { method: 'POST', body: JSON.stringify(body) }),

  getHrShiftTypes: (params?: { search?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrShiftType>>('/hr/shift-types', { params }),

  getHrShiftTypeDetail: (id: number | string) =>
    fetchApi<HrShiftType>(`/hr/shift-types/${id}`),

  getHrShiftAssignments: (params?: { employee_id?: number; shift_type_id?: number; start_date?: string; end_date?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrShiftAssignment>>('/hr/shift-assignments', { params }),

  getHrShiftAssignmentDetail: (id: number | string) =>
    fetchApi<HrShiftAssignment>(`/hr/shift-assignments/${id}`),

  createHrShiftAssignment: (body: HrShiftAssignmentPayload) =>
    fetchApi<HrShiftAssignment>('/hr/shift-assignments', { method: 'POST', body: JSON.stringify(body) }),

  updateHrShiftAssignment: (id: number | string, body: Partial<HrShiftAssignmentPayload>) =>
    fetchApi<HrShiftAssignment>(`/hr/shift-assignments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrShiftAssignment: (id: number | string) =>
    fetchApi<void>(`/hr/shift-assignments/${id}`, { method: 'DELETE' }),

  getHrAttendances: (params?: { employee_id?: number; status?: string; attendance_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAttendance>>('/hr/attendances', { params }),

  getHrAttendanceDetail: (id: number | string) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}`),

  createHrAttendance: (body: HrAttendancePayload) =>
    fetchApi<HrAttendance>('/hr/attendances', { method: 'POST', body: JSON.stringify(body) }),

  updateHrAttendance: (id: number | string, body: Partial<HrAttendancePayload>) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrAttendance: (id: number | string) =>
    fetchApi<void>(`/hr/attendances/${id}`, { method: 'DELETE' }),

  checkInHrAttendance: (id: number | string, body?: { latitude?: number; longitude?: number; device_info?: string }) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}/check-in`, { method: 'POST', body: JSON.stringify(body || {}) }),

  checkOutHrAttendance: (id: number | string, body?: { latitude?: number; longitude?: number }) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}/check-out`, { method: 'POST', body: JSON.stringify(body || {}) }),

  bulkMarkAttendance: (body: { employee_ids: (number | string)[]; attendance_date: string; status: string }) =>
    fetchApi<void>('/hr/attendances/bulk/mark', { method: 'POST', body: JSON.stringify(body) }),

  getHrAttendanceRequests: (params?: { employee_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAttendanceRequest>>('/hr/attendance-requests', { params }),

  getHrAttendanceRequestDetail: (id: number | string) =>
    fetchApi<HrAttendanceRequest>(`/hr/attendance-requests/${id}`),

  createHrAttendanceRequest: (body: HrAttendanceRequestPayload) =>
    fetchApi<HrAttendanceRequest>('/hr/attendance-requests', { method: 'POST', body: JSON.stringify(body) }),

  updateHrAttendanceRequest: (id: number | string, body: Partial<HrAttendanceRequestPayload>) =>
    fetchApi<HrAttendanceRequest>(`/hr/attendance-requests/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}`, { method: 'DELETE' }),

  approveHrAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}/approve`, { method: 'POST' }),

  rejectHrAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}/reject`, { method: 'POST' }),

  bulkApproveHrAttendanceRequests: (body: { request_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/attendance-requests/bulk/approve', { method: 'POST', body: JSON.stringify(body) }),

  bulkRejectHrAttendanceRequests: (body: { request_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/attendance-requests/bulk/reject', { method: 'POST', body: JSON.stringify(body) }),

  getHrJobOpenings: (params?: { status?: string; company?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrJobOpening>>('/hr/job-openings', { params }),

  getHrJobOpeningDetail: (id: number | string) =>
    fetchApi<HrJobOpening>(`/hr/job-openings/${id}`),

  createHrJobOpening: (body: HrJobOpeningPayload) =>
    fetchApi<HrJobOpening>('/hr/job-openings', { method: 'POST', body: JSON.stringify(body) }),

  updateHrJobOpening: (id: number | string, body: Partial<HrJobOpeningPayload>) =>
    fetchApi<HrJobOpening>(`/hr/job-openings/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrJobOpening: (id: number | string) =>
    fetchApi<void>(`/hr/job-openings/${id}`, { method: 'DELETE' }),

  getHrJobApplicants: (params?: { status?: string; job_title?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrJobApplicant>>('/hr/job-applicants', { params }),

  getHrJobApplicantDetail: (id: number | string) =>
    fetchApi<HrJobApplicant>(`/hr/job-applicants/${id}`),

  createHrJobApplicant: (body: HrJobApplicantPayload) =>
    fetchApi<HrJobApplicant>('/hr/job-applicants', { method: 'POST', body: JSON.stringify(body) }),

  updateHrJobApplicant: (id: number | string, body: Partial<HrJobApplicantPayload>) =>
    fetchApi<HrJobApplicant>(`/hr/job-applicants/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}`, { method: 'DELETE' }),

  screenHrJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}/screen`, { method: 'POST' }),

  scheduleInterviewForHrJobApplicant: (id: number | string, body: { interview_date: string; interviewer: string; location?: string; notes?: string }) =>
    fetchApi<void>(`/hr/job-applicants/${id}/schedule-interview`, { method: 'POST', body: JSON.stringify(body) }),

  makeOfferForHrJobApplicant: (id: number | string, body: { offer_id: number | string }) =>
    fetchApi<void>(`/hr/job-applicants/${id}/make-offer`, { method: 'POST', body: JSON.stringify(body) }),

  withdrawHrJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}/withdraw`, { method: 'POST' }),

  getHrJobOffers: (params?: { status?: string; company?: string; job_applicant?: string; offer_date_from?: string; offer_date_to?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrJobOffer>>('/hr/job-offers', { params }),

  getHrJobOfferDetail: (id: number | string) =>
    fetchApi<HrJobOffer>(`/hr/job-offers/${id}`),

  createHrJobOffer: (body: HrJobOfferPayload) =>
    fetchApi<HrJobOffer>('/hr/job-offers', { method: 'POST', body: JSON.stringify(body) }),

  updateHrJobOffer: (id: number | string, body: Partial<HrJobOfferPayload>) =>
    fetchApi<HrJobOffer>(`/hr/job-offers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}`, { method: 'DELETE' }),

  createHrInterview: (body: HrInterviewPayload) =>
    fetchApi<HrInterview>('/hr/interviews', { method: 'POST', body: JSON.stringify(body) }),

  updateHrInterview: (id: number | string, body: Partial<HrInterviewPayload>) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  completeHrInterview: (id: number | string, body: { feedback?: string; rating?: number; result?: string }) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}/complete`, { method: 'POST', body: JSON.stringify(body) }),

  cancelHrInterview: (id: number | string) =>
    fetchApi<void>(`/hr/interviews/${id}/cancel`, { method: 'POST' }),

  markNoShowHrInterview: (id: number | string) =>
    fetchApi<void>(`/hr/interviews/${id}/no-show`, { method: 'POST' }),

  sendHrJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/send`, { method: 'POST' }),

  voidHrJobOffer: (id: number | string, body: { void_reason: string; voided_at?: string }) =>
    fetchApi<void>(`/hr/job-offers/${id}/void`, { method: 'POST', body: JSON.stringify(body) }),

  acceptHrJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/accept`, { method: 'POST' }),

  rejectHrJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/reject`, { method: 'POST' }),

  bulkSendHrJobOffers: (body: { offer_ids: (number | string)[]; delivery_method?: string }) =>
    fetchApi<void>('/hr/job-offers/bulk/send', { method: 'POST', body: JSON.stringify(body) }),

  getHrInterviews: (params?: { job_applicant_id?: number; status?: string; interviewer?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrInterview>>('/hr/interviews', { params }),

  getHrInterviewDetail: (id: number | string) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}`),

  getHrSalaryComponents: (params?: { component_type?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryComponent>>('/hr/salary-components', { params }),

  getHrSalaryComponentDetail: (id: number | string) =>
    fetchApi<HrSalaryComponent>(`/hr/salary-components/${id}`),

  createHrSalaryComponent: (body: HrSalaryComponentPayload) =>
    fetchApi<HrSalaryComponent>('/hr/salary-components', { method: 'POST', body: JSON.stringify(body) }),

  updateHrSalaryComponent: (id: number | string, body: Partial<HrSalaryComponentPayload>) =>
    fetchApi<HrSalaryComponent>(`/hr/salary-components/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrSalaryComponent: (id: number | string) =>
    fetchApi<void>(`/hr/salary-components/${id}`, { method: 'DELETE' }),

  getHrSalaryStructures: (params?: { company?: string; is_active?: boolean; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryStructure>>('/hr/salary-structures', { params }),

  getHrSalaryStructureDetail: (id: number | string) =>
    fetchApi<HrSalaryStructure>(`/hr/salary-structures/${id}`),

  createHrSalaryStructure: (body: HrSalaryStructurePayload) =>
    fetchApi<HrSalaryStructure>('/hr/salary-structures', { method: 'POST', body: JSON.stringify(body) }),

  updateHrSalaryStructure: (id: number | string, body: Partial<HrSalaryStructurePayload>) =>
    fetchApi<HrSalaryStructure>(`/hr/salary-structures/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrSalaryStructure: (id: number | string) =>
    fetchApi<void>(`/hr/salary-structures/${id}`, { method: 'DELETE' }),

  getHrSalaryStructureAssignments: (params?: { employee_id?: number; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryStructureAssignment>>('/hr/salary-structure-assignments', { params }),

  getHrSalaryStructureAssignmentDetail: (id: number | string) =>
    fetchApi<HrSalaryStructureAssignment>(`/hr/salary-structure-assignments/${id}`),

  createHrSalaryStructureAssignment: (body: HrSalaryStructureAssignmentPayload) =>
    fetchApi<HrSalaryStructureAssignment>('/hr/salary-structure-assignments', { method: 'POST', body: JSON.stringify(body) }),

  updateHrSalaryStructureAssignment: (id: number | string, body: Partial<HrSalaryStructureAssignmentPayload>) =>
    fetchApi<HrSalaryStructureAssignment>(`/hr/salary-structure-assignments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrSalaryStructureAssignment: (id: number | string) =>
    fetchApi<void>(`/hr/salary-structure-assignments/${id}`, { method: 'DELETE' }),

  getHrPayrollEntries: (params?: { company?: string; posting_date_from?: string; posting_date_to?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrPayrollEntry>>('/hr/payroll-entries', { params }),

  getHrPayrollEntryDetail: (id: number | string) =>
    fetchApi<HrPayrollEntry>(`/hr/payroll-entries/${id}`),

  createHrPayrollEntry: (body: HrPayrollEntryPayload) =>
    fetchApi<HrPayrollEntry>('/hr/payroll-entries', { method: 'POST', body: JSON.stringify(body) }),

  updateHrPayrollEntry: (id: number | string, body: Partial<HrPayrollEntryPayload>) =>
    fetchApi<HrPayrollEntry>(`/hr/payroll-entries/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrPayrollEntry: (id: number | string) =>
    fetchApi<void>(`/hr/payroll-entries/${id}`, { method: 'DELETE' }),

  generateHrPayrollSlips: (id: number | string, body: { company: string; department?: string | null; branch?: string | null; designation?: string | null; start_date: string; end_date: string; regenerate?: boolean }) =>
    fetchApi<void>(`/hr/payroll-entries/${id}/generate-slips`, { method: 'POST', body: JSON.stringify(body) }),

  regenerateHrPayrollSlips: (id: number | string, body: { overwrite_drafts?: boolean }) =>
    fetchApi<void>(`/hr/payroll-entries/${id}/regenerate-slips`, { method: 'POST', body: JSON.stringify(body) }),

  getHrSalarySlips: (params?: { employee_id?: number; status?: string; start_date?: string; end_date?: string; company?: string; payroll_entry?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalarySlip>>('/hr/salary-slips', { params }),

  getHrSalarySlipDetail: (id: number | string) =>
    fetchApi<HrSalarySlip>(`/hr/salary-slips/${id}`),

  createHrSalarySlip: (body: HrSalarySlipPayload) =>
    fetchApi<HrSalarySlip>('/hr/salary-slips', { method: 'POST', body: JSON.stringify(body) }),

  updateHrSalarySlip: (id: number | string, body: Partial<HrSalarySlipPayload>) =>
    fetchApi<HrSalarySlip>(`/hr/salary-slips/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrSalarySlip: (id: number | string) =>
    fetchApi<void>(`/hr/salary-slips/${id}`, { method: 'DELETE' }),

  markHrSalarySlipPaid: (id: number | string, body: { payment_reference?: string; payment_mode?: string; paid_at?: string }) =>
    fetchApi<void>(`/hr/salary-slips/${id}/mark-paid`, { method: 'POST', body: JSON.stringify(body) }),

  voidHrSalarySlip: (id: number | string, body: { void_reason: string; voided_at?: string }) =>
    fetchApi<void>(`/hr/salary-slips/${id}/void`, { method: 'POST', body: JSON.stringify(body) }),

  exportHrSalarySlipRegister: async (params?: { employee_id?: number; status?: string; start_date?: string; end_date?: string; company?: string; payroll_entry?: string }) => {
    const url = buildApiUrl('/api/hr/salary-slips/register/export', params);
    const token = getAccessToken();
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(response.status, errorText || `HTTP ${response.status}`);
    }
    return response.blob();
  },

  getHrTrainingPrograms: (params?: { search?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrTrainingProgram>>('/hr/training-programs', { params }),

  getHrTrainingProgramDetail: (id: number | string) =>
    fetchApi<HrTrainingProgram>(`/hr/training-programs/${id}`),

  createHrTrainingProgram: (body: HrTrainingProgramPayload) =>
    fetchApi<HrTrainingProgram>('/hr/training-programs', { method: 'POST', body: JSON.stringify(body) }),

  updateHrTrainingProgram: (id: number | string, body: Partial<HrTrainingProgramPayload>) =>
    fetchApi<HrTrainingProgram>(`/hr/training-programs/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrTrainingProgram: (id: number | string) =>
    fetchApi<void>(`/hr/training-programs/${id}`, { method: 'DELETE' }),

  getHrTrainingEvents: (params?: { status?: string; company?: string; start_date?: string; end_date?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrTrainingEvent>>('/hr/training-events', { params }),

  getHrTrainingEventDetail: (id: number | string) =>
    fetchApi<HrTrainingEvent>(`/hr/training-events/${id}`),

  createHrTrainingEvent: (body: HrTrainingEventPayload) =>
    fetchApi<HrTrainingEvent>('/hr/training-events', { method: 'POST', body: JSON.stringify(body) }),

  updateHrTrainingEvent: (id: number | string, body: Partial<HrTrainingEventPayload>) =>
    fetchApi<HrTrainingEvent>(`/hr/training-events/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrTrainingEvent: (id: number | string) =>
    fetchApi<void>(`/hr/training-events/${id}`, { method: 'DELETE' }),

  enrollHrTrainingEvent: (id: number | string, body: { employee_ids: (number | string)[] }) =>
    fetchApi<void>(`/hr/training-events/${id}/enroll`, { method: 'POST', body: JSON.stringify(body) }),

  completeHrTrainingEvent: (id: number | string) =>
    fetchApi<void>(`/hr/training-events/${id}/complete`, { method: 'POST' }),

  getHrTrainingResults: (params?: { employee_id?: number; training_event?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrTrainingResult>>('/hr/training-results', { params }),

  getHrTrainingResultDetail: (id: number | string) =>
    fetchApi<HrTrainingResult>(`/hr/training-results/${id}`),

  createHrTrainingResult: (body: HrTrainingResultPayload) =>
    fetchApi<HrTrainingResult>('/hr/training-results', { method: 'POST', body: JSON.stringify(body) }),

  updateHrTrainingResult: (id: number | string, body: Partial<HrTrainingResultPayload>) =>
    fetchApi<HrTrainingResult>(`/hr/training-results/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrTrainingResult: (id: number | string) =>
    fetchApi<void>(`/hr/training-results/${id}`, { method: 'DELETE' }),

  getHrAppraisalTemplates: (params?: { company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAppraisalTemplate>>('/hr/appraisal-templates', { params }),

  getHrAppraisalTemplateDetail: (id: number | string) =>
    fetchApi<HrAppraisalTemplate>(`/hr/appraisal-templates/${id}`),

  createHrAppraisalTemplate: (body: HrAppraisalTemplatePayload) =>
    fetchApi<HrAppraisalTemplate>('/hr/appraisal-templates', { method: 'POST', body: JSON.stringify(body) }),

  updateHrAppraisalTemplate: (id: number | string, body: Partial<HrAppraisalTemplatePayload>) =>
    fetchApi<HrAppraisalTemplate>(`/hr/appraisal-templates/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrAppraisalTemplate: (id: number | string) =>
    fetchApi<void>(`/hr/appraisal-templates/${id}`, { method: 'DELETE' }),

  getHrAppraisals: (params?: { employee_id?: number; status?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAppraisal>>('/hr/appraisals', { params }),

  getHrAppraisalDetail: (id: number | string) =>
    fetchApi<HrAppraisal>(`/hr/appraisals/${id}`),

  createHrAppraisal: (body: HrAppraisalPayload) =>
    fetchApi<HrAppraisal>('/hr/appraisals', { method: 'POST', body: JSON.stringify(body) }),

  updateHrAppraisal: (id: number | string, body: Partial<HrAppraisalPayload>) =>
    fetchApi<HrAppraisal>(`/hr/appraisals/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}`, { method: 'DELETE' }),

  submitHrAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/submit`, { method: 'POST' }),

  reviewHrAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/review`, { method: 'POST' }),

  closeHrAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/close`, { method: 'POST' }),

  getHrEmployeeOnboardings: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeOnboarding>>('/hr/employee-onboardings', { params }),

  getHrEmployeeOnboardingDetail: (id: number | string) =>
    fetchApi<HrEmployeeOnboarding>(`/hr/employee-onboardings/${id}`),

  createHrEmployeeOnboarding: (body: HrEmployeeOnboardingPayload) =>
    fetchApi<HrEmployeeOnboarding>('/hr/employee-onboardings', { method: 'POST', body: JSON.stringify(body) }),

  updateHrEmployeeOnboarding: (id: number | string, body: Partial<HrEmployeeOnboardingPayload>) =>
    fetchApi<HrEmployeeOnboarding>(`/hr/employee-onboardings/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrEmployeeOnboarding: (id: number | string) =>
    fetchApi<void>(`/hr/employee-onboardings/${id}`, { method: 'DELETE' }),

  getHrEmployeeSeparations: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeSeparation>>('/hr/employee-separations', { params }),

  getHrEmployeeSeparationDetail: (id: number | string) =>
    fetchApi<HrEmployeeSeparation>(`/hr/employee-separations/${id}`),

  createHrEmployeeSeparation: (body: HrEmployeeSeparationPayload) =>
    fetchApi<HrEmployeeSeparation>('/hr/employee-separations', { method: 'POST', body: JSON.stringify(body) }),

  updateHrEmployeeSeparation: (id: number | string, body: Partial<HrEmployeeSeparationPayload>) =>
    fetchApi<HrEmployeeSeparation>(`/hr/employee-separations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrEmployeeSeparation: (id: number | string) =>
    fetchApi<void>(`/hr/employee-separations/${id}`, { method: 'DELETE' }),

  getHrEmployeePromotions: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeePromotion>>('/hr/employee-promotions', { params }),

  getHrEmployeePromotionDetail: (id: number | string) =>
    fetchApi<HrEmployeePromotion>(`/hr/employee-promotions/${id}`),

  createHrEmployeePromotion: (body: HrEmployeePromotionPayload) =>
    fetchApi<HrEmployeePromotion>('/hr/employee-promotions', { method: 'POST', body: JSON.stringify(body) }),

  updateHrEmployeePromotion: (id: number | string, body: Partial<HrEmployeePromotionPayload>) =>
    fetchApi<HrEmployeePromotion>(`/hr/employee-promotions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrEmployeePromotion: (id: number | string) =>
    fetchApi<void>(`/hr/employee-promotions/${id}`, { method: 'DELETE' }),

  getHrEmployeeTransfers: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeTransfer>>('/hr/employee-transfers', { params }),

  getHrEmployeeTransferDetail: (id: number | string) =>
    fetchApi<HrEmployeeTransfer>(`/hr/employee-transfers/${id}`),

  // HR Analytics
  getHrAnalyticsOverview: (params?: { company?: string }) =>
    fetchApi<HrAnalyticsOverview>('/hr/analytics/overview', { params }),

  getHrAnalyticsLeaveTrend: (params?: { company?: string; months?: number }) =>
    fetchApi<HrLeaveTrendPoint[]>('/hr/analytics/leave-trend', { params }),

  getHrAnalyticsAttendanceTrend: (params?: { company?: string; days?: number }) =>
    fetchApi<HrAttendanceTrendPoint[]>('/hr/analytics/attendance-trend', { params }),

  getHrAnalyticsPayrollSummary: (params?: { company?: string; department?: string; start_date?: string; end_date?: string; status?: string }) =>
    fetchApi<HrPayrollSummary>('/hr/analytics/payroll-summary', { params }),

  getHrAnalyticsPayrollTrend: (params?: { company?: string; department?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrPayrollTrendPoint[]>('/hr/analytics/payroll-trend', { params }),

  getHrAnalyticsPayrollComponents: (params?: { component_type?: string; company?: string; start_date?: string; end_date?: string; limit?: number }) =>
    fetchApi<HrPayrollComponentBreakdown[]>('/hr/analytics/payroll-components', { params }),

  getHrAnalyticsRecruitmentFunnel: (params?: { company?: string; job_title?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrRecruitmentFunnel>('/hr/analytics/recruitment-funnel', { params }),

  getHrAnalyticsAppraisalStatus: (params?: { company?: string; department?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrAppraisalStatusBreakdown>('/hr/analytics/appraisal-status', { params }),

  getHrAnalyticsLifecycleEvents: (params?: { company?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrLifecycleEventsBreakdown>('/hr/analytics/lifecycle-events', { params }),

  createHrEmployeeTransfer: (body: HrEmployeeTransferPayload) =>
    fetchApi<HrEmployeeTransfer>('/hr/employee-transfers', { method: 'POST', body: JSON.stringify(body) }),

  updateHrEmployeeTransfer: (id: number | string, body: Partial<HrEmployeeTransferPayload>) =>
    fetchApi<HrEmployeeTransfer>(`/hr/employee-transfers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHrEmployeeTransfer: (id: number | string) =>
    fetchApi<void>(`/hr/employee-transfers/${id}`, { method: 'DELETE' }),

  // Reports Domain
  getReportsRevenueSummary: () =>
    fetchApi<ReportsRevenueSummary>('/v1/reports/revenue/summary'),

  getReportsRevenueTrend: () =>
    fetchApi<ReportsRevenueTrendPoint[]>('/v1/reports/revenue/trend'),

  getReportsRevenueByCustomer: () =>
    fetchApi<ReportsRevenueByCustomer[]>('/v1/reports/revenue/by-customer'),

  getReportsRevenueByProduct: () =>
    fetchApi<ReportsRevenueByProduct[]>('/v1/reports/revenue/by-product'),

  getReportsExpensesSummary: () =>
    fetchApi<ReportsExpensesSummary>('/v1/reports/expenses/summary'),

  getReportsExpensesTrend: () =>
    fetchApi<ReportsExpenseTrendPoint[]>('/v1/reports/expenses/trend'),

  getReportsExpensesByCategory: () =>
    fetchApi<ReportsExpenseByCategory[]>('/v1/reports/expenses/by-category'),

  getReportsExpensesByVendor: () =>
    fetchApi<ReportsExpenseByVendor[]>('/v1/reports/expenses/by-vendor'),

  getReportsProfitabilityMargins: () =>
    fetchApi<ReportsProfitabilityMargins>('/v1/reports/profitability/margins'),

  getReportsProfitabilityTrend: () =>
    fetchApi<ReportsProfitabilityTrendPoint[]>('/v1/reports/profitability/trend'),

  getReportsProfitabilityBySegment: () =>
    fetchApi<ReportsProfitabilityBySegment[]>('/v1/reports/profitability/by-segment'),

  getReportsCashPositionSummary: () =>
    fetchApi<ReportsCashPositionSummary>('/v1/reports/cash-position/summary'),

  getReportsCashPositionForecast: () =>
    fetchApi<ReportsCashPositionForecastPoint[]>('/v1/reports/cash-position/forecast'),

  getReportsCashPositionRunway: () =>
    fetchApi<ReportsCashPositionRunway>('/v1/reports/cash-position/runway'),
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
  description?: string | null;
  amount?: number | null;
  tax_amount?: number | null;
  total_amount: number;
  amount_paid: number;
  balance: number | null;
  status: string;
  invoice_date: string | null;
  due_date: string | null;
  paid_date?: string | null;
  days_overdue?: number | null;
  category?: string | null;
  currency: string | null;
  source?: string | null;
  external_ids?: { splynx_id?: string | null; erpnext_id?: string | null };
  write_back_status?: string | null;
}

export interface FinanceInvoiceDetail extends FinanceInvoice {
  customer?: { id?: number | null; name?: string | null; email?: string | null };
  items?: Array<{
    id?: number | string;
    item_code?: string | null;
    item_name?: string | null;
    description?: string | null;
    qty?: number;
    stock_qty?: number;
    uom?: string | null;
    stock_uom?: string | null;
    conversion_factor?: number;
    rate?: number;
    price_list_rate?: number;
    discount_percentage?: number;
    discount_amount?: number;
    amount?: number;
    net_amount?: number;
    warehouse?: string | null;
    income_account?: string | null;
    expense_account?: string | null;
    cost_center?: string | null;
    sales_order?: string | null;
    delivery_note?: string | null;
    idx?: number;
  }>;
  payments?: Array<{
    id: number;
    amount: number;
    payment_method?: string | null;
    status: string;
    payment_date: string | null;
    currency?: string | null;
  }>;
  credit_notes?: Array<{
    id: number;
    amount: number;
    status: string;
    issue_date: string | null;
  }>;
}

export interface FinanceInvoiceListResponse {
  invoices: FinanceInvoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceInvoicePayload {
  invoice_number?: string | null;
  customer_id?: number | null;
  description?: string | null;
  amount?: number | null;
  tax_amount?: number | null;
  amount_paid?: number | null;
  currency?: string | null;
  status?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  paid_date?: string | null;
  category?: string | null;
  total_amount?: number | null; // fallback until backend fully aligns
  balance?: number | null;
  line_items?: Array<{
    description?: string | null;
    quantity?: number;
    unit_price?: number;
    tax_rate?: number;
  }>;
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
  external_ids?: { splynx_id?: string | null; erpnext_id?: string | null };
  write_back_status?: string | null;
}

export interface FinancePaymentDetail extends FinancePayment {
  customer?: { id?: number | null; name?: string | null; email?: string | null };
  invoice?: {
    id: number | null;
    invoice_number: string | null;
    total_amount?: number | null;
  };
  references?: Array<{
    id?: number;
    reference_doctype?: string | null;
    reference_name?: string | null;
    total_amount?: number | null;
    outstanding_amount?: number | null;
    allocated_amount?: number | null;
    exchange_rate?: number | null;
    exchange_gain_loss?: number | null;
    due_date?: string | null;
    idx?: number;
  }>;
}

export interface FinancePaymentListResponse {
  payments: FinancePayment[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinancePaymentPayload {
  customer_id: number | null;
  invoice_id?: number | null;
  receipt_number?: string | null;
  amount: number;
  currency?: string | null;
  payment_method?: string | null;
  status?: string;
  payment_date?: string | null;
  transaction_reference?: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
}

export interface FinanceCreditNote {
  id: number;
  credit_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  amount: number;
  currency: string | null;
  status: string;
  issue_date: string | null;
  applied_date?: string | null;
  description: string | null;
  invoice_id?: number | null;
  source?: string | null;
  write_back_status?: string | null;
}

export interface FinanceCreditNoteDetail extends FinanceCreditNote {
  invoice?: { id: number | null; invoice_number: string | null; total_amount?: number | null };
}

export interface FinanceCreditNoteListResponse {
  credit_notes: FinanceCreditNote[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceCreditNotePayload {
  credit_number?: string | null;
  customer_id?: number | null;
  invoice_id?: number | null;
  description?: string | null;
  amount?: number | null;
  currency?: string | null;
  status?: string | null;
  issue_date?: string | null;
  applied_date?: string | null;
}

export interface FinanceOrderItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number | null;
  stock_qty?: number | null;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number | null;
  rate?: number | null;
  price_list_rate?: number | null;
  discount_percentage?: number | null;
  discount_amount?: number | null;
  amount?: number | null;
  net_amount?: number | null;
  delivered_qty?: number | null;
  billed_amt?: number | null;
  warehouse?: string | null;
  delivery_date?: string | null;
  expense_account?: string | null;
  cost_center?: string | null;
  schedule_date?: string | null;
  idx?: number | null;
}

export interface FinanceOrder {
  id: number;
  order_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  status: string | null;
  total_amount: number;
  currency: string | null;
  order_date?: string | null;
  transaction_date?: string | null;
  delivery_date?: string | null;
  description?: string | null;
  total_qty?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  per_delivered?: number | null;
  per_billed?: number | null;
  billing_status?: string | null;
  delivery_status?: string | null;
  erpnext_id?: string | null;
  items?: FinanceOrderItem[];
  write_back_status?: string | null;
}

export interface FinanceOrderListResponse {
  orders: FinanceOrder[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceOrderPayload {
  customer_id?: number | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  currency?: string | null;
  transaction_date?: string | null;
  delivery_date?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  per_delivered?: number | null;
  per_billed?: number | null;
  billing_status?: string | null;
  delivery_status?: string | null;
  status?: string | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_number?: string | null; // retained for UI but optional
  description?: string | null;
}

export interface FinanceQuotationItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number | null;
  stock_qty?: number | null;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number | null;
  rate?: number | null;
  price_list_rate?: number | null;
  discount_percentage?: number | null;
  discount_amount?: number | null;
  amount?: number | null;
  net_amount?: number | null;
  idx?: number | null;
}

export interface FinanceQuotation {
  id: number;
  quotation_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  quotation_to?: string | null;
  party_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  status: string | null;
  total_amount: number;
  currency: string | null;
  quotation_date?: string | null;
  transaction_date?: string | null;
  valid_till?: string | null;
  description?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_lost_reason?: string | null;
  erpnext_id?: string | null;
  items?: FinanceQuotationItem[];
  write_back_status?: string | null;
}

export interface FinanceQuotationListResponse {
  quotations: FinanceQuotation[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceQuotationPayload {
  quotation_to?: string | null;
  party_name?: string | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  currency?: string | null;
  transaction_date?: string | null;
  valid_till?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  status?: string | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_lost_reason?: string | null;
  quotation_number?: string | null;
  description?: string | null;
}

export interface FinanceCustomerPayload {
  name: string;
  email?: string | null;
  billing_email?: string | null;
  phone?: string | null;
  phone_secondary?: string | null;
  address?: string | null;
  address_2?: string | null;
  city?: string | null;
  state?: string | null;
  zip_code?: string | null;
  country?: string | null;
  customer_type?: string | null;
  status?: string | null;
  billing_type?: string | null;
  gps?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  signup_date?: string | null;
}

export interface FinanceRevenueTrend {
  period: string;
  revenue: number;
  payment_count?: number;
}

export interface FinanceCollectionsAnalytics {
  by_method: Array<{
    method: string;
    amount: number;
    count: number;
  }>;
  timing?: Record<string, number>;
  daily_totals?: Array<{
    date: string;
    amount: number;
    count: number;
  }>;
  meta?: Record<string, unknown>;
}

export interface FinanceAgingAnalytics {
  buckets: {
    current: FinanceAgingBucket;
    '1_30': FinanceAgingBucket;
    '31_60': FinanceAgingBucket;
    '61_90': FinanceAgingBucket;
    over_90: FinanceAgingBucket;
  };
  total_invoices: number;
}

export interface FinanceAgingBucket {
  count: number;
  total: number;
  invoices: Array<{
    id: number;
    customer_name: string | null;
    total_amount: number;
    balance: number | null;
    due_date: string | null;
    status: string;
  }>;
}

export interface FinanceByCurrencyAnalytics {
  by_currency: Array<{
    currency: string;
    mrr?: number;
    arr?: number;
    subscription_count?: number;
    outstanding?: number;
  }>;
}

export interface FinancePaymentBehavior {
  avg_days_to_pay?: number;
  late_payments_percent?: number;
  early_payments_percent?: number;
  on_time_percent?: number;
  late_count?: number;
  early_count?: number;
  on_time_count?: number;
  best_payers?: Array<{ customer_name?: string | null; avg_days_to_pay?: number }>;
  worst_payers?: Array<{ customer_name?: string | null; avg_days_to_pay?: number }>;
  stats?: Record<string, number>;
}

export interface FinanceForecast {
  baseline_mrr: number;
  projection: Array<{ period: string; mrr: number }>;
  assumptions?: Record<string, unknown>;
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
  total?: number;
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
  total_invoices?: number;
  aging?: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  suppliers?: AccountingPayable[];
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
  total_invoices?: number;
  aging?: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  customers?: AccountingReceivable[];
  currency?: string;
}

export interface AccountingTaxCategory {
  id?: number;
  name?: string;
  description?: string | null;
  rate?: number | null;
  is_withholding?: boolean;
}

export interface AccountingTaxTemplate {
  id?: number;
  name?: string;
  type?: string | null;
  description?: string | null;
  rate?: number | null;
  account?: string | null;
}

export interface AccountingTaxSummary {
  total?: number;
  period?: { start?: string; end?: string };
  by_account?: Array<{
    account: string;
    account_name?: string | null;
    amount: number;
  }>;
}

export interface AccountingOutstandingSummary {
  total?: number;
  top?: Array<{
    id?: number | string;
    name?: string;
    amount?: number;
    currency?: string | null;
  }>;
  currency?: string | null;
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
  accounts?: Array<{
    id?: number;
    account?: string;
    account_type?: string | null;
    party_type?: string | null;
    party?: string | null;
    debit?: number;
    credit?: number;
    debit_in_account_currency?: number;
    credit_in_account_currency?: number;
    exchange_rate?: number;
    reference_type?: string | null;
    reference_name?: string | null;
    reference_due_date?: string | null;
    cost_center?: string | null;
    project?: string | null;
    bank_account?: string | null;
    cheque_no?: string | null;
    cheque_date?: string | null;
    user_remark?: string | null;
    idx?: number;
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

export interface AccountingAccountDetail extends AccountingAccount {
  ledger?: AccountingGeneralLedgerEntry[];
}

export interface AccountingPurchaseInvoice {
  id: number;
  invoice_number: string | null;
  supplier_id: number | null;
  supplier_name?: string | null;
  status: string;
  total_amount: number;
  balance?: number | null;
  currency?: string | null;
  invoice_date: string | null;
  due_date: string | null;
  description?: string | null;
}

export interface AccountingPurchaseInvoiceDetail extends AccountingPurchaseInvoice {
  lines?: Array<{
    item?: string | null;
    description?: string | null;
    quantity?: number;
    rate?: number;
    amount?: number;
  }>;
  payments?: Array<{
    id: number;
    amount: number;
    status: string;
    payment_date: string | null;
    method?: string | null;
  }>;
}

export interface AccountingPurchaseInvoiceListResponse {
  purchase_invoices: AccountingPurchaseInvoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountingBankTransaction {
  id: number;
  erpnext_id?: string | null;
  account: string;
  company?: string | null;
  status: string;
  amount: number;
  currency?: string | null;
  transaction_date: string | null;
  description?: string | null;
  reference?: string | null;
  reference_number?: string | null;
  transaction_id?: string | null;
  transaction_type?: string | null;
  deposit?: number | null;
  withdrawal?: number | null;
  allocated_amount?: number | null;
  unallocated_amount?: number | null;
  party_type?: string | null;
  party?: string | null;
  bank_party_name?: string | null;
  bank_party_account_number?: string | null;
  bank_party_iban?: string | null;
  docstatus?: number | null;
}

export interface AccountingBankTransactionListResponse {
  transactions: AccountingBankTransaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountingBankTransactionPayment {
  id?: number;
  erpnext_id?: string | null;
  payment_document?: string | null;
  payment_entry?: string | null;
  allocated_amount?: number | null;
  idx?: number | null;
}

export interface AccountingBankTransactionDetail extends AccountingBankTransaction {
  payments?: AccountingBankTransactionPayment[];
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

// Purchasing Domain Types
export interface PurchasingDashboard {
  as_of_date: string;
  total_outstanding: number;
  total_overdue: number;
  overdue_percentage: number;
  supplier_count: number;
  status_breakdown: Record<string, { count: number; total: number }>;
  due_this_week: { count: number; total: number };
  top_suppliers: Array<{ name: string; outstanding: number; bill_count: number }>;
}

export interface PurchasingBill {
  id: number;
  erpnext_id: string | null;
  supplier: string | null;
  supplier_name: string | null;
  posting_date: string | null;
  due_date: string | null;
  grand_total: number;
  outstanding_amount: number;
  status: string | null;
  currency: string | null;
  is_overdue: boolean;
  days_overdue: number;
  write_back_status?: string | null;
}

export interface PurchasingBillListResponse {
  bills: PurchasingBill[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingBillDetail extends PurchasingBill {
  net_total: number | null;
  total_taxes_and_charges: number;
  company: string | null;
  cost_center: string | null;
  remarks: string | null;
  items?: Array<{
    id?: number;
    item_code?: string | null;
    item_name?: string | null;
    description?: string | null;
    qty?: number;
    stock_qty?: number;
    uom?: string | null;
    stock_uom?: string | null;
    conversion_factor?: number;
    rate?: number;
    price_list_rate?: number;
    discount_percentage?: number;
    discount_amount?: number;
    amount?: number;
    net_amount?: number;
    warehouse?: string | null;
    expense_account?: string | null;
    cost_center?: string | null;
    purchase_order?: string | null;
    purchase_receipt?: string | null;
    idx?: number;
  }>;
  gl_entries: Array<{
    id: number;
    account: string;
    debit: number;
    credit: number;
    cost_center: string | null;
  }>;
}

export interface PurchasingBillPayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  posting_date?: string | null;
  due_date?: string | null;
  grand_total?: number | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  currency?: string | null;
  status?: string | null;
}

export interface PurchasingPayment {
  id: number;
  receipt_number: string | null;
  supplier_id?: number | null;
  supplier_name?: string | null;
  purchase_invoice_id?: number | null;
  amount: number;
  currency: string | null;
  payment_method: string | null;
  status: string | null;
  payment_date: string | null;
  transaction_reference?: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
}

export interface PurchasingPaymentListResponse {
  payments: PurchasingPayment[];
  total: number;
  limit: number;
  offset: number;
}

export type PurchasingPaymentDetail = PurchasingPayment;

export interface PurchasingSupplier {
  id: number;
  erpnext_id: string | null;
  name: string | null;
  group: string | null;
  type: string | null;
  country: string | null;
  currency: string | null;
  email: string | null;
  mobile: string | null;
  outstanding: number;
}

export interface PurchasingSupplierListResponse {
  suppliers: PurchasingSupplier[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingSupplierDetail extends PurchasingSupplier {
  tax_id: string | null;
  pan: string | null;
  total_purchases: number;
  total_outstanding: number;
  bill_count: number;
  recent_bills: Array<{
    id: number;
    bill_no: string | null;
    date: string | null;
    amount: number;
    outstanding: number;
    status: string | null;
  }>;
}

export interface PurchasingSupplierGroupsResponse {
  total_groups: number;
  groups: Array<{ name: string; count: number; outstanding: number }>;
}

export interface PurchasingExpense {
  id: number;
  posting_date: string | null;
  account?: string;
  amount: number;
  party: string | null;
  voucher_type: string | null;
  voucher_no: string | null;
  cost_center: string | null;
  status?: string | null;
  employee_id?: number | null;
  purpose?: string | null;
  total_claimed_amount?: number | null;
  total_sanctioned_amount?: number | null;
  total_amount_reimbursed?: number | null;
  company?: string | null;
  currency?: string | null;
  write_back_status?: string | null;
}

export interface PurchasingExpenseListResponse {
  expenses: PurchasingExpense[];
  total: number;
  limit: number;
  offset: number;
  summary?: Record<string, any>;
}

export interface PurchasingExpenseDetail extends PurchasingExpense {
  purpose?: string | null;
  employee_name?: string | null;
  expense_date?: string | null;
  notes?: string | null;
}

export interface PurchasingExpensePayload {
  employee_id?: number | null;
  purpose?: string | null;
  posting_date?: string | null;
  total_claimed_amount?: number | null;
  total_sanctioned_amount?: number | null;
  total_amount_reimbursed?: number | null;
  currency?: string | null;
  status?: string | null;
  company?: string | null;
  cost_center?: string | null;
}

export interface PurchasingExpenseTypesResponse {
  total_expenses: number;
  expense_types: Array<{
    account: string;
    account_name: string | null;
    total: number;
    entry_count: number;
    percentage: number;
  }>;
}

export interface PurchasingAgingBucket {
  count: number;
  total: number;
  invoices: Array<{
    id: number;
    invoice_no: string | null;
    supplier: string | null;
    posting_date: string | null;
    due_date: string | null;
    grand_total: number;
    outstanding: number;
    days_overdue: number;
  }>;
}

export interface PurchasingAgingResponse {
  as_of_date: string;
  total_payable: number;
  total_invoices: number;
  aging: {
    current: PurchasingAgingBucket;
    '1_30': PurchasingAgingBucket;
    '31_60': PurchasingAgingBucket;
    '61_90': PurchasingAgingBucket;
    over_90: PurchasingAgingBucket;
  };
}

export interface PurchasingBySupplierResponse {
  total: number;
  suppliers: Array<{
    name: string | null;
    bill_count: number;
    total_purchases: number;
    outstanding: number;
    percentage: number;
  }>;
}

export interface PurchasingByCostCenterResponse {
  total: number;
  cost_centers: Array<{
    name: string;
    total: number;
    entry_count: number;
    percentage: number;
  }>;
}

export interface PurchasingExpenseTrendResponse {
  granularity: string;
  trend: Array<{
    period: string | null;
    total: number;
    entry_count: number;
  }>;
}

export interface PurchasingDebitNote {
  id: number;
  erpnext_id: string | null;
  supplier: string | null;
  posting_date: string | null;
  grand_total: number;
  status: string | null;
  return_against: string | null;
  write_back_status?: string | null;
}

export interface PurchasingDebitNoteListResponse {
  debit_notes: PurchasingDebitNote[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingDebitNoteDetail extends PurchasingDebitNote {
  due_date?: string | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  total_taxes_and_charges?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  company?: string | null;
  items?: Array<{
    id?: number;
    item_code?: string | null;
    item_name?: string | null;
    description?: string | null;
    qty?: number;
    stock_qty?: number;
    uom?: string | null;
    stock_uom?: string | null;
    conversion_factor?: number;
    rate?: number;
    amount?: number;
    net_amount?: number;
    expense_account?: string | null;
    cost_center?: string | null;
    purchase_invoice?: string | null;
    purchase_invoice_item?: string | null;
    idx?: number;
  }>;
}

export interface PurchasingDebitNotePayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  posting_date?: string | null;
  due_date?: string | null;
  return_against?: string | null;
  grand_total?: number | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  total_taxes_and_charges?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  status?: string | null;
}

export interface PurchasingOrder {
  id?: number;
  order_no: string | null;
  supplier: string | null;
  date: string | null;
  total: number;
  grand_total?: number | null;
  schedule_date?: string | null;
  status?: string | null;
  currency?: string | null;
  write_back_status?: string | null;
}

export interface PurchasingOrderListResponse {
  orders: PurchasingOrder[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingOrderDetail extends PurchasingOrder {
  net_total?: number | null;
  total_taxes_and_charges?: number | null;
  discount_amount?: number | null;
  per_billed?: number | null;
  per_received?: number | null;
  billed_amt?: number | null;
  received_amt?: number | null;
  company?: string | null;
  conversion_rate?: number | null;
  cost_center?: string | null;
  project?: string | null;
  payment_terms_template?: string | null;
  items?: Array<{
    id?: number;
    item_code?: string | null;
    item_name?: string | null;
    description?: string | null;
    qty?: number;
    stock_qty?: number;
    uom?: string | null;
    stock_uom?: string | null;
    conversion_factor?: number;
    rate?: number;
    price_list_rate?: number;
    discount_percentage?: number;
    discount_amount?: number;
    amount?: number;
    net_amount?: number;
    received_qty?: number;
    billed_amt?: number;
    warehouse?: string | null;
    schedule_date?: string | null;
    expense_account?: string | null;
    cost_center?: string | null;
    idx?: number;
  }>;
}

export interface PurchasingOrderPayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  transaction_date?: string | null;
  schedule_date?: string | null;
  grand_total?: number | null;
  net_total?: number | null;
  total_taxes_and_charges?: number | null;
  discount_amount?: number | null;
  per_billed?: number | null;
  per_received?: number | null;
  billed_amt?: number | null;
  received_amt?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  status?: string | null;
  cost_center?: string | null;
  project?: string | null;
  payment_terms_template?: string | null;
}

// Inventory Domain Types
export interface InventoryItemPayload {
  item_code?: string;
  item_name?: string;
  description?: string | null;
  item_group?: string | null;
  uom?: string | null;
  brand?: string | null;
  is_stock_item?: boolean;
  default_warehouse?: string | null;
  reorder_level?: number | null;
  reorder_qty?: number | null;
  valuation_rate?: number | null;
  standard_selling_rate?: number | null;
  standard_buying_rate?: number | null;
  serial_number_series?: string | null;
  barcode?: string | null;
  status?: string | null;
}

export interface InventoryWarehousePayload {
  name?: string;
  parent_warehouse?: string | null;
  company?: string | null;
  is_group?: boolean;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  contact_person?: string | null;
  status?: string | null;
}

export interface InventoryStockEntryLine {
  item_code: string;
  qty: number;
  uom: string;
  s_warehouse?: string | null;
  t_warehouse?: string | null;
  rate?: number | null;
  serial_nos?: string[] | null;
}

export interface InventoryStockEntryPayload {
  entry_type: 'material_receipt' | 'material_issue' | 'material_transfer';
  posting_date?: string | null;
  company?: string | null;
  remarks?: string | null;
  lines: InventoryStockEntryLine[];
}

// Reports Domain Types
export interface ReportsRevenueSummary {
  mrr?: number;
  arr?: number;
  total_revenue?: number;
  growth_rate?: number;
  currency?: string | null;
}

export interface ReportsRevenueTrendPoint {
  period: string;
  revenue: number;
  mrr?: number;
  arr?: number;
}

export interface ReportsRevenueByCustomer {
  customer?: string | null;
  customer_id?: number | string | null;
  revenue: number;
  growth_rate?: number | null;
}

export interface ReportsRevenueByProduct {
  product?: string | null;
  revenue: number;
  growth_rate?: number | null;
}

export interface ReportsExpensesSummary {
  total_expenses?: number;
  currency?: string | null;
  categories?: Array<{ category: string; total: number; percentage?: number }>;
}

export interface ReportsExpenseTrendPoint {
  period: string;
  total: number;
}

export interface ReportsExpenseByCategory {
  category: string;
  total: number;
  percentage?: number;
}

export interface ReportsExpenseByVendor {
  vendor: string | null;
  total: number;
  invoice_count?: number;
}

export interface ReportsProfitabilityMargins {
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
}

export interface ReportsProfitabilityTrendPoint {
  period: string;
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
}

export interface ReportsProfitabilityBySegment {
  segment: string;
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
}

export interface ReportsCashPositionSummary {
  total_cash?: number;
  currency?: string | null;
  accounts?: Array<{ account: string; balance: number }>;
  updated_at?: string | null;
}

export interface ReportsCashPositionForecastPoint {
  period: string;
  projected_cash: number;
}

export interface ReportsCashPositionRunway {
  months_of_runway?: number;
  burn_rate?: number;
  currency?: string | null;
}

export { ApiError };
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

// HR Domain Types
export interface HrListResponse<T> {
  data: T[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface HrLeaveType {
  id?: number;
  leave_type?: string;
  name?: string;
  is_lwp?: boolean;
  is_carry_forward?: boolean;
}

export interface HrHolidayItem {
  holiday_date: string;
  description?: string | null;
  weekly_off?: boolean;
  idx?: number;
}

export interface HrHolidayListPayload {
  holiday_list_name: string;
  from_date: string;
  to_date: string;
  company?: string | null;
  weekly_off?: string | null;
  holidays?: HrHolidayItem[];
}

export interface HrHolidayList extends HrHolidayListPayload {
  id?: number;
}

export interface HrLeavePolicyDetail {
  leave_type?: string;
  annual_allocation?: number;
  max_leaves?: number;
  idx?: number;
}

export interface HrLeavePolicyPayload {
  leave_policy_name: string;
  company?: string | null;
  details?: HrLeavePolicyDetail[];
}

export interface HrLeavePolicy extends HrLeavePolicyPayload {
  id?: number;
}

export interface HrLeaveAllocationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  leave_type: string;
  leave_type_id?: number;
  from_date: string;
  to_date: string;
  new_leaves_allocated?: number;
  total_leaves_allocated?: number;
  unused_leaves?: number;
  carry_forwarded_leaves?: number;
  carry_forwarded_leaves_count?: number;
  leave_policy?: string;
  status?: string;
  docstatus?: number;
  company?: string;
}

export interface HrLeaveAllocation extends HrLeaveAllocationPayload {
  id?: number;
}

export interface HrLeaveApplicationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  leave_type: string;
  leave_type_id?: number;
  from_date: string;
  to_date: string;
  total_leave_days?: number;
  half_day?: boolean;
  half_day_date?: string | null;
  status?: string;
  company?: string;
  description?: string | null;
  docstatus?: number;
  leave_allocation?: string | null;
}

export interface HrLeaveApplication extends HrLeaveApplicationPayload {
  id?: number;
}

export interface HrShiftType {
  id?: number;
  shift_type?: string;
  name?: string;
  company?: string;
}

export interface HrShiftAssignmentPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  shift_type: string;
  shift_type_id?: number;
  from_date: string;
  to_date?: string;
  status?: string;
  company?: string;
  docstatus?: number;
}

export interface HrShiftAssignment extends HrShiftAssignmentPayload {
  id?: number;
}

export interface HrAttendancePayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  attendance_date: string;
  status: string;
  leave_type?: string | null;
  leave_application?: string | null;
  shift?: string | null;
  company?: string;
  in_time?: string | null;
  out_time?: string | null;
  working_hours?: number;
  check_in_latitude?: number;
  check_in_longitude?: number;
  check_out_latitude?: number;
  check_out_longitude?: number;
  device_info?: string | null;
  late_entry?: boolean;
  early_exit?: boolean;
  docstatus?: number;
}

export interface HrAttendance extends HrAttendancePayload {
  id?: number;
}

export interface HrAttendanceRequestPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  from_date: string;
  to_date: string;
  status?: string;
  company?: string;
  reason?: string | null;
  docstatus?: number;
}

export interface HrAttendanceRequest extends HrAttendanceRequestPayload {
  id?: number;
}

export interface HrJobOpeningPayload {
  job_title: string;
  status?: string;
  company?: string;
  designation?: string;
  department?: string;
  branch?: string;
  posting_date?: string;
  expected_date?: string;
  vacancies?: number;
  description?: string | null;
  docstatus?: number;
}

export interface HrJobOpening extends HrJobOpeningPayload {
  id?: number;
}

export interface HrJobApplicantPayload {
  applicant_name: string;
  email_id: string;
  status?: string;
  job_title?: string;
  source?: string;
  applicant_id?: string;
  company?: string;
  application_date?: string;
  docstatus?: number;
}

export interface HrJobApplicant extends HrJobApplicantPayload {
  id?: number;
}

export interface HrJobOfferTerm {
  offer_term?: string;
  value?: string;
  value_type?: string;
  idx?: number;
}

export interface HrJobOfferPayload {
  job_applicant: string;
  job_applicant_id?: number;
  job_applicant_name?: string;
  job_title?: string;
  company?: string;
  status?: string;
  offer_date?: string;
  designation?: string;
  salary_structure?: string;
  terms?: HrJobOfferTerm[];
}

export interface HrJobOffer extends HrJobOfferPayload {
  id?: number;
}

export interface HrInterviewPayload {
  job_applicant_id: number;
  scheduled_at: string;
  interviewer: string;
  location?: string | null;
  mode?: string | null;
  feedback?: string | null;
  rating?: number | null;
  result?: string | null;
  status?: string;
}

export interface HrInterview extends HrInterviewPayload {
  id?: number;
}

export interface HrSalaryComponentPayload {
  salary_component: string;
  abbr?: string;
  type: string;
  company?: string;
  depends_on_payment_days?: boolean;
  do_not_include_in_total?: boolean;
  round_to_the_nearest_integer?: boolean;
}

export interface HrSalaryComponent extends HrSalaryComponentPayload {
  id?: number;
}

export interface HrSalaryStructureLine {
  salary_component: string;
  abbr?: string;
  amount?: number;
  default_amount?: number;
  idx?: number;
}

export interface HrSalaryStructurePayload {
  name: string;
  company?: string;
  is_active?: boolean;
  currency?: string;
  earnings?: HrSalaryStructureLine[];
  deductions?: HrSalaryStructureLine[];
}

export interface HrSalaryStructure extends HrSalaryStructurePayload {
  id?: number;
}

export interface HrSalaryStructureAssignmentPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  salary_structure: string;
  from_date: string;
  to_date?: string;
  base?: number;
  variable?: number;
  company?: string;
}

export interface HrSalaryStructureAssignment extends HrSalaryStructureAssignmentPayload {
  id?: number;
}

export interface HrPayrollEntryPayload {
  company: string;
  posting_date: string;
  payroll_frequency: string;
  start_date: string;
  end_date: string;
  status?: string;
  docstatus?: number;
}

export interface HrPayrollEntry extends HrPayrollEntryPayload {
  id?: number;
}

export interface HrSalarySlipPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  department?: string;
  designation?: string;
  branch?: string;
  salary_structure?: string;
  posting_date: string;
  start_date: string;
  end_date: string;
  payroll_frequency?: string;
  company: string;
  currency?: string;
  total_working_days?: number;
  absent_days?: number;
  payment_days?: number;
  leave_without_pay?: number;
  gross_pay?: number;
  total_deduction?: number;
  net_pay?: number;
  rounded_total?: number;
  status?: string;
  docstatus?: number;
  bank_name?: string | null;
  bank_account_no?: string | null;
  payroll_entry?: string | null;
  earnings?: HrSalaryStructureLine[];
  deductions?: HrSalaryStructureLine[];
}

export interface HrSalarySlip extends HrSalarySlipPayload {
  id?: number;
}

export interface HrTrainingProgramPayload {
  program_name: string;
  description?: string | null;
  company?: string;
}

export interface HrTrainingProgram extends HrTrainingProgramPayload {
  id?: number;
}

export interface HrTrainingEventEmployee {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  attendance?: string;
  feedback?: string | null;
  idx?: number;
}

export interface HrTrainingEventPayload {
  training_event_name: string;
  training_program: string;
  status?: string;
  company?: string;
  start_time?: string;
  end_time?: string;
  location?: string | null;
  instructor?: string | null;
  employees?: HrTrainingEventEmployee[];
}

export interface HrTrainingEvent extends HrTrainingEventPayload {
  id?: number;
}

export interface HrTrainingResultPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  training_event: string;
  result?: string;
  score?: number;
  company?: string;
}

export interface HrTrainingResult extends HrTrainingResultPayload {
  id?: number;
}

export interface HrAppraisalTemplateGoal {
  goal: string;
  weightage?: number;
  idx?: number;
}

export interface HrAppraisalTemplatePayload {
  template_name: string;
  company?: string;
  goals?: HrAppraisalTemplateGoal[];
}

export interface HrAppraisalTemplate extends HrAppraisalTemplatePayload {
  id?: number;
}

export interface HrAppraisalGoal {
  goal: string;
  weightage?: number;
  score?: number;
  rating?: string;
  idx?: number;
}

export interface HrAppraisalPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  status?: string;
  appraisal_template?: string;
  start_date?: string;
  end_date?: string;
  goals?: HrAppraisalGoal[];
}

export interface HrAppraisal extends HrAppraisalPayload {
  id?: number;
}

export interface HrOnboardingActivity {
  activity: string;
  status?: string;
  idx?: number;
}

export interface HrEmployeeOnboardingPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  status?: string;
  activities?: HrOnboardingActivity[];
}

export interface HrEmployeeOnboarding extends HrEmployeeOnboardingPayload {
  id?: number;
}

export interface HrSeparationActivity {
  activity: string;
  status?: string;
  idx?: number;
}

export interface HrEmployeeSeparationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  reason?: string;
  notice_date?: string;
  relieving_date?: string;
  status?: string;
  activities?: HrSeparationActivity[];
}

export interface HrEmployeeSeparation extends HrEmployeeSeparationPayload {
  id?: number;
}

export interface HrEmployeePromotionDetail {
  promotion_based_on?: string;
  current_designation?: string;
  new_designation?: string;
  idx?: number;
}

export interface HrEmployeePromotionPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  promotion_date: string;
  company?: string;
  status?: string;
  details?: HrEmployeePromotionDetail[];
}

export interface HrEmployeePromotion extends HrEmployeePromotionPayload {
  id?: number;
}

export interface HrEmployeeTransferDetail {
  from_department?: string;
  to_department?: string;
  idx?: number;
}

export interface HrEmployeeTransferPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  transfer_date: string;
  status?: string;
  details?: HrEmployeeTransferDetail[];
}

export interface HrEmployeeTransfer extends HrEmployeeTransferPayload {
  id?: number;
}

// HR Analytics Types
export interface HrAnalyticsOverview {
  leave_by_status?: Record<string, number>;
  attendance_status_30d?: Record<string, number>;
  recruitment_funnel?: Record<string, number>;
  payroll_30d?: {
    gross_total?: number;
    deduction_total?: number;
    net_total?: number;
    slip_count?: number;
  };
  training_events_by_status?: Record<string, number>;
  appraisals_by_status?: Record<string, number>;
}

export interface HrLeaveTrendPoint {
  month: string;
  count: number;
}

export interface HrAttendanceTrendPoint {
  date: string;
  status_counts?: Record<string, number>;
  total?: number;
}

export interface HrPayrollSummary {
  gross_total?: number;
  deduction_total?: number;
  net_total?: number;
  average_gross?: number;
  average_net?: number;
  slip_count?: number;
}

export interface HrPayrollTrendPoint {
  month: string;
  gross_total?: number;
  deduction_total?: number;
  net_total?: number;
  slip_count?: number;
}

export interface HrPayrollComponentBreakdown {
  salary_component?: string;
  component_type?: string;
  amount?: number;
  count?: number;
}

export interface HrRecruitmentFunnel {
  openings?: Record<string, number>;
  applicants?: Record<string, number>;
  offers?: Record<string, number>;
}

export interface HrAppraisalStatusBreakdown {
  status_counts?: Record<string, number>;
}

export interface HrLifecycleEventsBreakdown {
  onboarding?: Record<string, number>;
  separation?: Record<string, number>;
  promotion?: Record<string, number>;
  transfer?: Record<string, number>;
}
