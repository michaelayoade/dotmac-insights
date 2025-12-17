/**
 * Admin Domain API
 * Includes: Sync, Data Explorer, Settings
 */

import { fetchApi, API_BASE, ApiError } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Sync Types
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

// Data Explorer Types
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

// Settings Types
export interface SettingsGroupMeta {
  group: string;
  label: string;
  description: string;
}

export interface SettingsResponse {
  group: string;
  schema_version: number;
  data: Record<string, unknown>;
  updated_at?: string;
  updated_by?: string;
}

export interface SettingsSchemaResponse {
  group: string;
  schema: {
    type: string;
    description?: string;
    properties: Record<
      string,
      {
        type: string;
        description?: string;
        default?: unknown;
        enum?: string[];
        'x-secret'?: boolean;
        format?: string;
        minimum?: number;
        maximum?: number;
        pattern?: string;
      }
    >;
    required?: string[];
  };
  secret_fields: string[];
}

export interface SettingsTestResponse {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  result?: Record<string, unknown>;
  error?: string;
}

export interface SettingsAuditEntry {
  id: number;
  group_name: string;
  action: string;
  old_value_redacted?: string;
  new_value_redacted?: string;
  user_email: string;
  ip_address?: string;
  created_at: string;
}

// =============================================================================
// API
// =============================================================================

// Helper to get access token for export function
function getAccessToken(): string {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('dotmac_access_token');
    if (token) return token;
    const isDev = process.env.NODE_ENV === 'development';
    if (isDev && process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
      return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
    }
  }
  return '';
}

export const adminApi = {
  // =========================================================================
  // SYNC
  // =========================================================================

  getSyncStatus: () => fetchApi<SyncStatus>('/sync/status'),

  triggerSync: (source: 'all' | 'splynx' | 'erpnext' | 'chatwoot', fullSync = false) =>
    fetchApi<{ message: string }>(`/sync/${source}`, {
      method: 'POST',
      params: { full_sync: fullSync },
    }),

  testConnections: () =>
    fetchApi<Record<string, boolean>>('/sync/test-connections', { method: 'POST' }),

  getSyncLogs: (limit = 50) => fetchApi<SyncLog[]>('/sync/logs', { params: { limit } }),

  // =========================================================================
  // DATA EXPLORER
  // =========================================================================

  getTables: () => fetchApi<TableInfo>('/explore/tables'),

  getTablesEnhanced: () => fetchApi<TablesResponse>('/explore/tables'),

  getTableData: (
    table: string,
    params?: {
      limit?: number;
      offset?: number;
      order_by?: string;
      order_dir?: 'asc' | 'desc';
    }
  ) =>
    fetchApi<{ table: string; total: number; data: Record<string, unknown>[] }>(
      `/explore/tables/${table}`,
      { params }
    ),

  getTableDataEnhanced: (
    table: string,
    params?: {
      limit?: number;
      offset?: number;
      order_by?: string;
      order_dir?: 'asc' | 'desc';
      date_column?: string;
      start_date?: string;
      end_date?: string;
      search?: string;
    }
  ) => fetchApi<ExploreTableResponse>(`/explore/tables/${table}`, { params }),

  exportTableData: async (
    table: string,
    format: 'csv' | 'json',
    params?: {
      date_column?: string;
      start_date?: string;
      end_date?: string;
      search?: string;
    }
  ) => {
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
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE}/api/explore/tables/${table}/export?${searchParams.toString()}`,
        {
          credentials: accessToken ? 'omit' : 'include',
          headers: {
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
        }
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to reach the API';
      throw new ApiError(0, `Export failed: ${message}`);
    }

    if (!response.ok) {
      throw new ApiError(response.status, `Export failed: ${response.statusText}`);
    }

    return response.blob();
  },

  getTableStats: (table: string) =>
    fetchApi<Record<string, unknown>>(`/explore/tables/${table}/stats`),

  getDataQuality: () => fetchApi<DataQuality>('/explore/data-quality'),

  search: (q: string, limit = 50) =>
    fetchApi<Record<string, unknown[]>>('/explore/search', { params: { q, limit } }),

  // =========================================================================
  // SETTINGS
  // =========================================================================

  getSettingsGroups: () => fetchApi<SettingsGroupMeta[]>('/admin/settings'),

  getSettings: (group: string) => fetchApi<SettingsResponse>(`/admin/settings/${group}`),

  getSettingsSchema: (group: string) =>
    fetchApi<SettingsSchemaResponse>(`/admin/settings/${group}/schema`),

  updateSettings: (group: string, data: Record<string, unknown>) =>
    fetchApi<SettingsResponse>(`/admin/settings/${group}`, {
      method: 'PUT',
      body: JSON.stringify({ data }),
    }),

  testSettings: (group: string, data: Record<string, unknown>) =>
    fetchApi<SettingsTestResponse>(`/admin/settings/${group}/test`, {
      method: 'POST',
      body: JSON.stringify({ data }),
    }),

  getSettingsTestStatus: (jobId: string) =>
    fetchApi<SettingsTestResponse>(`/admin/settings/test/${jobId}`),

  getSettingsAuditLog: (params?: { group?: string; skip?: number; limit?: number }) =>
    fetchApi<SettingsAuditEntry[]>('/admin/settings/audit', { params }),
};

export default adminApi;
