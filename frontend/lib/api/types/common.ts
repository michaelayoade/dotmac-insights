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
