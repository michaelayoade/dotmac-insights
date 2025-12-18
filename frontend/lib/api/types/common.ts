/**
 * Common/shared types used across multiple domains
 */

// Dashboard overview types
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

// Analytics / overview types
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

export interface AgingBucket {
  count: number;
  amount: number;
}

export interface AgingBySegment {
  by_segment: Record<
    string,
    {
      current: AgingBucket;
      '1_30_days': AgingBucket;
      '31_60_days': AgingBucket;
      '61_90_days': AgingBucket;
      over_90_days: AgingBucket;
      total: AgingBucket;
    }
  >;
  total_outstanding: number;
}

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

export interface TicketsByType {
  by_type: Array<{
    type: string;
    count: number;
    resolved: number;
    resolution_rate: number;
  }>;
  total: number;
}

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
}

// Common pagination response structure
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// Common date range params
export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

// Common list params
export interface ListParams {
  limit?: number;
  offset?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

// Common status types
export type EntityStatus = 'active' | 'inactive' | 'pending' | 'cancelled' | 'blocked';

// Audit fields common to many entities
export interface AuditFields {
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  updated_by?: string;
}
