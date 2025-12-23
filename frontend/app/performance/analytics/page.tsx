'use client';

import { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  Building2,
  Calendar,
  Download,
} from 'lucide-react';
import { usePerformanceTrends, useScoreDistribution, usePeriodList, useKRABreakdown } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn } from '@/lib/utils';
import { Button, FilterCard, FilterInput, FilterSelect } from '@/components/ui';

function formatScore(score: number | null): string {
  if (score === null) return '-';
  return score.toFixed(1);
}

export default function AnalyticsPage() {
  const [periodId, setPeriodId] = useState<number | undefined>();
  const [departmentFilter, setDepartmentFilter] = useState('');

  const { data: periods } = usePeriodList({ limit: 100 });
  const { data: trends, isLoading: trendsLoading, error: trendsError, mutate: mutateTrends } = usePerformanceTrends({
    periods: 6,
    department: departmentFilter || undefined,
  });
  const { data: distribution, isLoading: distLoading, error: distError } = useScoreDistribution(
    {
      period_id: periodId,
      department: departmentFilter || undefined,
    }
  );
  const { data: kraBreakdown, isLoading: kraLoading, error: kraError } = useKRABreakdown({
    period_id: periodId,
    department: departmentFilter || undefined,
  });

  const isLoading = trendsLoading || distLoading || kraLoading;
  const error = trendsError || distError || kraError;

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load analytics"
          error={error as Error}
          onRetry={() => mutateTrends()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Performance Analytics</h1>
          <p className="text-sm text-slate-400 mt-1">
            Trends, distributions, and insights across periods
          </p>
        </div>
        <Button
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated text-foreground rounded-lg hover:bg-slate-elevated/80 transition-colors border border-slate-border"
        >
          <Download className="w-4 h-4" />
          Export Report
        </Button>
      </div>

      {/* Filters */}
      <FilterCard contentClassName="flex gap-3 flex-wrap" iconClassName="text-violet-400">
        <FilterSelect
          value={periodId || ''}
          onChange={(e) => setPeriodId(e.target.value ? Number(e.target.value) : undefined)}
          className="focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Periods</option>
          {periods?.items.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </FilterSelect>
        <FilterInput
          type="text"
          placeholder="Filter by department..."
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          className="placeholder:text-slate-500 focus:ring-2 focus:ring-violet-500/50"
        />
      </FilterCard>

      {/* Trends Chart */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <h3 className="font-medium text-foreground mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-violet-400" />
          Performance Trends
        </h3>
        {trends && trends.length > 0 ? (
          <div className="space-y-4">
            {/* Simple bar representation */}
            <div className="grid grid-cols-6 gap-2">
              {trends.map((point, idx) => {
                const maxScore = 100;
                const heightPercent = (point.avg_score / maxScore) * 100;
                return (
                  <div key={idx} className="flex flex-col items-center">
                    <div className="h-32 w-full flex items-end justify-center">
                      <div
                        className={cn(
                          'w-8 rounded-t transition-all',
                          point.avg_score >= 70 && 'bg-emerald-500',
                          point.avg_score >= 50 && point.avg_score < 70 && 'bg-amber-500',
                          point.avg_score < 50 && 'bg-red-500',
                        )}
                        style={{ height: `${heightPercent}%` }}
                      />
                    </div>
                    <p className="text-xs text-slate-400 mt-2 text-center truncate w-full">
                      {point.period_name}
                    </p>
                    <p className="text-sm font-medium text-foreground">
                      {formatScore(point.avg_score)}
                    </p>
                  </div>
                );
              })}
            </div>
            {/* Trend indicator */}
            {trends.length >= 2 && (
              <div className="flex items-center gap-2 pt-4 border-t border-slate-border">
                {trends[trends.length - 1].avg_score > trends[trends.length - 2].avg_score ? (
                  <>
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    <span className="text-emerald-400 text-sm">
                      +{(trends[trends.length - 1].avg_score - trends[trends.length - 2].avg_score).toFixed(1)} from previous period
                    </span>
                  </>
                ) : trends[trends.length - 1].avg_score < trends[trends.length - 2].avg_score ? (
                  <>
                    <TrendingDown className="w-4 h-4 text-red-400" />
                    <span className="text-red-400 text-sm">
                      {(trends[trends.length - 1].avg_score - trends[trends.length - 2].avg_score).toFixed(1)} from previous period
                    </span>
                  </>
                ) : (
                  <span className="text-slate-400 text-sm">No change from previous period</span>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="text-slate-400 text-center py-8">No trend data available</p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Score Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-foreground mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-violet-400" />
            Score Distribution
          </h3>
          {distribution ? (
            <div className="space-y-3">
              {[
                { label: 'Outstanding (85-100)', key: 'outstanding', color: 'violet' },
                { label: 'Exceeds (70-84)', key: 'exceeds', color: 'emerald' },
                { label: 'Meets (50-69)', key: 'meets', color: 'amber' },
                { label: 'Below (0-49)', key: 'below', color: 'red' },
              ].map((band) => {
                const count = distribution?.[band.key as keyof typeof distribution] ?? 0;
                const total =
                  (distribution?.outstanding ?? 0) +
                  (distribution?.exceeds ?? 0) +
                  (distribution?.meets ?? 0) +
                  (distribution?.below ?? 0) || 1;
                const percent = Math.round((count / total) * 100);
                return (
                  <div key={band.key} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-foreground-secondary">{band.label}</span>
                      <span className="text-slate-400">{count} ({percent}%)</span>
                    </div>
                    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          band.color === 'violet' && 'bg-violet-500',
                          band.color === 'emerald' && 'bg-emerald-500',
                          band.color === 'amber' && 'bg-amber-500',
                          band.color === 'red' && 'bg-red-500',
                        )}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-slate-400 text-center py-8">No distribution data available</p>
          )}
        </div>

        {/* KRA Breakdown */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-foreground mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            KRA Performance
          </h3>
          {kraBreakdown && kraBreakdown.length > 0 ? (
            <div className="space-y-3">
              {kraBreakdown.map((kra) => (
                <div key={kra.kra_id || kra.kra_code || kra.kra_name} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-foreground font-medium truncate">{kra.kra_name}</p>
                    <p className="text-xs text-slate-500">{kra.employee_count ?? kra.count ?? 0} employees</p>
                  </div>
                  <div className="text-right">
                    <p className={cn(
                      'text-lg font-bold',
                      (kra.avg_score ?? 0) >= 70 && 'text-emerald-400',
                      (kra.avg_score ?? 0) >= 50 && (kra.avg_score ?? 0) < 70 && 'text-amber-400',
                      (kra.avg_score ?? 0) < 50 && 'text-red-400',
                    )}>
                      {formatScore(kra.avg_score)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-center py-8">No KRA data available</p>
          )}
        </div>
      </div>

      {/* Department Comparison */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <h3 className="font-medium text-foreground mb-4 flex items-center gap-2">
          <Building2 className="w-5 h-5 text-amber-400" />
          Department Overview
        </h3>
        <p className="text-slate-400 text-sm">
          Department-level analytics will show comparative performance across organizational units.
          Select a specific period above to view department breakdowns.
        </p>
      </div>
    </div>
  );
}
