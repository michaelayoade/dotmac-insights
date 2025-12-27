'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Database,
  ArrowUpRight,
  Calendar,
  Activity,
  Zap,
} from 'lucide-react';
import { adminApi, type SyncDashboard, type EntityStatus } from '@/lib/api/domains/admin';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; border: string; text: string; label: string }> = {
    completed: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Completed' },
    success: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Success' },
    started: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', label: 'Running' },
    running: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', label: 'Running' },
    failed: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', label: 'Failed' },
    partial: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', label: 'Partial' },
    never_synced: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', label: 'Never Synced' },
  };

  const c = config[status] || config.never_synced;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium px-2.5 py-0.5 text-xs',
        c.bg,
        c.border,
        c.text
      )}
    >
      {(status === 'completed' || status === 'success') && <CheckCircle2 className="w-3 h-3" />}
      {(status === 'failed') && <XCircle className="w-3 h-3" />}
      {(status === 'started' || status === 'running') && <RefreshCw className="w-3 h-3 animate-spin" />}
      {(status === 'partial' || status === 'never_synced') && <AlertTriangle className="w-3 h-3" />}
      {c.label}
    </span>
  );
}

function SourceCard({
  source,
  onTriggerSync,
}: {
  source: SyncDashboard['sources'][0];
  onTriggerSync: (source: string) => void;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-2 h-2 rounded-full',
            source.last_status === 'completed' ? 'bg-emerald-400' :
            source.last_status === 'failed' ? 'bg-rose-400' :
            source.last_status === 'started' ? 'bg-blue-400 animate-pulse' :
            'bg-slate-500'
          )} />
          <h3 className="font-semibold text-foreground capitalize">{source.source}</h3>
        </div>
        <Button
          onClick={() => onTriggerSync(source.source)}
          className="text-xs px-2 py-1 bg-slate-elevated text-slate-muted hover:text-foreground"
        >
          <RefreshCw className="w-3 h-3 mr-1" />
          Sync
        </Button>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-muted">Last Sync</span>
          <span className="text-foreground">
            {source.last_sync_at
              ? formatRelativeTime(new Date(source.last_sync_at))
              : 'Never'}
          </span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-muted">Status</span>
          {source.last_status ? (
            <StatusBadge status={source.last_status} />
          ) : (
            <span className="text-slate-500">-</span>
          )}
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-muted">Syncs Today</span>
          <span className="text-foreground">{source.total_syncs_today}</span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-muted">Success Rate</span>
          <span className={cn(
            'font-medium',
            source.success_rate >= 90 ? 'text-emerald-400' :
            source.success_rate >= 70 ? 'text-amber-400' :
            'text-rose-400'
          )}>
            {source.success_rate.toFixed(0)}%
          </span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-muted">Records Today</span>
          <span className="text-foreground">{source.records_synced_today.toLocaleString()}</span>
        </div>
        {source.failed_records > 0 && (
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-muted">Failed Records</span>
            <Link
              href="/admin/sync/dlq"
              className="text-rose-400 hover:underline flex items-center gap-1"
            >
              {source.failed_records}
              <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SyncDashboardPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope(['sync:read', 'admin:read']);
  const canFetch = !authLoading && !missingScope;

  const {
    data: dashboard,
    isLoading,
    error,
    mutate: refetch,
  } = useSWR(
    canFetch ? 'sync-dashboard' : null,
    () => adminApi.getSyncDashboard(),
    { refreshInterval: 30000 }
  );

  const {
    data: entities,
    isLoading: entitiesLoading,
  } = useSWR(
    canFetch ? 'sync-entities' : null,
    () => adminApi.getEntityStatus()
  );

  const handleTriggerSync = async (source: string) => {
    try {
      await adminApi.triggerSync(source as 'splynx' | 'erpnext' | 'chatwoot' | 'all');
      refetch();
    } catch (err) {
      console.error('Failed to trigger sync:', err);
    }
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need sync:read or admin:read permission to view this page."
        backHref="/admin"
        backLabel="Back to Admin"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-teal-500/20 to-cyan-500/20 rounded-xl">
            <RefreshCw className="w-6 h-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Sync Dashboard</h1>
            <p className="text-slate-muted text-sm">
              Monitor and manage data synchronization
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => refetch()}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </Button>
          <Button
            onClick={() => handleTriggerSync('all')}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30 transition-colors"
          >
            <Zap className="w-4 h-4" />
            Sync All
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load sync status</p>
            <p className="text-rose-300/70 text-sm">
              {error.message || 'Please check your connection and try again.'}
            </p>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-slate-card border border-slate-border rounded-xl p-5 animate-pulse">
              <div className="h-4 w-20 bg-slate-700 rounded mb-2" />
              <div className="h-8 w-32 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      ) : dashboard ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Syncs Today"
            value={dashboard.total_syncs_today}
            icon={Activity}
          />
          <StatCard
            title="Success Rate"
            value={`${dashboard.success_rate.toFixed(0)}%`}
            icon={CheckCircle2}
            variant={dashboard.success_rate >= 90 ? 'success' : dashboard.success_rate >= 70 ? 'warning' : 'danger'}
          />
          <Link href="/admin/sync/dlq">
            <StatCard
              title="Failed Records"
              value={dashboard.total_failed_records}
              icon={AlertTriangle}
              variant={dashboard.total_failed_records > 0 ? 'danger' : undefined}
            />
          </Link>
          <Link href="/admin/sync/schedules">
            <StatCard
              title="Active Schedules"
              value={dashboard.active_schedules}
              icon={Calendar}
            />
          </Link>
        </div>
      ) : null}

      {/* Source Status Cards */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-4">Sync Sources</h2>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-slate-card border border-slate-border rounded-xl p-5 animate-pulse">
                <div className="h-6 w-24 bg-slate-700 rounded mb-4" />
                <div className="space-y-3">
                  {[...Array(5)].map((_, j) => (
                    <div key={j} className="h-4 bg-slate-700 rounded" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : dashboard ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {dashboard.sources.map((source) => (
              <SourceCard
                key={source.source}
                source={source}
                onTriggerSync={handleTriggerSync}
              />
            ))}
          </div>
        ) : null}
      </div>

      {/* Recent Logs */}
      {dashboard && dashboard.recent_logs.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
            <h3 className="font-semibold text-foreground">Recent Activity</h3>
            <Link
              href="/sync"
              className="text-sm text-teal-electric hover:underline flex items-center gap-1"
            >
              View All
              <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="divide-y divide-slate-border">
            {dashboard.recent_logs.map((log) => (
              <div key={log.id} className="px-5 py-3 flex items-center justify-between hover:bg-slate-elevated/30">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'w-2 h-2 rounded-full',
                    log.status === 'completed' ? 'bg-emerald-400' :
                    log.status === 'failed' ? 'bg-rose-400' :
                    'bg-amber-400'
                  )} />
                  <div>
                    <span className="text-foreground font-medium capitalize">{log.source}</span>
                    <span className="text-slate-muted"> / </span>
                    <span className="text-slate-muted">{log.entity_type}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-slate-muted">
                    +{log.records_created} / ~{log.records_updated}
                  </span>
                  <StatusBadge status={log.status} />
                  <span className="text-slate-muted text-xs">
                    {log.started_at ? formatRelativeTime(new Date(log.started_at)) : '-'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Link
          href="/admin/sync/dlq"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-rose-500/10 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div>
              <h4 className="text-foreground font-medium text-sm">Failed Records</h4>
              <p className="text-slate-muted text-xs">Retry or resolve</p>
            </div>
          </div>
        </Link>

        <Link
          href="/admin/sync/cursors"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Database className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <h4 className="text-foreground font-medium text-sm">Cursors</h4>
              <p className="text-slate-muted text-xs">View sync markers</p>
            </div>
          </div>
        </Link>

        <Link
          href="/admin/sync/outbound"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/10 rounded-lg">
              <ArrowUpRight className="w-4 h-4 text-violet-400" />
            </div>
            <div>
              <h4 className="text-foreground font-medium text-sm">Outbound</h4>
              <p className="text-slate-muted text-xs">Outbound sync logs</p>
            </div>
          </div>
        </Link>

        <Link
          href="/admin/sync/schedules"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <Calendar className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <h4 className="text-foreground font-medium text-sm">Schedules</h4>
              <p className="text-slate-muted text-xs">Manage sync schedules</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
