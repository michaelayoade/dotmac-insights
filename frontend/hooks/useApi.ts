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

export function useRevenueTrend(months = 12, config?: SWRConfiguration) {
  return useSWR(
    ['revenue-trend', months],
    () => api.getRevenueTrend(months),
    config
  );
}

export function useChurnTrend(months = 12, config?: SWRConfiguration) {
  return useSWR(
    ['churn-trend', months],
    () => api.getChurnTrend(months),
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

// Non-hook export for triggering sync
export async function triggerSync(source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) {
  return api.triggerSync(source, fullSync);
}

export { ApiError };
