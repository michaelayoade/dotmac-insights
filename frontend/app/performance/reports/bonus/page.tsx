'use client';

import { useState } from 'react';
import {
  Award,
  Download,
  Users,
  DollarSign,
  Percent,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';
import { useBonusEligibility, usePeriodList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import type { BonusEligibility } from '@/lib/performance.types';

function formatScore(score: number | null): string {
  if (score === null) return '-';
  return score.toFixed(1);
}

function formatCurrency(amount: number | null): string {
  if (amount === null) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function BonusReportPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [periodId, setPeriodId] = useState<number>(0);
  const [departmentFilter, setDepartmentFilter] = useState('');

  const { data: periods } = usePeriodList({ limit: 100 });
  const { data: rawData, isLoading, error, mutate } = useBonusEligibility(periodId || 0);

  // Filter data by department if needed and slice for pagination
  const filteredData = rawData?.filter(item =>
    !departmentFilter || item.department?.toLowerCase().includes(departmentFilter.toLowerCase())
  ) ?? [];
  const data = filteredData.slice(offset, offset + limit);

  const columns = [
    {
      key: 'employee',
      header: 'Employee',
      render: (item: BonusEligibility) => (
        <div>
          <p className="text-white font-medium">{item.employee_name}</p>
          <p className="text-xs text-slate-400">{item.department || 'No department'}</p>
        </div>
      ),
    },
    {
      key: 'bonus_band',
      header: 'Bonus Band',
      render: (item: BonusEligibility) => (
        <span className="text-slate-300 text-sm">{item.bonus_band || '-'}</span>
      ),
    },
    {
      key: 'score',
      header: 'Score',
      align: 'right' as const,
      render: (item: BonusEligibility) => (
        <span className={cn(
          'font-bold text-lg',
          (item.final_score ?? 0) >= 85 && 'text-violet-400',
          (item.final_score ?? 0) >= 70 && (item.final_score ?? 0) < 85 && 'text-emerald-400',
          (item.final_score ?? 0) >= 50 && (item.final_score ?? 0) < 70 && 'text-amber-400',
          (item.final_score ?? 0) < 50 && 'text-red-400',
        )}>
          {formatScore(item.final_score)}
        </span>
      ),
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (item: BonusEligibility) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
          item.rating?.toLowerCase().includes('outstanding') && 'text-violet-400 bg-violet-400/10',
          item.rating?.toLowerCase().includes('exceeds') && 'text-emerald-400 bg-emerald-400/10',
          item.rating?.toLowerCase().includes('meets') && 'text-amber-400 bg-amber-400/10',
          item.rating?.toLowerCase().includes('below') && 'text-red-400 bg-red-400/10',
        )}>
          {item.rating || '-'}
        </span>
      ),
    },
    {
      key: 'eligible',
      header: 'Eligible',
      align: 'center' as const,
      render: (item: BonusEligibility) => (
        item.bonus_band ? (
          <span className="text-emerald-400">Yes</span>
        ) : (
          <span className="text-slate-500">No</span>
        )
      ),
    },
    {
      key: 'factor',
      header: 'Factor',
      align: 'right' as const,
      render: (item: BonusEligibility) => (
        <span className={cn(
          'font-mono',
          (item.bonus_factor ?? 0) > 1 && 'text-emerald-400',
          (item.bonus_factor ?? 0) === 1 && 'text-slate-300',
          (item.bonus_factor ?? 0) < 1 && 'text-amber-400',
        )}>
          {(item.bonus_factor ?? 0).toFixed(2)}x
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: BonusEligibility) => (
        <Link
          href={`/performance/employees/${item.employee_id}`}
          className="text-slate-400 hover:text-white p-1"
        >
          <ChevronRight className="w-4 h-4" />
        </Link>
      ),
    },
  ];

  // Calculate summary stats from filteredData (not paginated)
  const summary = filteredData.length > 0 ? {
    total: filteredData.length,
    eligible: filteredData.filter((i: BonusEligibility) => i.bonus_band).length,
    avgFactor: filteredData.length > 0
      ? filteredData.reduce((sum: number, i: BonusEligibility) => sum + (i.bonus_factor ?? 0), 0) / filteredData.length
      : 0,
  } : null;

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load bonus eligibility report"
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Bonus Eligibility Report</h1>
          <p className="text-sm text-slate-400 mt-1">
            Performance-based bonus calculations and eligibility
          </p>
        </div>
        <button
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition-colors"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center">
                <Users className="w-5 h-5 text-violet-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{summary.total}</p>
                <p className="text-sm text-slate-400">Total Employees</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Award className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{summary.eligible}</p>
                <p className="text-sm text-slate-400">Bonus Eligible</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <Percent className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{summary.avgFactor.toFixed(2)}x</p>
                <p className="text-sm text-slate-400">Avg Factor</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={periodId || ''}
          onChange={(e) => {
            setPeriodId(e.target.value ? Number(e.target.value) : 0);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Periods</option>
          {periods?.items.filter(p => ['finalized', 'review'].includes(p.status)).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Filter by department..."
          value={departmentFilter}
          onChange={(e) => {
            setDepartmentFilter(e.target.value);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        />
      </div>

      {/* Info Card */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-start gap-3">
          <DollarSign className="w-5 h-5 text-emerald-400 mt-0.5" />
          <div>
            <h3 className="font-medium text-white">Bonus Calculation</h3>
            <p className="text-sm text-slate-400 mt-1">
              Bonus eligibility and multipliers are calculated based on the active bonus policy.
              Employees must score above the minimum threshold (typically 50) to be eligible.
              The multiplier is determined by score bands defined in the policy.
            </p>
          </div>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data ?? []}
        keyField="employee_id"
        loading={isLoading}
        emptyMessage="No bonus eligibility data available"
      />

      {/* Pagination */}
      {filteredData.length > limit && (
        <Pagination
          total={filteredData.length}
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
