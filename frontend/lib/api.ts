const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

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

  const apiKey = typeof window !== 'undefined'
    ? localStorage.getItem('dotmac_api_key') || ''
    : '';

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || `HTTP ${response.status}`);
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

  getRevenueTrend: (months = 12) =>
    fetchApi<RevenueTrend[]>('/analytics/revenue/trend', { params: { months } }),

  getChurnTrend: (months = 12) =>
    fetchApi<ChurnTrend[]>('/analytics/churn/trend', { params: { months } }),

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

export { ApiError };
