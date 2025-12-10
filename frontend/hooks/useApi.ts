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

export function useCustomers(
  params?: {
    status?: string;
    customer_type?: string;
    billing_type?: string;
    pop_id?: number;
    search?: string;
    limit?: number;
    offset?: number;
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

export function useSyncStatus(config?: SWRConfiguration) {
  return useSWR('sync-status', () => api.getSyncStatus(), {
    refreshInterval: 10000, // Refresh every 10 seconds
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

// Non-hook export for triggering sync
export async function triggerSync(source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) {
  return api.triggerSync(source, fullSync);
}

export { ApiError };
