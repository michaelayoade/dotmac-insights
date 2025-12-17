/**
 * Analytics Domain API (Cross-Domain Reports)
 * Includes: Revenue, Expenses, Profitability, Cash Position
 */

import { fetchApi } from '../core';

// =============================================================================
// REVENUE REPORTS
// =============================================================================

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

// =============================================================================
// EXPENSE REPORTS
// =============================================================================

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

// =============================================================================
// PROFITABILITY REPORTS
// =============================================================================

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

// =============================================================================
// CASH POSITION REPORTS
// =============================================================================

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

// =============================================================================
// API OBJECT
// =============================================================================

export const analyticsApi = {
  // Revenue Reports
  getRevenueSummary: () =>
    fetchApi<ReportsRevenueSummary>('/v1/reports/revenue/summary'),

  getRevenueTrend: () =>
    fetchApi<ReportsRevenueTrendPoint[]>('/v1/reports/revenue/trend'),

  getRevenueByCustomer: () =>
    fetchApi<ReportsRevenueByCustomer[]>('/v1/reports/revenue/by-customer'),

  getRevenueByProduct: () =>
    fetchApi<ReportsRevenueByProduct[]>('/v1/reports/revenue/by-product'),

  // Expense Reports
  getExpensesSummary: () =>
    fetchApi<ReportsExpensesSummary>('/v1/reports/expenses/summary'),

  getExpensesTrend: () =>
    fetchApi<ReportsExpenseTrendPoint[]>('/v1/reports/expenses/trend'),

  getExpensesByCategory: () =>
    fetchApi<ReportsExpenseByCategory[]>('/v1/reports/expenses/by-category'),

  getExpensesByVendor: () =>
    fetchApi<ReportsExpenseByVendor[]>('/v1/reports/expenses/by-vendor'),

  // Profitability Reports
  getProfitabilityMargins: () =>
    fetchApi<ReportsProfitabilityMargins>('/v1/reports/profitability/margins'),

  getProfitabilityTrend: () =>
    fetchApi<ReportsProfitabilityTrendPoint[]>('/v1/reports/profitability/trend'),

  getProfitabilityBySegment: () =>
    fetchApi<ReportsProfitabilityBySegment[]>('/v1/reports/profitability/by-segment'),

  // Cash Position Reports
  getCashPositionSummary: () =>
    fetchApi<ReportsCashPositionSummary>('/v1/reports/cash-position/summary'),

  getCashPositionForecast: () =>
    fetchApi<ReportsCashPositionForecastPoint[]>('/v1/reports/cash-position/forecast'),

  getCashPositionRunway: () =>
    fetchApi<ReportsCashPositionRunway>('/v1/reports/cash-position/runway'),
};
