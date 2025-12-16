'use client';

import { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  BarChart3,
  Activity,
  TrendingUp,
  TrendingDown,
  Clock,
  AlertTriangle,
  Users,
  Target,
  Calendar,
  Filter,
  Loader2,
  CheckCircle2,
  XCircle,
  Zap,
  MapPin,
} from 'lucide-react';
import {
  useSupportDashboard,
  useSupportAnalyticsVolumeTrend,
  useSupportAnalyticsResolutionTime,
  useSupportAnalyticsByCategory,
  useSupportAnalyticsSlaPerformance,
  useSupportInsightsPatterns,
  useSupportInsightsAgentPerformance,
  useSupportSlaBreachesSummary,
  useSupportRoutingQueueHealth,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';

// Chart styling constants
const CHART_COLORS = ['#2dd4bf', '#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ec4899'];
const TOOLTIP_STYLE = {
  contentStyle: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' },
  labelStyle: { color: '#f8fafc' },
};

// =============================================================================
// UTILITY COMPONENTS
// =============================================================================

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass = 'text-teal-electric',
  trend,
  loading,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  trend?: { value: number; positive?: boolean };
  loading?: boolean;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-slate-muted text-sm">{title}</p>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <p className={cn('text-2xl font-bold', colorClass)}>{value}</p>
          )}
          {subtitle && <p className="text-slate-muted text-xs">{subtitle}</p>}
          {trend && (
            <div className={cn('flex items-center gap-1 text-xs', trend.positive ? 'text-emerald-400' : 'text-rose-400')}>
              {trend.positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{Math.abs(trend.value).toFixed(1)}%</span>
            </div>
          )}
        </div>
        <div className={cn('p-2 rounded-lg bg-slate-elevated')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-4 h-4 text-teal-electric" />}
        <div>
          <h3 className="text-white font-semibold">{title}</h3>
          {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
        </div>
      </div>
      {children}
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

function SlaGauge({ attainment }: { attainment: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (attainment / 100) * circumference;
  const color = attainment >= 90 ? '#10B981' : attainment >= 70 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative w-28 h-28 mx-auto">
      <svg className="w-full h-full -rotate-90">
        <circle cx="56" cy="56" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{attainment.toFixed(0)}%</span>
        <span className="text-[10px] text-slate-muted">SLA</span>
      </div>
    </div>
  );
}

function HeatmapCell({ value, max }: { value: number; max: number }) {
  const intensity = max > 0 ? Math.min(value / max, 1) : 0;
  const bg = intensity > 0.7 ? 'bg-teal-500' : intensity > 0.4 ? 'bg-teal-600' : intensity > 0 ? 'bg-teal-700' : 'bg-slate-elevated';
  return (
    <div className={cn('w-8 h-8 rounded flex items-center justify-center text-xs font-mono', bg, intensity > 0.4 ? 'text-white' : 'text-slate-muted')}>
      {value || '-'}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function SupportAnalyticsPage() {
  const [months, setMonths] = useState(6);
  const [days, setDays] = useState(30);

  // Fetch all analytics data
  const { data: dashboard, isLoading: dashboardLoading } = useSupportDashboard();
  const { data: volumeTrend } = useSupportAnalyticsVolumeTrend({ months });
  const { data: resolutionTrend } = useSupportAnalyticsResolutionTime({ months });
  const { data: categoryBreakdown } = useSupportAnalyticsByCategory({ days });
  const { data: slaPerformance } = useSupportAnalyticsSlaPerformance({ months });
  const { data: patterns } = useSupportInsightsPatterns({ days });
  const { data: agentInsights } = useSupportInsightsAgentPerformance({ days });
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days });
  const { data: queueHealth } = useSupportRoutingQueueHealth();
  const qh = (queueHealth || {}) as any;
  const overdueDetail = (dashboard as any)?.overdue_detail || [];

  // Calculate trends
  const latestSla = slaPerformance?.[slaPerformance.length - 1];
  const prevSla = slaPerformance?.[slaPerformance.length - 2];
  const slaTrend = latestSla && prevSla ? latestSla.attainment_rate - prevSla.attainment_rate : 0;

  const latestVolume = volumeTrend?.[volumeTrend.length - 1];
  const prevVolume = volumeTrend?.[volumeTrend.length - 2];
  const volumeTrendPct = latestVolume && prevVolume && prevVolume.total > 0
    ? ((latestVolume.total - prevVolume.total) / prevVolume.total) * 100
    : 0;

  // Peak hour analysis
  const peakHour = patterns?.peak_hours?.[0];
  const peakDay = patterns?.peak_days?.[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Support Analytics</h1>
            <p className="text-slate-muted text-sm">Ticket volumes, SLA, resolution times & patterns</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Time Range</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div>
            <label className="text-xs text-slate-muted mb-1 block">Trend Months</label>
            <select
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value={3}>3 months</option>
              <option value={6}>6 months</option>
              <option value={12}>12 months</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-muted mb-1 block">Breakdown Days</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Total Tickets"
          value={dashboard?.tickets?.total ?? 0}
          icon={Activity}
          colorClass="text-blue-400"
          loading={dashboardLoading}
          trend={volumeTrendPct ? { value: volumeTrendPct, positive: volumeTrendPct < 0 } : undefined}
        />
        <MetricCard
          title="Open"
          value={dashboard?.tickets?.open ?? 0}
          subtitle={`${dashboard?.tickets?.on_hold ?? 0} on hold`}
          icon={AlertTriangle}
          colorClass="text-amber-400"
          loading={dashboardLoading}
        />
        <MetricCard
          title="Resolved"
          value={dashboard?.tickets?.resolved ?? 0}
          icon={CheckCircle2}
          colorClass="text-emerald-400"
          loading={dashboardLoading}
        />
        <MetricCard
          title="Overdue"
          value={dashboard?.metrics?.overdue_tickets ?? slaBreach?.currently_overdue ?? 0}
          subtitle={`${slaBreach?.total_breaches ?? 0} breached (${days}d)`}
          icon={XCircle}
          colorClass="text-rose-400"
          loading={dashboardLoading}
        />
        <MetricCard
          title="Unassigned"
          value={dashboard?.metrics?.unassigned_tickets ?? queueHealth?.unassigned_tickets ?? 0}
          subtitle={`${queueHealth?.total_agents ?? 0} agents`}
          icon={Users}
          colorClass="text-violet-400"
          loading={dashboardLoading}
        />
      </div>

      {/* SLA & Resolution Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* SLA Gauge */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">SLA Attainment</h3>
          </div>
          <SlaGauge attainment={dashboard?.sla?.attainment_rate ?? 0} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-center">
            <div>
              <p className="text-xs text-slate-muted">Met</p>
              <p className="text-lg font-bold text-emerald-400">{latestSla?.met ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-slate-muted">Breached</p>
              <p className="text-lg font-bold text-rose-400">{latestSla?.breached ?? 0}</p>
            </div>
          </div>
          {slaTrend !== 0 && (
            <div className={cn('mt-3 text-xs text-center flex items-center justify-center gap-1', slaTrend > 0 ? 'text-emerald-400' : 'text-rose-400')}>
              {slaTrend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{Math.abs(slaTrend).toFixed(1)}% vs prev month</span>
            </div>
          )}
        </div>

        {/* SLA Trend Chart - Recharts */}
        <ChartCard title="SLA Trend" subtitle="Monthly attainment rate" icon={TrendingUp}>
          {slaPerformance?.length ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={slaPerformance}>
                  <defs>
                    <linearGradient id="slaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => `${value.toFixed(1)}%`} />
                  <Line
                    type="monotone"
                    dataKey="attainment_rate"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ fill: '#10b981', r: 4 }}
                    name="Attainment"
                  />
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-2 flex items-center justify-between text-xs text-slate-muted">
                <span>Target: 90%</span>
                <span className="text-emerald-400 font-semibold">Latest: {latestSla?.attainment_rate?.toFixed(1)}%</span>
              </div>
            </>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No SLA data</div>
          )}
        </ChartCard>

        {/* Resolution Time - Recharts */}
        <ChartCard title="Avg Resolution Time" subtitle="Hours to resolve" icon={Clock}>
          {resolutionTrend?.length ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={resolutionTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => `${value.toFixed(1)}h`} />
                  <Bar dataKey="avg_resolution_hours" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Avg Hours" />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-2 text-center">
                <span className="text-2xl font-bold text-white">
                  {resolutionTrend[resolutionTrend.length - 1]?.avg_resolution_hours?.toFixed(1) ?? 0}h
                </span>
                <span className="text-xs text-slate-muted ml-2">latest month</span>
              </div>
            </>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No resolution data</div>
          )}
        </ChartCard>
      </div>

      {/* Volume Trend - Recharts */}
      <ChartCard title="Ticket Volume Trend" subtitle={`${months} months of ticket data`} icon={Activity}>
        {volumeTrend?.length ? (
          <div className="space-y-4">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={volumeTrend}>
                <defs>
                  <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="resolvedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Area
                  type="monotone"
                  dataKey="total"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#volumeGradient)"
                  name="Total Tickets"
                />
                <Area
                  type="monotone"
                  dataKey="resolved"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#resolvedGradient)"
                  name="Resolved"
                />
              </AreaChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {volumeTrend.slice(-6).map((v) => (
                <div key={v.period} className="bg-slate-elevated rounded-lg p-2 text-center">
                  <p className="text-[10px] text-slate-muted">{v.period}</p>
                  <p className="text-sm font-bold text-white">{v.total}</p>
                  <p className="text-[10px] text-emerald-400">{v.resolution_rate}% res</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="h-[240px] flex items-center justify-center text-slate-muted text-sm">No volume data</div>
        )}
      </ChartCard>

      {/* Category & Agent Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* By Category - Recharts */}
        <ChartCard title={`By Ticket Type (${days}d)`} subtitle="Volume and resolution rate" icon={Zap}>
          {categoryBreakdown?.by_ticket_type?.length ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={categoryBreakdown.by_ticket_type.slice(0, 6)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                  <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis
                    type="category"
                    dataKey="type"
                    stroke="#64748b"
                    tick={{ fontSize: 10 }}
                    width={80}
                    tickFormatter={(value) => (value || 'Other').substring(0, 12)}
                  />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Bar dataKey="count" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Total" />
                  <Bar dataKey="resolved" fill="#10b981" radius={[0, 4, 4, 0]} name="Resolved" />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {categoryBreakdown.by_ticket_type.slice(0, 4).map((cat) => (
                  <div key={cat.type} className="flex items-center justify-between text-xs bg-slate-elevated rounded px-2 py-1">
                    <span className="text-slate-muted truncate">{cat.type || 'Other'}</span>
                    <span className="text-emerald-400 font-mono">{cat.resolution_rate}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">No category data</div>
          )}
        </ChartCard>

        {/* Agent Performance */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-cyan-400" />
            <h3 className="text-white font-semibold">Agent Performance ({days}d)</h3>
          </div>
          {agentInsights?.by_assignee?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-muted text-left">
                    <th className="pb-2">Agent</th>
                    <th className="pb-2 text-right">Tickets</th>
                    <th className="pb-2 text-right">Resolved</th>
                    <th className="pb-2 text-right">Res %</th>
                    <th className="pb-2 text-right">Avg Time</th>
                  </tr>
                </thead>
                <tbody>
                  {agentInsights.by_assignee.slice(0, 10).map((agent) => (
                    <tr key={agent.assignee} className="border-t border-slate-border/40">
                      <td className="py-2 text-white truncate max-w-[120px]">{agent.assignee}</td>
                      <td className="py-2 text-right font-mono text-slate-muted">{agent.total_tickets}</td>
                      <td className="py-2 text-right font-mono text-emerald-400">{agent.resolved}</td>
                      <td className="py-2 text-right font-mono text-blue-400">{agent.resolution_rate}%</td>
                      <td className="py-2 text-right font-mono text-violet-400">{agent.avg_resolution_hours.toFixed(1)}h</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm text-center py-8">No agent data</p>
          )}
        </div>
      </div>

      {/* Patterns & Insights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Peak Hours */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-orange-400" />
            <h3 className="text-white font-semibold">Peak Hours</h3>
          </div>
          {patterns?.peak_hours?.length ? (
            <div className="space-y-2">
              {patterns.peak_hours.slice(0, 5).map((h, idx) => (
                <div key={h.hour} className="flex items-center justify-between">
                  <span className="text-slate-muted text-sm">
                    {idx === 0 && '🔥 '}
                    {h.hour.toString().padStart(2, '0')}:00
                  </span>
                  <span className="font-mono text-white">{h.count} tickets</span>
                </div>
              ))}
              <p className="text-xs text-slate-muted mt-3 pt-3 border-t border-slate-border">
                Peak at <span className="text-orange-400">{peakHour?.hour}:00</span> with {peakHour?.count} tickets
              </p>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No data</p>
          )}
        </div>

        {/* Peak Days */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-4 h-4 text-purple-400" />
            <h3 className="text-white font-semibold">Peak Days</h3>
          </div>
          {patterns?.peak_days?.length ? (
            <div className="space-y-2">
              {patterns.peak_days.map((d, idx) => (
                <div key={d.day} className="flex items-center justify-between">
                  <span className="text-slate-muted text-sm">
                    {idx === 0 && '🔥 '}
                    {d.day}
                  </span>
                  <span className="font-mono text-white">{d.count} tickets</span>
                </div>
              ))}
              <p className="text-xs text-slate-muted mt-3 pt-3 border-t border-slate-border">
                Busiest: <span className="text-purple-400">{peakDay?.day}</span>
              </p>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No data</p>
          )}
        </div>

        {/* By Region */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <MapPin className="w-4 h-4 text-rose-400" />
            <h3 className="text-white font-semibold">By Region</h3>
          </div>
          {patterns?.by_region?.length ? (
            <div className="space-y-2">
              {patterns.by_region.slice(0, 6).map((r) => (
                <div key={r.region} className="flex items-center justify-between">
                  <span className="text-slate-muted text-sm truncate max-w-[140px]">{r.region}</span>
                  <span className="font-mono text-white">{r.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No region data</p>
          )}
        </div>
      </div>

      {/* Queue Health */}
      {queueHealth && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Queue Health</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{qh.unassigned_tickets ?? 0}</p>
              <p className="text-xs text-slate-muted">Unassigned</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{(qh.avg_wait_hours ?? 0).toFixed(1)}h</p>
              <p className="text-xs text-slate-muted">Avg Wait</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-400">{qh.total_agents ?? 0}</p>
              <p className="text-xs text-slate-muted">Agents</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-400">{qh.total_capacity ?? 0}</p>
              <p className="text-xs text-slate-muted">Capacity</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet-400">{qh.total_load ?? 0}</p>
              <p className="text-xs text-slate-muted">Current Load</p>
            </div>
            <div className="text-center">
              <p className={cn('text-2xl font-bold', (qh.overall_utilization_pct ?? 0) > 80 ? 'text-rose-400' : 'text-teal-electric')}>
                {(qh.overall_utilization_pct ?? 0)}%
              </p>
              <p className="text-xs text-slate-muted">Utilization</p>
            </div>
          </div>
        </div>
      )}

      {/* Overdue Detail */}
      {overdueDetail.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <h3 className="text-white font-semibold">Overdue Tickets</h3>
            <span className="text-xs text-slate-muted ml-auto">{overdueDetail.length} tickets</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-muted text-left">
                  <th className="pb-2">Ticket</th>
                  <th className="pb-2">Priority</th>
                  <th className="pb-2">Assigned</th>
                  <th className="pb-2 text-right">Age (hours)</th>
                </tr>
              </thead>
              <tbody>
                {overdueDetail.slice(0, 10).map((ticket: any) => (
                  <tr key={ticket.id} className="border-t border-slate-border/40">
                    <td className="py-2 text-white font-mono">{ticket.ticket_number || `#${ticket.id}`}</td>
                    <td className="py-2">
                      <span className={cn(
                        'px-2 py-0.5 rounded-full text-xs font-medium',
                        ticket.priority === 'urgent' ? 'bg-rose-500/20 text-rose-400' :
                        ticket.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-slate-elevated text-slate-muted'
                      )}>
                        {ticket.priority}
                      </span>
                    </td>
                    <td className="py-2 text-slate-muted">{ticket.assigned_to || 'Unassigned'}</td>
                    <td className="py-2 text-right font-mono text-rose-400">{ticket.age_hours?.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
