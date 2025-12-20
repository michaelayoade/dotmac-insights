/**
 * Sync Domain Hooks
 *
 * SWR hooks for data synchronization status and operations.
 */
import useSWR, { SWRConfiguration } from 'swr';
import { fetcher, apiFetch } from '@/lib/api';
import { SYNC_CONFIG } from '@/lib/swr-config';

// ============================================================================
// TYPES
// ============================================================================

export interface SyncSourceStatus {
  status: 'success' | 'error' | 'running' | 'pending';
  last_sync?: string;
  records_created?: number;
  records_updated?: number;
  duration_seconds?: number;
  error?: string;
}

export interface SyncStatus {
  splynx?: SyncSourceStatus;
  erpnext?: SyncSourceStatus;
  chatwoot?: SyncSourceStatus;
}

export interface SyncLog {
  id: number;
  source: 'splynx' | 'erpnext' | 'chatwoot';
  sync_type: 'full' | 'incremental';
  status: 'success' | 'error' | 'running' | 'pending';
  records_fetched?: number;
  records_created?: number;
  records_updated?: number;
  duration_seconds?: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface SyncTriggerResponse {
  message: string;
  task_id?: string;
  full_sync?: boolean;
  backend?: 'celery' | 'asyncio';
}

export type SyncSource = 'all' | 'splynx' | 'erpnext' | 'chatwoot';

// ============================================================================
// HOOKS
// ============================================================================

/**
 * Fetch sync status for all sources
 */
export function useSyncStatus(config?: SWRConfiguration) {
  return useSWR<SyncStatus>(
    'sync-status',
    () => fetcher('/sync/status'),
    { ...SYNC_CONFIG, ...config }
  );
}

/**
 * Fetch sync logs
 */
export function useSyncLogs(limit = 50, config?: SWRConfiguration) {
  return useSWR<SyncLog[]>(
    ['sync-logs', limit],
    () => fetcher(`/sync/logs?limit=${limit}`),
    { ...SYNC_CONFIG, ...config }
  );
}

/**
 * Test connections to external systems
 */
export function useTestConnections(config?: SWRConfiguration) {
  return useSWR<Record<string, boolean>>(
    'sync-test-connections',
    () => fetcher('/sync/test-connections'),
    { ...config, revalidateOnFocus: false }
  );
}

// ============================================================================
// MUTATIONS
// ============================================================================

/**
 * Trigger a sync operation
 */
export async function triggerSync(
  source: SyncSource,
  fullSync = false
): Promise<SyncTriggerResponse> {
  return apiFetch<SyncTriggerResponse>(`/sync/${source}`, {
    method: 'POST',
    params: { full_sync: fullSync },
  });
}

/**
 * Test all connections
 */
export async function testConnections(): Promise<Record<string, boolean>> {
  return apiFetch<Record<string, boolean>>('/sync/test-connections', {
    method: 'POST',
  });
}

// ============================================================================
// COMPOSITE HOOK
// ============================================================================

/**
 * Combined hook for sync page with unified status
 */
export function useSyncDashboard(config?: SWRConfiguration) {
  const status = useSyncStatus(config);
  const logs = useSyncLogs(50, config);

  const isLoading = status.isLoading || logs.isLoading;
  const error = status.error || logs.error;
  const retry = () => {
    status.mutate();
    logs.mutate();
  };

  return {
    status: status.data,
    logs: logs.data,
    isLoading,
    error,
    retry,
    mutateStatus: status.mutate,
    mutateLogs: logs.mutate,
  };
}
