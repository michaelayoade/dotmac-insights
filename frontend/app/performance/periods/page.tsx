'use client';

import { useState } from 'react';
import {
  Calendar,
  Plus,
  Play,
  Check,
  Clock,
  Archive,
  MoreVertical,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';
import { usePeriodList, useActivatePeriod, useStartScoring, useFinalizePeriod } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import type { EvaluationPeriod, PeriodStatus } from '@/lib/performance.types';
import { Button, FilterCard, FilterSelect, StatusPill } from '@/components/ui';

const STATUS_TONES: Record<PeriodStatus, StatusTone> = {
  draft: 'default',
  active: 'success',
  scoring: 'warning',
  review: 'info',
  finalized: 'info',
  archived: 'default',
};

export default function PeriodsPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [statusFilter, setStatusFilter] = useState<PeriodStatus | ''>('');

  const { data, isLoading, error, mutate } = usePeriodList({
    status: statusFilter || undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'code',
      header: 'Period',
      render: (item: EvaluationPeriod) => (
        <div>
          <Link
            href={`/performance/periods/${item.id}`}
            className="text-violet-400 hover:text-violet-300 font-medium"
          >
            {item.code}
          </Link>
          <p className="text-sm text-slate-400">{item.name}</p>
        </div>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (item: EvaluationPeriod) => (
        <span className="text-foreground-secondary capitalize">
          {item.period_type.replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'dates',
      header: 'Date Range',
      render: (item: EvaluationPeriod) => (
        <div className="text-sm">
          <span className="text-foreground-secondary">{formatDate(item.start_date)}</span>
          <span className="text-slate-500 mx-1">to</span>
          <span className="text-foreground-secondary">{formatDate(item.end_date)}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: EvaluationPeriod) => (
        <StatusPill
          label={formatStatusLabel(item.status)}
          tone={STATUS_TONES[item.status] || 'default'}
        />
      ),
    },
    {
      key: 'scorecards',
      header: 'Scorecards',
      render: (item: EvaluationPeriod) => (
        <div className="text-sm">
          <span className="text-foreground font-medium">{item.scorecard_count}</span>
          <span className="text-slate-500 ml-1">total</span>
          {item.scorecard_count > 0 && (
            <div className="text-xs text-slate-400 mt-1">
              {item.computed_count} computed / {item.finalized_count} finalized
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: EvaluationPeriod) => (
        <Link
          href={`/performance/periods/${item.id}`}
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
          message="Failed to load evaluation periods"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Evaluation Periods</h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage performance evaluation cycles
          </p>
        </div>
        <Link
          href="/performance/periods/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-foreground rounded-lg hover:bg-violet-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Period
        </Link>
      </div>

      {/* Filters */}
      <FilterCard
        actions={statusFilter && (
          <Button
            onClick={() => {
              setStatusFilter('');
              setOffset(0);
            }}
            className="text-slate-400 text-sm hover:text-foreground transition-colors"
          >
            Clear filter
          </Button>
        )}
        iconClassName="text-violet-400"
        contentClassName="flex gap-3"
      >
        <FilterSelect
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as PeriodStatus | '');
            setOffset(0);
          }}
          className="focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="scoring">Scoring</option>
          <option value="review">Review</option>
          <option value="finalized">Finalized</option>
          <option value="archived">Archived</option>
        </FilterSelect>
      </FilterCard>

      {/* Status Summary */}
      <div className="flex gap-3 flex-wrap">
        {[
          { status: 'draft', icon: Clock, label: 'Draft' },
          { status: 'active', icon: Play, label: 'Active' },
          { status: 'scoring', icon: Calendar, label: 'Scoring' },
          { status: 'review', icon: Clock, label: 'Review' },
          { status: 'finalized', icon: Check, label: 'Finalized' },
        ].map((item) => {
          const count = data?.items.filter(p => p.status === item.status).length || 0;
          return (
            <Button
              key={item.status}
              onClick={() => setStatusFilter(item.status as PeriodStatus)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                statusFilter === item.status
                  ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                  : 'bg-slate-elevated text-slate-400 border border-slate-border hover:text-foreground'
              )}
            >
              <item.icon className="w-3.5 h-3.5" />
              {item.label}
              <span className="ml-1 text-xs opacity-70">({count})</span>
            </Button>
          );
        })}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No evaluation periods found"
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
