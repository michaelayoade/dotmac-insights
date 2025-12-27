'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  Clock,
  RotateCcw,
  Eye,
  Filter,
} from 'lucide-react';
import { adminApi, type OutboundLog, type OutboundStats } from '@/lib/api/domains/admin';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; border: string; text: string; label: string }> = {
    success: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Success' },
    pending: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', label: 'Pending' },
    failed: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', label: 'Failed' },
    skipped: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', label: 'Skipped' },
  };
  const c = config[status] || config.pending;
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', c.bg, c.border, c.text)}>
      {status === 'success' && <CheckCircle2 className="w-3 h-3" />}
      {status === 'pending' && <Clock className="w-3 h-3" />}
      {status === 'failed' && <XCircle className="w-3 h-3" />}
      {status === 'skipped' && <ArrowUpRight className="w-3 h-3" />}
      {c.label}
    </span>
  );
}

function OutboundLogRow({
  log,
  onRetry,
  onView,
}: {
  log: OutboundLog;
  onRetry: (id: number) => void;
  onView: (id: number) => void;
}) {
  return (
    <div className="px-5 py-4 flex items-center gap-4 hover:bg-slate-elevated/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-foreground font-medium">{log.entity_type}</span>
          <span className="text-slate-muted font-mono text-xs">#{log.entity_id}</span>
          <span className="text-slate-muted">→</span>
          <span className="text-foreground capitalize">{log.target_system}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-elevated text-slate-muted capitalize">
            {log.operation}
          </span>
        </div>
        {log.error_message && (
          <p className="text-sm text-rose-400 truncate">{log.error_message}</p>
        )}
        <div className="flex items-center gap-3 mt-1 text-xs text-slate-muted">
          {log.external_id && <span>External: {log.external_id}</span>}
          <span>{formatRelativeTime(new Date(log.created_at))}</span>
          {log.retry_count > 0 && <span>Retries: {log.retry_count}</span>}
        </div>
      </div>
      <StatusBadge status={log.status} />
      <div className="flex items-center gap-1">
        <Button
          onClick={() => onView(log.id)}
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated"
          title="View details"
        >
          <Eye className="w-4 h-4" />
        </Button>
        {log.status === 'failed' && (
          <Button
            onClick={() => onRetry(log.id)}
            className="p-2 text-slate-muted hover:text-blue-400 hover:bg-blue-500/10"
            title="Retry"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

function DetailModal({
  logId,
  onClose,
}: {
  logId: number | null;
  onClose: () => void;
}) {
  const { data: log, isLoading } = useSWR(
    logId ? `outbound-log-${logId}` : null,
    () => adminApi.getOutboundLog(logId!)
  );

  if (!logId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-card border border-slate-border rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">Outbound Sync Details</h3>
          <Button onClick={onClose} className="text-slate-muted hover:text-foreground">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>
        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : log ? (
          <div className="p-5 overflow-y-auto max-h-[60vh] space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Entity</p>
                <p className="text-foreground">{log.entity_type} #{log.entity_id}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Target</p>
                <p className="text-foreground capitalize">{log.target_system}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Operation</p>
                <p className="text-foreground capitalize">{log.operation}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Status</p>
                <StatusBadge status={log.status} />
              </div>
            </div>

            {log.external_id && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">External ID</p>
                <p className="text-foreground font-mono">{log.external_id}</p>
              </div>
            )}

            {log.idempotency_key && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Idempotency Key</p>
                <p className="text-foreground font-mono text-xs">{log.idempotency_key}</p>
              </div>
            )}

            {log.error_message && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Error</p>
                <p className="text-rose-400 bg-rose-500/10 rounded p-3 text-sm">{log.error_message}</p>
              </div>
            )}

            {log.request_payload && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Request Payload</p>
                <pre className="bg-slate-elevated rounded p-3 text-xs text-slate-muted overflow-x-auto">
                  {JSON.stringify(log.request_payload, null, 2)}
                </pre>
              </div>
            )}

            {log.response_payload && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Response Payload</p>
                <pre className="bg-slate-elevated rounded p-3 text-xs text-slate-muted overflow-x-auto">
                  {JSON.stringify(log.response_payload, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function OutboundPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope(['sync:read', 'admin:read']);
  const canFetch = !authLoading && !missingScope;

  const [targetFilter, setTargetFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedLog, setSelectedLog] = useState<number | null>(null);

  const {
    data: logsData,
    isLoading,
    error,
    mutate: refetch,
  } = useSWR(
    canFetch ? ['outbound-logs', targetFilter, statusFilter] : null,
    () => adminApi.getOutboundLogs({
      target_system: targetFilter || undefined,
      status: statusFilter || undefined,
      limit: 100,
    })
  );

  const { data: stats } = useSWR(
    canFetch ? 'outbound-stats' : null,
    () => adminApi.getOutboundStats()
  );

  const handleRetry = async (id: number) => {
    try {
      await adminApi.retryOutboundLog(id);
      refetch();
    } catch (err) {
      console.error('Failed to retry:', err);
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
          <div className="p-3 bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-xl">
            <ArrowUpRight className="w-6 h-6 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Outbound Sync Logs</h1>
            <p className="text-slate-muted text-sm">
              View sync operations to external systems
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

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard title="Total" value={stats.total} icon={ArrowUpRight} />
          <StatCard title="Success" value={stats.success} icon={CheckCircle2} variant="success" />
          <StatCard title="Failed" value={stats.failed} icon={XCircle} variant="danger" />
          <StatCard title="Pending" value={stats.pending} icon={Clock} />
          <StatCard title="Skipped" value={stats.skipped} icon={ArrowUpRight} />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-muted" />
          <select
            value={targetFilter}
            onChange={(e) => setTargetFilter(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">All Targets</option>
            <option value="splynx">Splynx</option>
            <option value="erpnext">ERPNext</option>
            <option value="chatwoot">Chatwoot</option>
            <option value="zoho">Zoho</option>
          </select>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
        >
          <option value="">All Statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
          <option value="skipped">Skipped</option>
        </select>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load outbound logs</p>
            <p className="text-rose-300/70 text-sm">{error.message}</p>
          </div>
        </div>
      )}

      {/* Logs List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border">
          <h3 className="font-semibold text-foreground">
            Outbound Logs ({logsData?.total || 0})
          </h3>
        </div>

        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : logsData && logsData.items.length > 0 ? (
          <div className="divide-y divide-slate-border">
            {logsData.items.map((log) => (
              <OutboundLogRow
                key={log.id}
                log={log}
                onRetry={handleRetry}
                onView={setSelectedLog}
              />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <ArrowUpRight className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-foreground font-medium">No outbound logs found</p>
            <p className="text-slate-muted text-sm">Outbound syncs will appear here</p>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <DetailModal
        logId={selectedLog}
        onClose={() => setSelectedLog(null)}
      />
    </div>
  );
}
