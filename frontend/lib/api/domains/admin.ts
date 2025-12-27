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
// SYNC ADMIN TYPES
// =============================================================================

// DLQ Types
export interface DlqRecord {
  id: number;
  source: string;
  entity_type: string;
  external_id?: string | null;
  error_message: string;
  error_type?: string | null;
  retry_count: number;
  max_retries: number;
  is_resolved: boolean;
  resolution_notes?: string | null;
  created_at: string;
  last_retry_at?: string | null;
  resolved_at?: string | null;
}

export interface DlqDetailRecord extends DlqRecord {
  payload: string;
}

export interface DlqListResponse {
  items: DlqRecord[];
  total: number;
}

export interface DlqStats {
  total: number;
  unresolved: number;
  resolved: number;
  pending_retry: number;
  max_retries_reached: number;
  by_source: Record<string, number>;
  by_entity: Record<string, number>;
}

// Cursor Types
export interface SyncCursor {
  id: number;
  source: string;
  entity_type: string;
  last_sync_timestamp?: string | null;
  last_modified_at?: string | null;
  last_id?: string | null;
  cursor_value?: string | null;
  records_synced: number;
  last_sync_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CursorListResponse {
  items: SyncCursor[];
  total: number;
}

export interface CursorHealth {
  total_cursors: number;
  healthy: number;
  stale: number;
  critical: number;
  stale_cursors: SyncCursor[];
}

// Outbound Types
export interface OutboundLog {
  id: number;
  entity_type: string;
  entity_id: number;
  target_system: string;
  operation: string;
  status: string;
  external_id?: string | null;
  error_message?: string | null;
  retry_count: number;
  created_at: string;
  completed_at?: string | null;
}

export interface OutboundDetailLog extends OutboundLog {
  request_payload?: Record<string, unknown> | null;
  response_payload?: Record<string, unknown> | null;
  idempotency_key?: string | null;
  payload_hash?: string | null;
}

export interface OutboundListResponse {
  items: OutboundLog[];
  total: number;
}

export interface OutboundStats {
  total: number;
  success: number;
  failed: number;
  pending: number;
  skipped: number;
  by_target: Record<string, Record<string, number>>;
  by_entity: Record<string, Record<string, number>>;
}

// Dashboard Types
export interface SyncSourceDashboardStatus {
  source: string;
  last_sync_at?: string | null;
  last_status?: string | null;
  last_entity?: string | null;
  total_syncs_today: number;
  success_rate: number;
  records_synced_today: number;
  failed_records: number;
}

export interface SyncDashboard {
  total_syncs_today: number;
  success_rate: number;
  total_failed_records: number;
  active_schedules: number;
  sources: SyncSourceDashboardStatus[];
  recent_logs: Array<{
    id: number;
    source: string;
    entity_type: string;
    status: string;
    started_at?: string | null;
    records_created: number;
    records_updated: number;
  }>;
}

export interface EntityStatus {
  source: string;
  entity_type: string;
  last_sync_at?: string | null;
  records_synced: number;
  cursor_value?: string | null;
  failed_count: number;
}

// Schedule Types
export interface SyncSchedule {
  id: number;
  name: string;
  description?: string | null;
  task_name: string;
  cron_expression: string;
  kwargs?: Record<string, unknown> | null;
  is_enabled: boolean;
  is_system: boolean;
  last_run_at?: string | null;
  last_run_status?: string | null;
  last_error?: string | null;
  next_run_at?: string | null;
  run_count: number;
  created_at: string;
}

export interface ScheduleListResponse {
  items: SyncSchedule[];
  total: number;
}

export interface AvailableTask {
  name: string;
  description: string;
  default_kwargs?: Record<string, unknown> | null;
}

export interface ScheduleCreatePayload {
  name: string;
  description?: string | null;
  task_name: string;
  cron_expression: string;
  kwargs?: Record<string, unknown> | null;
  is_enabled?: boolean;
}

export interface ScheduleUpdatePayload {
  name?: string;
  description?: string | null;
  task_name?: string;
  cron_expression?: string;
  kwargs?: Record<string, unknown> | null;
  is_enabled?: boolean;
}

// Roles / Permissions
export interface PermissionResponse {
  id: number;
  name: string;
  scope: string;
  description?: string;
  category?: string;
}

export interface RoleResponse {
  id: number;
  name: string;
  description?: string;
  is_system: boolean;
  permissions: string[];
  user_count: number;
  created_at?: string;
}

export interface RoleCreatePayload {
  name: string;
  description?: string | null;
  permission_ids: number[];
}

export interface RoleUpdatePayload {
  name?: string;
  description?: string | null;
  permission_ids?: number[];
}

// =============================================================================
// API
// =============================================================================

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
  // SYNC ADMIN - Dashboard
  // =========================================================================

  getSyncDashboard: () => fetchApi<SyncDashboard>('/admin/sync/dashboard'),

  getEntityStatus: () => fetchApi<EntityStatus[]>('/admin/sync/entities'),

  triggerEntitySync: (source: string, entity: string, fullSync = false) =>
    fetchApi<{ message: string; task_id?: string }>(`/sync/${source}/${entity}`, {
      method: 'POST',
      params: { full_sync: fullSync },
    }),

  // =========================================================================
  // SYNC ADMIN - DLQ (Dead Letter Queue)
  // =========================================================================

  getDlqRecords: (params?: {
    source?: string;
    entity_type?: string;
    is_resolved?: boolean;
    limit?: number;
    offset?: number;
  }) => fetchApi<DlqListResponse>('/admin/sync/dlq', { params }),

  getDlqRecord: (id: number) => fetchApi<DlqDetailRecord>(`/admin/sync/dlq/${id}`),

  getDlqStats: () => fetchApi<DlqStats>('/admin/sync/dlq/stats'),

  retryDlqRecord: (id: number) =>
    fetchApi<{ status: string; record_id: number; retry_count: number }>(
      `/admin/sync/dlq/${id}/retry`,
      { method: 'POST' }
    ),

  retryDlqBatch: (params?: { source?: string; entity_type?: string; ids?: number[] }) =>
    fetchApi<{ status: string; count: number }>('/admin/sync/dlq/retry-batch', {
      method: 'POST',
      body: JSON.stringify(params || {}),
    }),

  resolveDlqRecord: (id: number, notes?: string) =>
    fetchApi<{ status: string; record_id: number }>(`/admin/sync/dlq/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ notes }),
    }),

  deleteDlqRecord: (id: number) =>
    fetchApi<{ status: string; record_id: number }>(`/admin/sync/dlq/${id}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // SYNC ADMIN - Cursors
  // =========================================================================

  getCursors: (params?: { source?: string; limit?: number; offset?: number }) =>
    fetchApi<CursorListResponse>('/admin/sync/cursors', { params }),

  getCursor: (source: string, entityType: string) =>
    fetchApi<SyncCursor>(`/admin/sync/cursors/${source}/${entityType}`),

  getCursorHealth: () => fetchApi<CursorHealth>('/admin/sync/cursors/health'),

  resetCursor: (source: string, entityType: string, reason?: string) =>
    fetchApi<{ status: string; source: string; entity_type: string }>(
      `/admin/sync/cursors/${source}/${entityType}/reset`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }
    ),

  updateCursor: (
    source: string,
    entityType: string,
    data: {
      last_sync_timestamp?: string;
      last_modified_at?: string;
      last_id?: string;
      cursor_value?: string;
    }
  ) =>
    fetchApi<SyncCursor>(`/admin/sync/cursors/${source}/${entityType}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // =========================================================================
  // SYNC ADMIN - Outbound Logs
  // =========================================================================

  getOutboundLogs: (params?: {
    target_system?: string;
    entity_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<OutboundListResponse>('/admin/sync/outbound', { params }),

  getOutboundLog: (id: number) => fetchApi<OutboundDetailLog>(`/admin/sync/outbound/${id}`),

  getOutboundStats: () => fetchApi<OutboundStats>('/admin/sync/outbound/stats'),

  retryOutboundLog: (id: number) =>
    fetchApi<{ status: string; log_id: number }>(`/admin/sync/outbound/${id}/retry`, {
      method: 'POST',
    }),

  // =========================================================================
  // SYNC ADMIN - Schedules
  // =========================================================================

  getSchedules: (params?: { is_enabled?: boolean }) =>
    fetchApi<ScheduleListResponse>('/admin/sync/schedules', { params }),

  getSchedule: (id: number) => fetchApi<SyncSchedule>(`/admin/sync/schedules/${id}`),

  getAvailableTasks: () => fetchApi<AvailableTask[]>('/admin/sync/schedules/tasks'),

  createSchedule: (payload: ScheduleCreatePayload) =>
    fetchApi<SyncSchedule>('/admin/sync/schedules', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSchedule: (id: number, payload: ScheduleUpdatePayload) =>
    fetchApi<SyncSchedule>(`/admin/sync/schedules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteSchedule: (id: number) =>
    fetchApi<{ status: string; schedule_id: number }>(`/admin/sync/schedules/${id}`, {
      method: 'DELETE',
    }),

  runScheduleNow: (id: number) =>
    fetchApi<{ status: string; schedule_id: number; task_id?: string }>(
      `/admin/sync/schedules/${id}/run`,
      { method: 'POST' }
    ),

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

    let response: Response;
    try {
      response = await fetch(
        `${API_BASE}/api/explore/tables/${table}/export?${searchParams.toString()}`,
        {
          credentials: 'include',
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

  // =========================================================================
  // ROLES / PERMISSIONS
  // =========================================================================

  listRoles: () => fetchApi<RoleResponse[]>('/admin/roles'),

  createRole: (payload: RoleCreatePayload) =>
    fetchApi<RoleResponse>('/admin/roles', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateRole: (roleId: number, payload: RoleUpdatePayload) =>
    fetchApi<RoleResponse>(`/admin/roles/${roleId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteRole: (roleId: number) =>
    fetchApi<{ status: string; role_id: number }>(`/admin/roles/${roleId}`, { method: 'DELETE' }),

  listPermissions: (category?: string) =>
    fetchApi<PermissionResponse[]>('/admin/permissions', {
      params: category ? { category } : undefined,
    }),
};

export default adminApi;
