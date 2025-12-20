'use client';

import { useState } from 'react';
import {
  ClipboardCheck,
  User,
  ChevronRight,
  Clock,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useReviewQueue, usePeriodList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import type { ReviewQueueItem, ScorecardStatus } from '@/lib/performance.types';

function getStatusColor(status: ScorecardStatus): string {
  switch (status) {
    case 'computed': return 'text-cyan-400 bg-cyan-400/10';
    case 'in_review': return 'text-violet-400 bg-violet-400/10';
    default: return 'text-slate-400 bg-slate-400/10';
  }
}

function formatScore(score: number | null): string {
  if (score === null) return '-';
  return score.toFixed(1);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ReviewQueuePage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [periodId, setPeriodId] = useState<number | undefined>();

  const { data: periods } = usePeriodList({ limit: 100 });
  const { data, isLoading, error, mutate } = useReviewQueue({
    period_id: periodId,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'employee',
      header: 'Employee',
      render: (item: ReviewQueueItem) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center">
            <User className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <Link
              href={`/performance/scorecards/${item.scorecard_id}`}
              className="text-white font-medium hover:text-violet-400"
            >
              {item.employee_name}
            </Link>
            <p className="text-xs text-slate-400">{item.department || 'No department'}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'designation',
      header: 'Designation',
      render: (item: ReviewQueueItem) => (
        <span className="text-slate-300 text-sm">{item.designation || '-'}</span>
      ),
    },
    {
      key: 'period',
      header: 'Period',
      render: (item: ReviewQueueItem) => (
        <span className="text-slate-300 text-sm">{item.period_name}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: ReviewQueueItem) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium capitalize',
          getStatusColor(item.status)
        )}>
          {item.status.replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'score',
      header: 'Score',
      align: 'right' as const,
      render: (item: ReviewQueueItem) => (
        <span className={cn(
          'font-bold text-lg',
          item.total_score === null && 'text-slate-500',
          item.total_score !== null && item.total_score >= 70 && 'text-emerald-400',
          item.total_score !== null && item.total_score >= 50 && item.total_score < 70 && 'text-amber-400',
          item.total_score !== null && item.total_score < 50 && 'text-red-400',
        )}>
          {formatScore(item.total_score)}
        </span>
      ),
    },
    {
      key: 'submitted',
      header: 'Submitted',
      render: (item: ReviewQueueItem) => (
        <span className="text-slate-400 text-sm">{formatDate(item.submitted_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: ReviewQueueItem) => (
        <Link
          href={`/performance/scorecards/${item.scorecard_id}`}
          className="inline-flex items-center gap-1 text-violet-400 hover:text-violet-300 text-sm"
        >
          Review <ChevronRight className="w-4 h-4" />
        </Link>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load review queue"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Review Queue</h1>
          <p className="text-sm text-slate-400 mt-1">
            Scorecards pending manager review and approval
          </p>
        </div>
      </div>

      {/* Summary Stats */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{data.pending_count}</p>
                <p className="text-sm text-slate-400">Pending Review</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center">
                <ClipboardCheck className="w-5 h-5 text-violet-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{data.in_review_count}</p>
                <p className="text-sm text-slate-400">In Review</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-slate-500/20 flex items-center justify-center">
                <User className="w-5 h-5 text-slate-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{data.total}</p>
                <p className="text-sm text-slate-400">Total in Queue</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={periodId || ''}
          onChange={(e) => {
            setPeriodId(e.target.value ? Number(e.target.value) : undefined);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Periods</option>
          {periods?.items.filter(p => ['active', 'scoring', 'review'].includes(p.status)).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {/* Empty State */}
      {data && data.items.length === 0 && (
        <div className="text-center py-16 bg-slate-card border border-slate-border rounded-xl">
          <CheckCircle className="w-16 h-16 mx-auto mb-4 text-emerald-400 opacity-50" />
          <h2 className="text-xl font-semibold text-white mb-2">All Caught Up!</h2>
          <p className="text-slate-400">No scorecards pending review at this time.</p>
        </div>
      )}

      {/* Table */}
      {data && data.items.length > 0 && (
        <>
          <DataTable
            columns={columns}
            data={data.items}
            keyField="scorecard_id"
            loading={isLoading}
            emptyMessage="No scorecards in review queue"
          />

          {/* Pagination */}
          {data.total > limit && (
            <Pagination
              total={data.total}
              limit={limit}
              offset={offset}
              onPageChange={setOffset}
              onLimitChange={(newLimit) => {
                setLimit(newLimit);
                setOffset(0);
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
