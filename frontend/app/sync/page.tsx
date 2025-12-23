'use client';

import { useState } from 'react';
import {
  RefreshCw,
  Database,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Play,
  Loader2,
  Server,
  MessageSquare,
  CreditCard,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { DataTable } from '@/components/DataTable';
import { useSyncStatus, useSyncLogs, triggerSync } from '@/hooks/useApi';
import { formatDate, cn } from '@/lib/utils';
import { useToast, Modal } from '@dotmac/core';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DashboardShell, PageHeader, Button } from '@/components/ui';

type SyncSource = 'splynx' | 'erpnext' | 'chatwoot';

const SOURCE_CONFIG: Record<SyncSource, {
  name: string;
  icon: typeof Database;
  color: string;
  description: string;
  entities: string[];
}> = {
  splynx: {
    name: 'Splynx',
    icon: CreditCard,
    color: 'text-blue-400',
    description: 'Customer billing, subscriptions, invoices, and payments',
    entities: ['Customers', 'Subscriptions', 'Invoices', 'Payments', 'Services'],
  },
  erpnext: {
    name: 'ERPNext',
    icon: Server,
    color: 'text-purple-400',
    description: 'Employees, expenses, and business operations',
    entities: ['Employees', 'Expenses', 'Leave Requests', 'Payroll', 'Attendance'],
  },
  chatwoot: {
    name: 'Chatwoot',
    icon: MessageSquare,
    color: 'text-amber-400',
    description: 'Customer conversations and support tickets',
    entities: ['Conversations', 'Messages', 'Contacts', 'Agents', 'Teams'],
  },
};

export default function SyncPage() {
  const { hasAccess: canRead, isLoading: authLoading } = useRequireScope('sync:read');
  const { hasAccess: canWrite } = useRequireScope('sync:write');
  const [syncingSource, setSyncingSource] = useState<SyncSource | 'all' | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ open: boolean; source: SyncSource | null }>({ open: false, source: null });
  const swrGuard = { isPaused: () => authLoading || !canRead };
  const { data: syncStatus, mutate: refreshStatus, error: syncStatusError, isLoading: statusLoading } = useSyncStatus(swrGuard);
  const { data: syncLogs, mutate: refreshLogs, isLoading: logsLoading, error: syncLogsError } = useSyncLogs(50, swrGuard);
  const { toast } = useToast();

  const handleSync = async (source: SyncSource | 'all', fullSync: boolean = false) => {
    if (!canWrite) {
      toast({ title: 'Access denied', description: 'You need sync:write to trigger syncs.', variant: 'error' });
      return;
    }
    setSyncingSource(source);
    const sourceName = source === 'all' ? 'All Sources' : SOURCE_CONFIG[source].name;

    toast({
      title: `${fullSync ? 'Full' : 'Quick'} sync requested`,
      description: `Syncing ${sourceName}...`,
      variant: 'info',
    });

    try {
      const response = await triggerSync(source, fullSync);
      refreshStatus();
      refreshLogs();
      toast({
        title: 'Sync started',
        description: response?.message || `${sourceName} sync initiated`,
        variant: 'success',
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toast({
        title: 'Sync failed',
        description: message,
        variant: 'error',
      });
    } finally {
      setSyncingSource(null);
    }
  };

  const handleFullSyncClick = (source: SyncSource) => {
    setConfirmModal({ open: true, source });
  };

  const confirmFullSync = () => {
    if (confirmModal.source) {
      handleSync(confirmModal.source, true);
    }
    setConfirmModal({ open: false, source: null });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return <Badge variant="success" size="sm"><CheckCircle className="w-3 h-3 mr-1" />Success</Badge>;
      case 'error':
        return <Badge variant="danger" size="sm"><XCircle className="w-3 h-3 mr-1" />Error</Badge>;
      case 'running':
        return <Badge variant="info" size="sm"><Loader2 className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
      default:
        return <Badge variant="default" size="sm"><Clock className="w-3 h-3 mr-1" />Pending</Badge>;
    }
  };

  if (authLoading) {
    return <LoadingState />;
  }

  if (!canRead) {
    return <AccessDenied />;
  }

  const isLoading = statusLoading || logsLoading;
  const firstError = syncStatusError || syncLogsError;
  const retryAll = () => {
    refreshStatus();
    refreshLogs();
  };

  return (
    <DashboardShell
      isLoading={isLoading}
      error={firstError}
      onRetry={retryAll}
      softError={true}
      loadingMessage="Loading sync status..."
    >
      <div className="space-y-8">
        {firstError && (
          <ErrorDisplay
            message="Failed to load sync status."
            error={firstError as Error}
            onRetry={retryAll}
          />
        )}
        {/* Header */}
        <PageHeader
          title="Data Sync"
          subtitle="Manage data synchronization from external systems"
          icon={Database}
          actions={
            <Button
              variant="primary"
              icon={syncingSource === 'all' ? Loader2 : RefreshCw}
              onClick={() => handleSync('all', false)}
              disabled={syncingSource !== null || !canWrite}
              loading={syncingSource === 'all'}
            >
              Sync All Sources
            </Button>
          }
        />

      {/* Sync Status Overview */}
      {syncStatus && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-teal-electric/20">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-muted text-sm">Last Sync</span>
              <Badge variant="info">Most Recent</Badge>
            </div>
            <p className="text-foreground font-mono text-lg">
              {(() => {
                const lastSyncs = Object.values(syncStatus || {})
                  .filter((s): s is NonNullable<typeof s> => !!(s as any)?.last_sync)
                  .map((s: any) => new Date(s.last_sync).getTime());
                const latest = lastSyncs.length > 0 ? Math.max(...lastSyncs) : null;
                return latest ? formatDate(new Date(latest).toISOString()) : 'Never';
              })()}
            </p>
          </Card>

          <Card className="border-teal-electric/20">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-muted text-sm">Total Records</span>
              <Badge variant="success">Synced</Badge>
            </div>
            <p className="text-foreground font-mono text-lg">
              {Object.values(syncStatus || {})
                .filter((s): s is NonNullable<typeof s> => !!s)
                .reduce((sum, s: any) => sum + (s.records_created || 0) + (s.records_updated || 0), 0)
                .toLocaleString()}
            </p>
          </Card>

          <Card className="border-teal-electric/20">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-muted text-sm">Sync Health</span>
              {Object.values(syncStatus || {}).some((s: any) => s?.error) ? (
                <Badge variant="warning">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Has Errors
                </Badge>
              ) : (
                <Badge variant="success">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Healthy
                </Badge>
              )}
            </div>
            <p className="text-foreground font-mono text-lg">
              {Object.values(syncStatus || {}).filter((s: any) => s?.status === 'success').length} / {Object.keys(syncStatus || {}).length} OK
            </p>
          </Card>
        </div>
      )}

      {/* Source Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {(Object.keys(SOURCE_CONFIG) as SyncSource[]).map((source) => {
          const config = SOURCE_CONFIG[source];
          const Icon = config.icon;
          const sourceStatus = syncStatus?.[source];
          const isSyncing = syncingSource === source || syncingSource === 'all';

          return (
            <Card key={source} className="relative overflow-hidden">
              {/* Sync indicator */}
              {isSyncing && (
                <div className="absolute inset-0 bg-teal-electric/5 animate-pulse" />
              )}

              <div className="relative">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-12 h-12 rounded-xl bg-slate-elevated flex items-center justify-center', config.color)}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">{config.name}</h3>
                      <p className="text-slate-muted text-xs">
                        {sourceStatus?.last_sync
                          ? `Last: ${formatDate(sourceStatus.last_sync)}`
                          : 'Never synced'}
                      </p>
                    </div>
                  </div>
                  {sourceStatus && getStatusBadge(sourceStatus.status)}
                </div>

                {/* Description */}
                <p className="text-slate-muted text-sm mb-3">{config.description}</p>

                {/* Synced Entities */}
                <div className="flex flex-wrap gap-1 mb-4">
                  {config.entities.map((entity) => (
                    <span
                      key={entity}
                      className="px-2 py-0.5 text-xs rounded-full bg-slate-elevated text-slate-muted"
                    >
                      {entity}
                    </span>
                  ))}
                </div>

                {/* Stats */}
                {sourceStatus && (
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-slate-elevated rounded-lg p-3">
                      <p className="text-slate-muted text-xs">Records</p>
                      <p className="text-foreground font-mono font-semibold">
                        {((sourceStatus.records_created || 0) + (sourceStatus.records_updated || 0)).toLocaleString()}
                      </p>
                    </div>
                    <div className="bg-slate-elevated rounded-lg p-3">
                      <p className="text-slate-muted text-xs">Duration</p>
                      <p className="text-foreground font-mono font-semibold">
                        {sourceStatus.duration_seconds ? `${sourceStatus.duration_seconds}s` : '—'}
                      </p>
                    </div>
                  </div>
                )}

                {/* Error Message */}
                {sourceStatus?.error && (
                  <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 mb-4">
                    <p className="text-coral-alert text-sm font-mono truncate">
                      {sourceStatus.error}
                    </p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <Button
                    onClick={() => handleSync(source, false)}
                    disabled={isSyncing || !canWrite}
                    className={cn(
                      'flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all',
                      isSyncing || !canWrite
                        ? 'bg-slate-elevated text-slate-muted cursor-not-allowed'
                        : 'bg-slate-elevated text-foreground hover:bg-slate-border'
                    )}
                  >
                    {isSyncing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                    Quick Sync
                  </Button>
                  <Button
                    onClick={() => handleFullSyncClick(source)}
                    disabled={isSyncing || !canWrite}
                    className={cn(
                      'flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all',
                      isSyncing || !canWrite
                        ? 'bg-slate-elevated text-slate-muted cursor-not-allowed'
                        : 'border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-elevated'
                    )}
                  >
                    <RefreshCw className="w-4 h-4" />
                    Full Sync
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Sync Logs */}
      <Card padding="none">
        <div className="p-6 border-b border-slate-border flex items-center justify-between">
          <div>
            <CardTitle>Sync History</CardTitle>
            <CardDescription>Recent synchronization activity</CardDescription>
          </div>
          <Button
            onClick={() => refreshLogs()}
            className="text-slate-muted hover:text-foreground transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
          </Button>
        </div>
        <DataTable
          columns={[
            {
              key: 'source',
              header: 'Source',
              render: (item) => {
                const source = item.source as SyncSource;
                const config = SOURCE_CONFIG[source];
                if (!config) return <span className="capitalize">{source}</span>;
                const Icon = config.icon;
                return (
                  <div className="flex items-center gap-2">
                    <Icon className={cn('w-4 h-4', config.color)} />
                    <span className="text-foreground font-medium">{config.name}</span>
                  </div>
                );
              },
            },
            {
              key: 'sync_type',
              header: 'Type',
              render: (item) => (
                <Badge variant={item.sync_type === 'full' ? 'info' : 'default'} size="sm">
                  {item.sync_type as string}
                </Badge>
              ),
            },
            {
              key: 'status',
              header: 'Status',
              render: (item) => getStatusBadge(item.status as string),
            },
            {
              key: 'records_fetched',
              header: 'Records',
              align: 'right',
              render: (item) => (
                <span className="font-mono text-foreground">
                  {(item.records_fetched as number || 0).toLocaleString()}
                  {(item.records_created || item.records_updated) ? (
                    <span className="text-slate-muted text-xs ml-1">
                      (+{String(item.records_created || 0)}/~{String(item.records_updated || 0)})
                    </span>
                  ) : null}
                </span>
              ),
            },
            {
              key: 'duration_seconds',
              header: 'Duration',
              align: 'right',
              render: (item) => (
                <span className="font-mono text-slate-muted">
                  {item.duration_seconds ? `${(item.duration_seconds as number).toFixed(1)}s` : '—'}
                </span>
              ),
            },
            {
              key: 'started_at',
              header: 'Started',
              render: (item) => (
                <span className="text-slate-muted text-sm">
                  {formatDate(item.started_at as string)}
                </span>
              ),
            },
            {
              key: 'error_message',
              header: 'Error',
              render: (item) =>
                item.error_message ? (
                  <span className="text-coral-alert text-sm truncate max-w-[200px] block">
                    {item.error_message as string}
                  </span>
                ) : (
                  <span className="text-slate-muted">—</span>
                ),
            },
          ]}
          data={(syncLogs || []) as unknown as Record<string, unknown>[]}
          keyField="id"
          loading={logsLoading}
          emptyMessage="No sync history available"
        />
      </Card>

      {/* Full Sync Confirmation Modal */}
      <Modal
        open={confirmModal.open}
        onOpenChange={(open) => setConfirmModal({ open, source: confirmModal.source })}
        title="Confirm Full Sync"
        description={`Full sync will re-fetch all data from ${confirmModal.source ? SOURCE_CONFIG[confirmModal.source].name : 'the source'}. This may take several minutes and will reset incremental sync cursors.`}
        size="sm"
      >
        <div className="flex gap-3 justify-end mt-6">
          <Button
            onClick={() => setConfirmModal({ open: false, source: null })}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
          >
            Cancel
          </Button>
          <Button
            onClick={confirmFullSync}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-amber-warn text-slate-deep hover:bg-amber-400 transition-colors"
          >
            <RefreshCw className="w-4 h-4 inline mr-2" />
            Start Full Sync
          </Button>
        </div>
      </Modal>
      </div>
    </DashboardShell>
  );
}
