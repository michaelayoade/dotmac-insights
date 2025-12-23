'use client';

import { useState } from 'react';
import {
  ClipboardCheck,
  Search,
  ChevronRight,
  User,
  Building2,
  Calendar,
} from 'lucide-react';
import Link from 'next/link';
import { useScorecardList, usePeriodList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import type { Scorecard, ScorecardStatus } from '@/lib/performance.types';
import { Button, FilterCard, FilterInput, FilterSelect, StatusPill } from '@/components/ui';

const STATUS_TONES: Record<ScorecardStatus, StatusTone> = {
  pending: 'default',
  computing: 'warning',
  computed: 'info',
  in_review: 'info',
  approved: 'success',
  disputed: 'danger',
  finalized: 'info',
};

function formatScore(score: number | null): string {
  if (score === null) return '-';
  return score.toFixed(1);
}

export default function ScorecardsPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [periodId, setPeriodId] = useState<number | undefined>();
  const [statusFilter, setStatusFilter] = useState<ScorecardStatus | ''>('');
  const [departmentFilter, setDepartmentFilter] = useState('');

  const { data: periods } = usePeriodList({ limit: 100 });
  const { data, isLoading, error, mutate } = useScorecardList({
    period_id: periodId,
    status: statusFilter || undefined,
    department: departmentFilter || undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'employee',
      header: 'Employee',
      render: (item: Scorecard) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center">
            <User className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <Link
              href={`/performance/scorecards/${item.id}`}
              className="text-foreground font-medium hover:text-violet-400"
            >
              {item.employee_name || 'Unknown'}
            </Link>
            <p className="text-xs text-slate-400">{item.employee_code}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'department',
      header: 'Department',
      render: (item: Scorecard) => (
        <div className="text-sm">
          <p className="text-foreground-secondary">{item.department || '-'}</p>
          <p className="text-xs text-slate-500">{item.designation || '-'}</p>
        </div>
      ),
    },
    {
      key: 'period',
      header: 'Period',
      render: (item: Scorecard) => (
        <div className="text-sm">
          <p className="text-foreground-secondary">{item.period_name}</p>
          <p className="text-xs text-slate-500 font-mono">{item.period_code}</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: Scorecard) => (
        <StatusPill
          label={formatStatusLabel(item.status)}
          tone={STATUS_TONES[item.status] || 'default'}
        />
      ),
    },
    {
      key: 'score',
      header: 'Score',
      align: 'right' as const,
      render: (item: Scorecard) => (
        <div className="text-right">
          <p className={cn(
            'text-lg font-bold',
            item.total_weighted_score === null && 'text-slate-500',
            item.total_weighted_score !== null && item.total_weighted_score >= 70 && 'text-emerald-400',
            item.total_weighted_score !== null && item.total_weighted_score >= 50 && item.total_weighted_score < 70 && 'text-amber-400',
            item.total_weighted_score !== null && item.total_weighted_score < 50 && 'text-red-400',
          )}>
            {formatScore(item.total_weighted_score)}
          </p>
          {item.final_rating && (
            <p className="text-xs text-slate-400">{item.final_rating}</p>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: Scorecard) => (
        <Link
          href={`/performance/scorecards/${item.id}`}
          className="text-slate-400 hover:text-foreground p-1"
        >
          <ChevronRight className="w-4 h-4" />
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
          message="Failed to load scorecards"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Employee Scorecards</h1>
          <p className="text-sm text-slate-400 mt-1">
            View and manage performance scorecards
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={(periodId || statusFilter || departmentFilter) && (
          <Button
            onClick={() => {
              setPeriodId(undefined);
              setStatusFilter('');
              setDepartmentFilter('');
              setOffset(0);
            }}
            className="text-slate-400 text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        iconClassName="text-violet-400"
        contentClassName="flex gap-3 flex-wrap"
      >
        <FilterSelect
          value={periodId || ''}
          onChange={(e) => {
            setPeriodId(e.target.value ? Number(e.target.value) : undefined);
            setOffset(0);
          }}
          className="focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Periods</option>
          {periods?.items.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.status})
            </option>
          ))}
        </FilterSelect>
        <FilterSelect
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ScorecardStatus | '');
            setOffset(0);
          }}
          className="focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="computing">Computing</option>
          <option value="computed">Computed</option>
          <option value="in_review">In Review</option>
          <option value="approved">Approved</option>
          <option value="finalized">Finalized</option>
        </FilterSelect>
        <FilterInput
          type="text"
          placeholder="Filter by department..."
          value={departmentFilter}
          onChange={(e) => {
            setDepartmentFilter(e.target.value);
            setOffset(0);
          }}
          className="placeholder:text-slate-500 focus:ring-2 focus:ring-violet-500/50"
        />
      </FilterCard>

      {/* Summary Stats */}
      {data && (
        <div className="flex gap-3 flex-wrap text-sm">
          <div className="px-3 py-1.5 bg-slate-elevated rounded-lg border border-slate-border">
            <span className="text-slate-400">Total:</span>
            <span className="text-foreground font-medium ml-1">{data.total}</span>
          </div>
        </div>
      )}

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No scorecards found"
      />

      {/* Pagination */}
      {data && data.total > limit && (
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
    </div>
  );
}
