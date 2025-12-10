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

    // In development only, allow NEXT_PUBLIC_SERVICE_TOKEN for testing
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
      return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
    }
    return '';
  }
  // Server-side: only use service token in development
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
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
    // Include credentials for cookie-based auth (httpOnly cookies)
    // This enables backend to use secure session cookies as an alternative to Bearer tokens
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      // If we have a localStorage token, send it as Bearer; otherwise rely on cookies
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

export interface Customer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  status: string;
  customer_type: string;
  billing_type: string | null;
  pop_id: number | null;
  account_number: string | null;
  signup_date: string | null;
  tenure_days: number;
}

export interface CustomerDetail extends Customer {
  address: string | null;
  city: string | null;
  state: string | null;
  pop: { id: number; name: string } | null;
  external_ids: {
    splynx_id: number | null;
    erpnext_id: string | null;
    chatwoot_contact_id: number | null;
  };
  metrics: {
    total_invoiced: number;
    total_paid: number;
    outstanding: number;
    open_tickets: number;
    total_conversations: number;
  };
  subscriptions: Array<{
    id: number;
    plan_name: string;
    price: number;
    status: string;
    start_date: string | null;
    download_speed: number | null;
    upload_speed: number | null;
  }>;
  recent_invoices: Array<{
    id: number;
    invoice_number: string | null;
    total_amount: number;
    amount_paid: number;
    status: string;
    invoice_date: string | null;
    due_date: string | null;
    days_overdue: number;
  }>;
  recent_conversations: Array<{
    id: number;
    chatwoot_id: number | null;
    status: string;
    channel: string | null;
    created_at: string | null;
    message_count: number;
  }>;
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

  // Customers
  getCustomers: (params?: {
    status?: string;
    customer_type?: string;
    billing_type?: string;
    pop_id?: number;
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<{ total: number; data: Customer[] }>('/customers', { params }),

  getCustomer: (id: number) =>
    fetchApi<CustomerDetail>(`/customers/${id}`),

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
        credentials: 'include',
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
    fetchApi<ChurnRiskCustomer[]>('/analytics/churn/risk', { params: { limit } }),

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

export { ApiError };
