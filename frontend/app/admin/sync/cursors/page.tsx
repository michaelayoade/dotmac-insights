'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Database,
  RotateCcw,
  Clock,
} from 'lucide-react';
import { adminApi, type SyncCursor, type CursorHealth } from '@/lib/api/domains/admin';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function HealthBadge({ status }: { status: 'healthy' | 'stale' | 'critical' }) {
  const config = {
    healthy: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Healthy' },
    stale: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', label: 'Stale' },
    critical: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', label: 'Critical' },
  };
  const c = config[status];
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', c.bg, c.border, c.text)}>
      {status === 'healthy' && <CheckCircle2 className="w-3 h-3" />}
      {status === 'stale' && <Clock className="w-3 h-3" />}
      {status === 'critical' && <AlertTriangle className="w-3 h-3" />}
      {c.label}
    </span>
  );
}

function getCursorHealth(cursor: SyncCursor): 'healthy' | 'stale' | 'critical' {
  if (!cursor.last_sync_at) return 'critical';
  const lastSync = new Date(cursor.last_sync_at);
  const hoursAgo = (Date.now() - lastSync.getTime()) / (1000 * 60 * 60);
  if (hoursAgo > 72) return 'critical';
  if (hoursAgo > 24) return 'stale';
  return 'healthy';
}

function CursorRow({
  cursor,
  onReset,
}: {
  cursor: SyncCursor;
  onReset: (source: string, entityType: string) => void;
}) {
  const health = getCursorHealth(cursor);

  return (
    <div className="px-5 py-4 flex items-center gap-4 hover:bg-slate-elevated/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-foreground font-medium capitalize">{cursor.source}</span>
          <span className="text-slate-muted">/</span>
          <span className="text-foreground">{cursor.entity_type}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-muted">
          <span>Records: {cursor.records_synced.toLocaleString()}</span>
          {cursor.last_sync_at && (
            <span>Last: {formatRelativeTime(new Date(cursor.last_sync_at))}</span>
          )}
          {cursor.last_id && (
            <span className="font-mono">ID: {cursor.last_id}</span>
          )}
        </div>
      </div>
      <HealthBadge status={health} />
      <Button
        onClick={() => onReset(cursor.source, cursor.entity_type)}
        className="p-2 text-slate-muted hover:text-amber-400 hover:bg-amber-500/10"
        title="Reset cursor (will trigger full sync)"
      >
        <RotateCcw className="w-4 h-4" />
      </Button>
    </div>
  );
}

export default function CursorsPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope(['sync:read', 'admin:read']);
  const canFetch = !authLoading && !missingScope;

  const [sourceFilter, setSourceFilter] = useState<string>('');

  const {
    data: cursorsData,
    isLoading,
    error,
    mutate: refetch,
  } = useSWR(
    canFetch ? ['sync-cursors', sourceFilter] : null,
    () => adminApi.getCursors({ source: sourceFilter || undefined })
  );

  const { data: health } = useSWR(
    canFetch ? 'cursor-health' : null,
    () => adminApi.getCursorHealth()
  );

  const handleReset = async (source: string, entityType: string) => {
    const reason = window.prompt('Reason for reset (optional):');
    if (reason === null) return; // Cancelled

    if (!window.confirm(`Reset cursor for ${source}/${entityType}? This will trigger a full sync on next run.`)) {
      return;
    }

    try {
      await adminApi.resetCursor(source, entityType, reason || undefined);
      refetch();
    } catch (err) {
      console.error('Failed to reset cursor:', err);
      alert('Failed to reset cursor');
    }
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need sync:read or admin:read permission to view this page."
        backHref="/admin/sync"
        backLabel="Back to Sync Dashboard"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 rounded-xl">
            <Database className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Sync Cursors</h1>
            <p className="text-slate-muted text-sm">
              View and manage incremental sync markers
            </p>
          </div>
        </div>
        <Button
          onClick={() => refetch()}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Health Stats */}
      {health && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Total Cursors" value={health.total_cursors} icon={Database} />
          <StatCard title="Healthy" value={health.healthy} icon={CheckCircle2} variant="success" />
          <StatCard title="Stale (>24h)" value={health.stale} icon={Clock} variant="warning" />
          <StatCard title="Critical (>72h)" value={health.critical} icon={AlertTriangle} variant="danger" />
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-4">
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
        >
          <option value="">All Sources</option>
          <option value="splynx">Splynx</option>
          <option value="erpnext">ERPNext</option>
          <option value="chatwoot">Chatwoot</option>
        </select>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load cursors</p>
            <p className="text-rose-300/70 text-sm">{error.message}</p>
          </div>
        </div>
      )}

      {/* Cursors List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">
            Cursors ({cursorsData?.total || 0})
          </h3>
          <p className="text-xs text-slate-muted">
            Resetting a cursor will trigger a full sync on next run
          </p>
        </div>

        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : cursorsData && cursorsData.items.length > 0 ? (
          <div className="divide-y divide-slate-border">
            {cursorsData.items.map((cursor) => (
              <CursorRow
                key={`${cursor.source}-${cursor.entity_type}`}
                cursor={cursor}
                onReset={handleReset}
              />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <Database className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-foreground font-medium">No cursors found</p>
            <p className="text-slate-muted text-sm">Cursors will be created when syncs run</p>
          </div>
        )}
      </div>

      {/* Stale Cursors Warning */}
      {health && health.stale_cursors.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-400 font-medium">Stale Cursors Detected</p>
              <p className="text-amber-300/70 text-sm mb-3">
                The following cursors haven&apos;t been synced recently:
              </p>
              <ul className="space-y-1 text-sm text-amber-300/70">
                {health.stale_cursors.slice(0, 5).map((cursor) => (
                  <li key={`${cursor.source}-${cursor.entity_type}`}>
                    • <span className="capitalize">{cursor.source}</span> / {cursor.entity_type}
                    {cursor.last_sync_at && (
                      <span className="text-amber-400/60">
                        {' '}(last: {formatRelativeTime(new Date(cursor.last_sync_at))})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {health.stale_cursors.length > 5 && (
                <p className="text-amber-400/60 text-sm mt-2">
                  +{health.stale_cursors.length - 5} more
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
