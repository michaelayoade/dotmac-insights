'use client';

import { useMemo } from 'react';
import {
  Award,
  Users,
  ClipboardCheck,
  TrendingUp,
  TrendingDown,
  Calendar,
  BarChart3,
  ArrowRight,
  Medal,
  AlertTriangle,
} from 'lucide-react';
import Link from 'next/link';
import { usePerformanceDashboard } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn } from '@/lib/utils';

function formatScore(score: number | null): string {
  if (score === null) return '-';
  return score.toFixed(1);
}

function getRatingColor(rating: string | null): string {
  if (!rating) return 'text-slate-400';
  const lower = rating.toLowerCase();
  if (lower.includes('outstanding')) return 'text-violet-400';
  if (lower.includes('exceeds')) return 'text-emerald-400';
  if (lower.includes('meets')) return 'text-amber-400';
  return 'text-red-400';
}

export default function PerformanceDashboardPage() {
  const { data, isLoading, error, mutate } = usePerformanceDashboard();

  const progressPercent = useMemo(() => {
    if (!data || data.scorecards_generated === 0) return 0;
    return Math.round((data.scorecards_finalized / data.scorecards_generated) * 100);
  }, [data]);

  const computedPercent = useMemo(() => {
    if (!data || data.scorecards_generated === 0) return 0;
    return Math.round((data.scorecards_computed / data.scorecards_generated) * 100);
  }, [data]);

  if (isLoading) {
    return <LoadingState />;
  }

  if (!data) {
    return (
      <div className="space-y-6">
        {error && (
          <ErrorDisplay
            message="Failed to load performance dashboard"
            error={error as Error}
            onRetry={() => mutate()}
          />
        )}
        <div className="text-center py-16 text-slate-400">
          <Award className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <h2 className="text-xl font-semibold text-white mb-2">No Active Period</h2>
          <p className="mb-6">Create an evaluation period to get started with performance management.</p>
          <Link
            href="/performance/periods/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500/20 text-violet-400 rounded-lg hover:bg-violet-500/30 transition-colors"
          >
            <Calendar className="w-4 h-4" />
            Create Period
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load performance dashboard"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Active Period Banner */}
      {data.active_period && (
        <div className="bg-gradient-to-r from-violet-500/20 to-purple-500/20 border border-violet-500/30 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-violet-400" />
              <div>
                <p className="text-sm text-slate-400">Active Period</p>
                <p className="text-white font-medium">{data.active_period.name}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-slate-400 uppercase tracking-wider">Status</p>
                <p className={cn(
                  'font-medium capitalize',
                  data.active_period.status === 'active' && 'text-emerald-400',
                  data.active_period.status === 'scoring' && 'text-amber-400',
                  data.active_period.status === 'review' && 'text-cyan-400',
                  data.active_period.status === 'finalized' && 'text-violet-400',
                )}>
                  {data.active_period.status}
                </p>
              </div>
              <Link
                href={`/performance/periods/${data.active_period.id}`}
                className="flex items-center gap-1 text-violet-400 hover:text-violet-300 text-sm"
              >
                View Period <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <Users className="w-5 h-5 text-slate-400" />
            <span className="text-xs text-slate-500">Employees</span>
          </div>
          <p className="text-2xl font-bold text-white">{data.total_employees}</p>
          <p className="text-sm text-slate-400">Total active employees</p>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <ClipboardCheck className="w-5 h-5 text-cyan-400" />
            <span className="text-xs text-slate-500">Scorecards</span>
          </div>
          <p className="text-2xl font-bold text-white">{data.scorecards_generated}</p>
          <p className="text-sm text-slate-400">{data.scorecards_computed} computed ({computedPercent}%)</p>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <BarChart3 className="w-5 h-5 text-amber-400" />
            <span className="text-xs text-slate-500">In Review</span>
          </div>
          <p className="text-2xl font-bold text-white">{data.scorecards_in_review}</p>
          <p className="text-sm text-slate-400">Awaiting approval</p>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <Award className="w-5 h-5 text-emerald-400" />
            <span className="text-xs text-slate-500">Average</span>
          </div>
          <p className="text-2xl font-bold text-white">{formatScore(data.avg_score)}</p>
          <p className="text-sm text-slate-400">Avg performance score</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-white">Period Progress</h3>
          <span className="text-sm text-slate-400">{progressPercent}% finalized</span>
        </div>
        <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-slate-500">
          <span>{data.scorecards_finalized} finalized</span>
          <span>{data.scorecards_generated - data.scorecards_finalized} remaining</span>
        </div>
      </div>

      {/* Score Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-violet-400" />
            Score Distribution
          </h3>
          <div className="space-y-3">
            {[
              { label: 'Outstanding (85-100)', count: data.score_distribution.outstanding, color: 'violet' },
              { label: 'Exceeds (70-84)', count: data.score_distribution.exceeds, color: 'emerald' },
              { label: 'Meets (50-69)', count: data.score_distribution.meets, color: 'amber' },
              { label: 'Below (0-49)', count: data.score_distribution.below, color: 'red' },
            ].map((band) => {
              const total = Object.values(data.score_distribution).reduce((a, b) => a + b, 0) || 1;
              const percent = Math.round((band.count / total) * 100);
              return (
                <div key={band.label} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-300">{band.label}</span>
                    <span className="text-slate-400">{band.count} ({percent}%)</span>
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
        </div>

        {/* Quick Actions */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-white mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-3">
            <Link
              href="/performance/reviews"
              className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg hover:bg-slate-elevated/80 transition-colors"
            >
              <ClipboardCheck className="w-5 h-5 text-amber-400" />
              <div>
                <p className="text-sm font-medium text-white">Review Queue</p>
                <p className="text-xs text-slate-400">{data.scorecards_in_review} pending</p>
              </div>
            </Link>
            <Link
              href="/performance/scorecards"
              className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg hover:bg-slate-elevated/80 transition-colors"
            >
              <Users className="w-5 h-5 text-cyan-400" />
              <div>
                <p className="text-sm font-medium text-white">All Scorecards</p>
                <p className="text-xs text-slate-400">{data.scorecards_generated} total</p>
              </div>
            </Link>
            <Link
              href="/performance/analytics"
              className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg hover:bg-slate-elevated/80 transition-colors"
            >
              <BarChart3 className="w-5 h-5 text-violet-400" />
              <div>
                <p className="text-sm font-medium text-white">Analytics</p>
                <p className="text-xs text-slate-400">Trends & insights</p>
              </div>
            </Link>
            <Link
              href="/performance/reports/bonus"
              className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg hover:bg-slate-elevated/80 transition-colors"
            >
              <Award className="w-5 h-5 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-white">Bonus Report</p>
                <p className="text-xs text-slate-400">Eligibility calc</p>
              </div>
            </Link>
          </div>
        </div>
      </div>

      {/* Top Performers & Improvement Needed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Performers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-white mb-4 flex items-center gap-2">
            <Medal className="w-5 h-5 text-amber-400" />
            Top Performers
          </h3>
          {data.top_performers.length === 0 ? (
            <p className="text-slate-400 text-sm">No scorecards computed yet</p>
          ) : (
            <div className="space-y-3">
              {data.top_performers.map((emp, idx) => (
                <div key={emp.employee_id} className="flex items-center gap-3">
                  <div className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
                    idx === 0 && 'bg-amber-500/20 text-amber-400',
                    idx === 1 && 'bg-slate-400/20 text-slate-300',
                    idx === 2 && 'bg-orange-500/20 text-orange-400',
                    idx > 2 && 'bg-slate-elevated text-slate-400',
                  )}>
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{emp.employee_name}</p>
                    <p className="text-xs text-slate-400">{emp.department || 'No department'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-emerald-400">{formatScore(emp.score)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Improvement Needed */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="font-medium text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            Needs Improvement
          </h3>
          {data.improvement_needed.length === 0 ? (
            <p className="text-slate-400 text-sm">No employees below threshold</p>
          ) : (
            <div className="space-y-3">
              {data.improvement_needed.map((emp) => (
                <div key={emp.employee_id} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{emp.employee_name}</p>
                    <p className="text-xs text-slate-400">{emp.department || 'No department'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-red-400">{formatScore(emp.score)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
          {data.improvement_needed.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-border">
              <p className="text-xs text-slate-400">
                Consider scheduling coaching sessions or PIP for employees scoring below 50.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
