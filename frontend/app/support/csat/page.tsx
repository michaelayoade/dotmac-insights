'use client';

import { useState } from 'react';
import {
  Smile,
  Frown,
  Meh,
  Star,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  MessageSquare,
  Loader2,
  CheckCircle,
  XCircle,
  ThumbsUp,
} from 'lucide-react';
import {
  useSupportCsatAgentPerformance,
  useSupportCsatSummary,
  useSupportCsatSurveys,
  useSupportCsatTrends,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { FilterCard, FilterSelect } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

// =============================================================================
// UTILITY COMPONENTS
// =============================================================================

function RatingStars({ rating, size = 'md' }: { rating: number; size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'w-3 h-3', md: 'w-4 h-4', lg: 'w-5 h-5' };
  const fullStars = Math.floor(rating);
  const hasHalf = rating - fullStars >= 0.5;

  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={cn(
            sizes[size],
            star <= fullStars
              ? 'text-amber-400 fill-amber-400'
              : star === fullStars + 1 && hasHalf
                ? 'text-amber-400 fill-amber-400/50'
                : 'text-slate-muted'
          )}
        />
      ))}
    </div>
  );
}

function SatisfactionGauge({ rating }: { rating: number }) {
  const maxRating = 5;
  const pct = (rating / maxRating) * 100;
  const color = rating >= 4 ? '#10B981' : rating >= 3 ? '#F59E0B' : '#EF4444';
  const face = rating >= 4 ? Smile : rating >= 3 ? Meh : Frown;
  const Face = face;

  const radius = 45;
  const circumference = Math.PI * radius; // Half circle
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="relative w-32 h-20 mx-auto">
      <svg className="w-full h-full" viewBox="0 0 100 60">
        {/* Background arc */}
        <path
          d="M 5 55 A 45 45 0 0 1 95 55"
          fill="none"
          stroke="#1e293b"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          d="M 5 55 A 45 45 0 0 1 95 55"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 flex flex-col items-center">
        <Face className="w-6 h-6" style={{ color }} />
        <span className="text-xl font-bold text-foreground">{rating.toFixed(2)}</span>
      </div>
    </div>
  );
}

function ProgressBar({ value, max, color = 'bg-teal-electric' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

function MiniTrendChart({ data, valueKey, labelKey }: { data: any[]; valueKey: string; labelKey: string }) {
  const maxValue = Math.max(...data.map((d) => d[valueKey] || 0), 1);

  return (
    <div className="flex items-end gap-2 h-20">
      {data.map((item, idx) => {
        const val = item[valueKey] || 0;
        const height = (val / maxValue) * 100;
        const color = val >= 4 ? 'bg-emerald-500' : val >= 3 ? 'bg-amber-500' : 'bg-rose-500';
        return (
          <div key={idx} className="flex-1 flex flex-col items-center gap-1">
            <span className="text-[10px] text-slate-muted">{val.toFixed(1)}</span>
            <div
              className={cn('w-full rounded-t transition-all', color)}
              style={{ height: `${Math.max(height, 8)}%` }}
              title={`${item[labelKey]}: ${val}`}
            />
            <span className="text-[9px] text-slate-muted">{String(item[labelKey]).slice(-5)}</span>
          </div>
        );
      })}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function SupportCsatPage() {
  const [days, setDays] = useState(30);

  const { data: surveys, isLoading: surveysLoading } = useSupportCsatSurveys({ active_only: false });
  const { data: summary, isLoading: summaryLoading } = useSupportCsatSummary({ days });
  const { data: agents } = useSupportCsatAgentPerformance({ days });
  const { data: trends } = useSupportCsatTrends({ months: 6 });

  const activeSurveys = surveys?.filter((s: any) => s.is_active) || [];
  const avgRating = summary?.average_rating || 0;
  const responseRate = summary?.response_rate || 0;
  const totalResponses = summary?.total_responses || 0;

  // Calculate trend direction
  const latestTrend = trends?.[trends.length - 1];
  const prevTrend = trends?.[trends.length - 2];
  const trendDiff = latestTrend && prevTrend ? latestTrend.avg_rating - prevTrend.avg_rating : 0;

  // Agent stats
  const topAgents = [...(agents || [])].sort((a, b) => b.avg_rating - a.avg_rating).slice(0, 5);
  const bottomAgents = [...(agents || [])].sort((a, b) => a.avg_rating - b.avg_rating).slice(0, 3);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <Smile className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">CSAT & Feedback</h1>
            <p className="text-slate-muted text-sm">Customer satisfaction surveys, responses & trends</p>
          </div>
        </div>
      </div>

      {/* Filter */}
      <FilterCard title="Time Range" contentClassName="flex items-center gap-4">
        <div>
          <label className="text-xs text-slate-muted mb-1 block">Period (days)</label>
          <FilterSelect
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
          </FilterSelect>
        </div>
      </FilterCard>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Average Rating"
          value={avgRating.toFixed(2)}
          subtitle="out of 5.0"
          icon={Star}
          colorClass={avgRating >= 4 ? 'text-emerald-400' : avgRating >= 3 ? 'text-amber-400' : 'text-rose-400'}
          loading={summaryLoading}
        />
        <StatCard
          title="Total Responses"
          value={totalResponses}
          subtitle={`last ${days} days`}
          icon={MessageSquare}
          colorClass="text-blue-400"
          loading={summaryLoading}
        />
        <StatCard
          title="Response Rate"
          value={`${responseRate.toFixed(1)}%`}
          subtitle="of sent surveys"
          icon={ThumbsUp}
          colorClass="text-violet-400"
          loading={summaryLoading}
        />
      </div>

      {/* Satisfaction Gauge & Trend Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Gauge */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Smile className="w-4 h-4 text-amber-400" />
            <h3 className="text-foreground font-semibold">Satisfaction Score</h3>
          </div>
          <SatisfactionGauge rating={avgRating} />
          <div className="mt-4 flex justify-center">
            <RatingStars rating={avgRating} size="lg" />
          </div>
          {trendDiff !== 0 && (
            <div className={cn('mt-3 text-xs text-center flex items-center justify-center gap-1', trendDiff > 0 ? 'text-emerald-400' : 'text-rose-400')}>
              {trendDiff > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{trendDiff > 0 ? '+' : ''}{trendDiff.toFixed(2)} vs last month</span>
            </div>
          )}
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-elevated rounded-lg p-2">
              <Smile className="w-4 h-4 text-emerald-400 mx-auto" />
              <p className="text-xs text-slate-muted mt-1">Satisfied</p>
              <p className="text-sm font-bold text-foreground">
                {agents?.filter((a: any) => a.satisfaction_pct >= 80).length || 0}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-2">
              <Meh className="w-4 h-4 text-amber-400 mx-auto" />
              <p className="text-xs text-slate-muted mt-1">Neutral</p>
              <p className="text-sm font-bold text-foreground">
                {agents?.filter((a: any) => a.satisfaction_pct >= 50 && a.satisfaction_pct < 80).length || 0}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-2">
              <Frown className="w-4 h-4 text-rose-400 mx-auto" />
              <p className="text-xs text-slate-muted mt-1">Unhappy</p>
              <p className="text-sm font-bold text-foreground">
                {agents?.filter((a: any) => a.satisfaction_pct < 50).length || 0}
              </p>
            </div>
          </div>
        </div>

        {/* Trend Chart */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Rating Trend (6 months)</h3>
          </div>
          {trends?.length ? (
            <>
              <MiniTrendChart data={trends} valueKey="avg_rating" labelKey="period" />
              <div className="mt-4 grid grid-cols-2 gap-4 text-center">
                <div>
                  <p className="text-xs text-slate-muted">Latest</p>
                  <p className="text-lg font-bold text-foreground">{latestTrend?.avg_rating?.toFixed(2) ?? '-'}</p>
                  <p className="text-[10px] text-slate-muted">{latestTrend?.response_count ?? 0} responses</p>
                </div>
                <div>
                  <p className="text-xs text-slate-muted">6-Month Avg</p>
                  <p className="text-lg font-bold text-foreground">
                    {trends.length
                      ? (trends.reduce((s: number, t: any) => s + (t.avg_rating || 0), 0) / trends.length).toFixed(2)
                      : '-'}
                  </p>
                </div>
              </div>
            </>
          ) : (
            <p className="text-slate-muted text-sm text-center py-8">No trend data available</p>
          )}
        </div>
      </div>

      {/* Agent Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Performers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Star className="w-4 h-4 text-amber-400" />
            <h3 className="text-foreground font-semibold">Top Performers</h3>
          </div>
          {topAgents.length ? (
            <div className="space-y-3">
              {topAgents.map((agent, idx) => (
                <div key={agent.agent_id} className="flex items-center gap-3">
                  <div className={cn(
                    'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                    idx === 0 ? 'bg-amber-500/20 text-amber-400' :
                    idx === 1 ? 'bg-slate-400/20 text-foreground-secondary' :
                    idx === 2 ? 'bg-orange-600/20 text-orange-400' :
                    'bg-slate-elevated text-slate-muted'
                  )}>
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-foreground text-sm truncate">{agent.agent_name || `Agent ${agent.agent_id}`}</span>
                      <div className="flex items-center gap-2">
                        <RatingStars rating={agent.avg_rating} size="sm" />
                        <span className="text-sm font-mono text-foreground">{agent.avg_rating.toFixed(2)}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-1 text-xs text-slate-muted">
                      <span>{agent.response_count} responses</span>
                      <span className={cn(agent.satisfaction_pct >= 80 ? 'text-emerald-400' : 'text-amber-400')}>
                        {agent.satisfaction_pct.toFixed(0)}% satisfied
                      </span>
                    </div>
                    <ProgressBar value={agent.satisfaction_pct} max={100} color="bg-emerald-500" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm text-center py-4">No agent data</p>
          )}
        </div>

        {/* Needs Improvement */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-cyan-400" />
            <h3 className="text-foreground font-semibold">All Agents ({days}d)</h3>
          </div>
          {agents?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-muted text-left">
                    <th className="pb-2">Agent</th>
                    <th className="pb-2 text-right">Rating</th>
                    <th className="pb-2 text-right">Responses</th>
                    <th className="pb-2 text-right">Satisfaction</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent: any) => (
                    <tr key={agent.agent_id} className="border-t border-slate-border/40">
                      <td className="py-2 text-foreground truncate max-w-[120px]">
                        {agent.agent_name || `Agent ${agent.agent_id}`}
                      </td>
                      <td className="py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Star className={cn(
                            'w-3 h-3',
                            agent.avg_rating >= 4 ? 'text-amber-400 fill-amber-400' : 'text-slate-muted'
                          )} />
                          <span className="font-mono text-foreground">{agent.avg_rating.toFixed(2)}</span>
                        </div>
                      </td>
                      <td className="py-2 text-right font-mono text-slate-muted">{agent.response_count}</td>
                      <td className="py-2 text-right">
                        <span className={cn(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          agent.satisfaction_pct >= 80 ? 'bg-emerald-500/20 text-emerald-400' :
                          agent.satisfaction_pct >= 50 ? 'bg-amber-500/20 text-amber-400' :
                          'bg-rose-500/20 text-rose-400'
                        )}>
                          {agent.satisfaction_pct.toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm text-center py-4">No agent data</p>
          )}
        </div>
      </div>

      {/* Surveys */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Surveys</h3>
          </div>
          <span className="text-xs text-slate-muted">
            {activeSurveys.length} active / {surveys?.length || 0} total
          </span>
        </div>
        {surveysLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : surveys?.length ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {surveys.map((survey: any) => (
              <div
                key={survey.id}
                className={cn(
                  'rounded-lg border p-4',
                  survey.is_active
                    ? 'border-emerald-500/30 bg-emerald-500/5'
                    : 'border-slate-border bg-slate-elevated'
                )}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-foreground font-semibold">{survey.name}</p>
                    <p className="text-xs text-slate-muted capitalize mt-0.5">
                      {survey.survey_type?.replace(/_/g, ' ') || 'General'}
                    </p>
                  </div>
                  {survey.is_active ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-slate-muted" />
                  )}
                </div>
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-muted">
                  <span className="px-2 py-0.5 rounded bg-slate-elevated">
                    Trigger: {survey.trigger || 'Manual'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-muted text-sm text-center py-8">No surveys configured</p>
        )}
      </div>
    </div>
  );
}
