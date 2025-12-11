import useSWR, { SWRConfiguration } from 'swr';
import { api, ApiError } from '@/lib/api';

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
    sort_by?: 'invoice_date' | 'due_date' | 'total_amount' | 'amount_paid' | 'customer_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
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
    sort_by?: 'payment_date' | 'amount' | 'customer_id' | 'invoice_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
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
    sort_by?: 'issue_date' | 'amount' | 'customer_id' | 'invoice_id' | 'status';
    sort_dir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
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

export function useFinanceAging(params?: { as_of_date?: string; currency?: string }, config?: SWRConfiguration) {
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
export function useAccountingDashboard(config?: SWRConfiguration) {
  return useSWR('accounting-dashboard', () => api.getAccountingDashboard(), {
    refreshInterval: 60000,
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

export function useAccountingTrialBalance(asOfDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['accounting-trial-balance', asOfDate],
    () => api.getAccountingTrialBalance(asOfDate),
    config
  );
}

export function useAccountingBalanceSheet(asOfDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['accounting-balance-sheet', asOfDate],
    () => api.getAccountingBalanceSheet(asOfDate),
    config
  );
}

export function useAccountingIncomeStatement(startDate?: string, endDate?: string, config?: SWRConfiguration) {
  return useSWR(
    ['accounting-income-statement', startDate, endDate],
    () => api.getAccountingIncomeStatement(startDate, endDate),
    config
  );
}

export function useAccountingGeneralLedger(
  params?: {
    account?: string;
    start_date?: string;
    end_date?: string;
    voucher_type?: string;
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
    () => api.getAccountingCashFlow(startDate, endDate),
    config
  );
}

export function useAccountingPayables(
  params?: {
    supplier_id?: number;
    min_amount?: number;
    limit?: number;
    offset?: number;
    currency?: string;
    aging_bucket?: string;
    search?: string;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-payables', params],
    () => api.getAccountingPayables(params),
    config
  );
}

export function useAccountingReceivables(
  params?: {
    customer_id?: number;
    min_amount?: number;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  return useSWR(
    ['accounting-receivables', params],
    () => api.getAccountingReceivables(params),
    config
  );
}

export function useAccountingJournalEntries(
  params?: {
    voucher_type?: string;
    start_date?: string;
    end_date?: string;
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

export function useAccountingSuppliers(
  params?: {
    search?: string;
    supplier_group?: string;
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

// Non-hook export for triggering sync
export async function triggerSync(source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) {
  return api.triggerSync(source, fullSync);
}

export { ApiError };
