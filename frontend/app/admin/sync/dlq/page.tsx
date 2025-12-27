'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Trash2,
  Eye,
  Filter,
} from 'lucide-react';
import { adminApi, type DlqRecord, type DlqStats } from '@/lib/api/domains/admin';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function StatusBadge({ isResolved }: { isResolved: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        isResolved
          ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
          : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
      )}
    >
      {isResolved ? (
        <>
          <CheckCircle2 className="w-3 h-3" />
          Resolved
        </>
      ) : (
        <>
          <XCircle className="w-3 h-3" />
          Failed
        </>
      )}
    </span>
  );
}

function DlqRecordRow({
  record,
  onRetry,
  onResolve,
  onView,
  onDelete,
}: {
  record: DlqRecord;
  onRetry: (id: number) => void;
  onResolve: (id: number) => void;
  onView: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="px-5 py-4 flex items-center gap-4 hover:bg-slate-elevated/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-foreground font-medium capitalize">{record.source}</span>
          <span className="text-slate-muted">/</span>
          <span className="text-slate-muted">{record.entity_type}</span>
          {record.external_id && (
            <>
              <span className="text-slate-muted">/</span>
              <span className="text-slate-muted font-mono text-xs">{record.external_id}</span>
            </>
          )}
        </div>
        <p className="text-sm text-rose-400 truncate">{record.error_message}</p>
        <div className="flex items-center gap-3 mt-1 text-xs text-slate-muted">
          <span>Retries: {record.retry_count}/{record.max_retries}</span>
          <span>{formatRelativeTime(new Date(record.created_at))}</span>
        </div>
      </div>
      <StatusBadge isResolved={record.is_resolved} />
      <div className="flex items-center gap-1">
        <Button
          onClick={() => onView(record.id)}
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated"
          title="View details"
        >
          <Eye className="w-4 h-4" />
        </Button>
        {!record.is_resolved && record.retry_count < record.max_retries && (
          <Button
            onClick={() => onRetry(record.id)}
            className="p-2 text-slate-muted hover:text-blue-400 hover:bg-blue-500/10"
            title="Retry"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        )}
        {!record.is_resolved && (
          <Button
            onClick={() => onResolve(record.id)}
            className="p-2 text-slate-muted hover:text-emerald-400 hover:bg-emerald-500/10"
            title="Mark resolved"
          >
            <CheckCircle2 className="w-4 h-4" />
          </Button>
        )}
        <Button
          onClick={() => onDelete(record.id)}
          className="p-2 text-slate-muted hover:text-rose-400 hover:bg-rose-500/10"
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

function DetailModal({
  recordId,
  onClose,
}: {
  recordId: number | null;
  onClose: () => void;
}) {
  const { data: record, isLoading } = useSWR(
    recordId ? `dlq-record-${recordId}` : null,
    () => adminApi.getDlqRecord(recordId!)
  );

  if (!recordId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-card border border-slate-border rounded-xl max-w-3xl w-full max-h-[80vh] overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">Failed Record Details</h3>
          <Button onClick={onClose} className="text-slate-muted hover:text-foreground">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>
        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : record ? (
          <div className="p-5 overflow-y-auto max-h-[60vh] space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Source</p>
                <p className="text-foreground capitalize">{record.source}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Entity Type</p>
                <p className="text-foreground">{record.entity_type}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">External ID</p>
                <p className="text-foreground font-mono">{record.external_id || '-'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Retry Count</p>
                <p className="text-foreground">{record.retry_count} / {record.max_retries}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-muted uppercase mb-1">Error Message</p>
              <p className="text-rose-400 bg-rose-500/10 rounded p-3 text-sm">{record.error_message}</p>
            </div>
            {record.error_type && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Error Type</p>
                <p className="text-foreground font-mono text-sm">{record.error_type}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-slate-muted uppercase mb-1">Payload</p>
              <pre className="bg-slate-elevated rounded p-3 text-xs text-slate-muted overflow-x-auto">
                {JSON.stringify(JSON.parse(record.payload), null, 2)}
              </pre>
            </div>
            {record.resolution_notes && (
              <div>
                <p className="text-xs text-slate-muted uppercase mb-1">Resolution Notes</p>
                <p className="text-foreground">{record.resolution_notes}</p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function DlqPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope(['sync:read', 'admin:read']);
  const canFetch = !authLoading && !missingScope;

  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [resolvedFilter, setResolvedFilter] = useState<boolean | undefined>(false);
  const [selectedRecord, setSelectedRecord] = useState<number | null>(null);

  const {
    data: dlqData,
    isLoading,
    error,
    mutate: refetch,
  } = useSWR(
    canFetch ? ['dlq-records', sourceFilter, resolvedFilter] : null,
    () => adminApi.getDlqRecords({
      source: sourceFilter || undefined,
      is_resolved: resolvedFilter,
      limit: 100,
    })
  );

  const { data: stats } = useSWR(
    canFetch ? 'dlq-stats' : null,
    () => adminApi.getDlqStats()
  );

  const handleRetry = async (id: number) => {
    try {
      await adminApi.retryDlqRecord(id);
      refetch();
    } catch (err) {
      console.error('Failed to retry:', err);
    }
  };

  const handleResolve = async (id: number) => {
    const notes = window.prompt('Resolution notes (optional):');
    try {
      await adminApi.resolveDlqRecord(id, notes || undefined);
      refetch();
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this record?')) return;
    try {
      await adminApi.deleteDlqRecord(id);
      refetch();
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const handleRetryBatch = async () => {
    if (!window.confirm('Retry all unresolved records?')) return;
    try {
      const result = await adminApi.retryDlqBatch({ source: sourceFilter || undefined });
      alert(`Scheduled ${result.count} records for retry`);
      refetch();
    } catch (err) {
      console.error('Failed to retry batch:', err);
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
          <div className="p-3 bg-gradient-to-br from-rose-500/20 to-orange-500/20 rounded-xl">
            <AlertTriangle className="w-6 h-6 text-rose-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Failed Records (DLQ)</h1>
            <p className="text-slate-muted text-sm">
              View and manage failed sync records
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
          {dlqData && dlqData.items.some(r => !r.is_resolved) && (
            <Button
              onClick={handleRetryBatch}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Retry All
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Total" value={stats.total} icon={AlertTriangle} />
          <StatCard title="Unresolved" value={stats.unresolved} icon={XCircle} variant="danger" />
          <StatCard title="Resolved" value={stats.resolved} icon={CheckCircle2} variant="success" />
          <StatCard title="Pending Retry" value={stats.pending_retry} icon={RotateCcw} />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-muted" />
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
        <div className="flex items-center gap-2">
          <select
            value={resolvedFilter === undefined ? '' : resolvedFilter ? 'true' : 'false'}
            onChange={(e) => setResolvedFilter(e.target.value === '' ? undefined : e.target.value === 'true')}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="false">Unresolved</option>
            <option value="true">Resolved</option>
            <option value="">All</option>
          </select>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load records</p>
            <p className="text-rose-300/70 text-sm">{error.message}</p>
          </div>
        </div>
      )}

      {/* Records List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border">
          <h3 className="font-semibold text-foreground">
            Records ({dlqData?.total || 0})
          </h3>
        </div>

        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : dlqData && dlqData.items.length > 0 ? (
          <div className="divide-y divide-slate-border">
            {dlqData.items.map((record) => (
              <DlqRecordRow
                key={record.id}
                record={record}
                onRetry={handleRetry}
                onResolve={handleResolve}
                onView={setSelectedRecord}
                onDelete={handleDelete}
              />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-foreground font-medium">No failed records</p>
            <p className="text-slate-muted text-sm">All sync operations are healthy</p>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <DetailModal
        recordId={selectedRecord}
        onClose={() => setSelectedRecord(null)}
      />
    </div>
  );
}
