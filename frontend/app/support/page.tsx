'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  AreaChart,
  Area,
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
import { useConsolidatedSupportDashboard } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  Ticket,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Users,
  Target,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Headphones,
  MessageSquare,
  BarChart3,
  Zap,
  Shield,
  Activity,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { CHART_COLORS } from '@/lib/design-tokens';

const CHART_PALETTE = CHART_COLORS.palette;
const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

function MetricCard({
  label,
  value,
  icon: Icon,
  trend,
  trendLabel,
  colorClass = 'text-teal-electric',
  loading,
  href,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  colorClass?: string;
  loading?: boolean;
  href?: string;
}) {
  const content = (
    <div className={cn(
      'bg-slate-card border border-slate-border rounded-xl p-5 transition-colors',
      href && 'hover:border-teal-electric/50 cursor-pointer'
    )}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          {loading ? (
            <div className="h-8 w-16 bg-slate-elevated animate-pulse rounded mt-1" />
          ) : (
            <p className={cn('text-3xl font-bold mt-1', colorClass)}>{value}</p>
          )}
          {trendLabel && (
            <div className="flex items-center gap-1 mt-2">
              {trend === 'up' && <TrendingUp className="w-3 h-3 text-emerald-400" />}
              {trend === 'down' && <TrendingDown className="w-3 h-3 text-rose-400" />}
              <span className={cn('text-xs', trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-rose-400' : 'text-slate-muted')}>
                {trendLabel}
              </span>
            </div>
          )}
        </div>
        <div className={cn('p-3 rounded-xl', colorClass.includes('teal') ? 'bg-teal-500/10' : 'bg-slate-elevated')}>
          <Icon className={cn('w-6 h-6', colorClass)} />
        </div>
      </div>
      {href && (
        <div className="mt-3 pt-3 border-t border-slate-border/50 flex items-center text-xs text-teal-electric">
          <span>View details</span>
          <ArrowRight className="w-3 h-3 ml-1" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

function QuickActionCard({
  title,
  description,
  href,
  icon: Icon,
  colorClass = 'text-teal-electric',
}: {
  title: string;
  description: string;
  href: string;
  icon: React.ElementType;
  colorClass?: string;
}) {
  return (
    <Link
      href={href}
      className="group bg-slate-card border border-slate-border rounded-xl p-4 hover:border-teal-electric/50 transition-colors flex items-center gap-4"
    >
      <div className={cn('p-3 rounded-xl bg-slate-elevated group-hover:bg-teal-electric/10 transition-colors')}>
        <Icon className={cn('w-5 h-5', colorClass)} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-foreground font-semibold">{title}</p>
        <p className="text-slate-muted text-sm truncate">{description}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-slate-muted group-hover:text-teal-electric transition-colors" />
    </Link>
  );
}

function SlaGauge({ attainment }: { attainment: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (attainment / 100) * circumference;
  const color = attainment >= 90 ? CHART_COLORS.success : attainment >= 70 ? CHART_COLORS.warning : CHART_COLORS.danger;

  return (
    <div className="relative w-32 h-32 mx-auto">
      <svg className="w-full h-full -rotate-90">
        <circle cx="64" cy="64" r={radius} fill="none" stroke={CHART_COLORS.grid} strokeWidth="10" />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-foreground">{attainment.toFixed(0)}%</span>
        <span className="text-xs text-slate-muted">SLA Met</span>
      </div>
    </div>
  );
}

export default function SupportDashboardPage() {
  const { data, isLoading, error, mutate } = useConsolidatedSupportDashboard();

  // Chart data must be computed unconditionally
  const volumeTrendData = useMemo(() => {
    if (!data?.volume_trend) return [];
    return data.volume_trend.map((item) => ({
      period: item.period,
      tickets: item.count,
    }));
  }, [data?.volume_trend]);

  const categoryData = useMemo(() => {
    if (!data?.by_category) return [];
    return data.by_category.map((item, index) => ({
      name: item.category,
      value: item.count,
      color: CHART_PALETTE[index % CHART_PALETTE.length],
    }));
  }, [data?.by_category]);

  const slaPerformanceData = useMemo(() => {
    if (!data?.sla_performance) return [];
    return data.sla_performance.map((item) => ({
      period: item.period,
      met: item.met,
      breached: item.breached,
      rate: item.rate,
    }));
  }, [data?.sla_performance]);

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load support dashboard data."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) {
    return <LoadingState />;
  }

  const { summary, queue_health, sla_breaches } = data;
  const slaAttainment = summary?.sla_attainment ?? 100;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Support Dashboard"
        subtitle="Ticket management, SLA performance, and team metrics"
        icon={Headphones}
        iconClassName="bg-purple-500/10 border border-purple-500/30"
      />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Open Tickets"
          value={summary?.open_tickets ?? 0}
          icon={Ticket}
          colorClass="text-blue-400"
          href="/support/tickets?status=open"
        />
        <MetricCard
          label="Resolved Tickets"
          value={summary?.resolved_tickets ?? 0}
          icon={CheckCircle2}
          colorClass="text-emerald-400"
          href="/support/tickets?status=resolved"
        />
        <MetricCard
          label="Overdue Tickets"
          value={summary?.overdue_tickets ?? 0}
          icon={AlertTriangle}
          colorClass={summary?.overdue_tickets ? 'text-rose-400' : 'text-slate-muted'}
          trend={summary?.overdue_tickets ? 'down' : 'neutral'}
          trendLabel={summary?.overdue_tickets ? 'Action needed' : 'All on track'}
          href="/support/tickets?overdue=true"
        />
        <MetricCard
          label="Avg Resolution Time"
          value={`${(summary?.avg_resolution_hours ?? 0).toFixed(1)}h`}
          icon={Clock}
          colorClass="text-amber-400"
          href="/support/analytics"
        />
      </div>

      {/* SLA & Queue Health Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* SLA Attainment Gauge */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">SLA Attainment</h3>
            </div>
            <Link href="/support/sla" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Details <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <SlaGauge attainment={slaAttainment} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-center">
            <div className="bg-slate-elevated/50 rounded-lg p-2">
              <p className="text-emerald-400 font-bold">{sla_breaches?.total ? (summary?.resolved_tickets || 0) - sla_breaches.total : summary?.resolved_tickets || 0}</p>
              <p className="text-slate-muted text-xs">SLA Met</p>
            </div>
            <div className="bg-slate-elevated/50 rounded-lg p-2">
              <p className="text-rose-400 font-bold">{sla_breaches?.total ?? 0}</p>
              <p className="text-slate-muted text-xs">SLA Breached</p>
            </div>
          </div>
        </div>

        {/* Queue Health */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Queue Health</h3>
            </div>
            <Link href="/support/routing" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Queues <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Unassigned</span>
              <span className={cn('font-bold', (queue_health?.unassigned_count || 0) > 0 ? 'text-amber-400' : 'text-emerald-400')}>
                {queue_health?.unassigned_count ?? summary?.unassigned_tickets ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Avg Wait Time</span>
              <span className="text-foreground font-bold">{(queue_health?.avg_wait_hours ?? 0).toFixed(1)}h</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Agent Capacity</span>
              <span className="text-foreground font-bold">{queue_health?.total_agents ?? summary?.agent_count ?? 0} agents</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Current Load</span>
              <span className={cn('font-bold', (queue_health?.current_load || 0) > 10 ? 'text-rose-400' : 'text-emerald-400')}>
                {(queue_health?.current_load ?? 0).toFixed(1)} tickets/agent
              </span>
            </div>
          </div>
        </div>

        {/* Team Stats */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Team Overview</h3>
            </div>
            <Link href="/support/teams" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Teams <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Link href="/support/teams" className="bg-slate-elevated/50 rounded-lg p-4 text-center hover:bg-slate-elevated transition-colors">
              <Users className="w-6 h-6 text-blue-400 mx-auto mb-2" />
              <p className="text-2xl font-bold text-foreground">{summary?.team_count ?? 0}</p>
              <p className="text-slate-muted text-xs">Teams</p>
            </Link>
            <Link href="/support/agents" className="bg-slate-elevated/50 rounded-lg p-4 text-center hover:bg-slate-elevated transition-colors">
              <Headphones className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
              <p className="text-2xl font-bold text-foreground">{summary?.agent_count ?? 0}</p>
              <p className="text-slate-muted text-xs">Active Agents</p>
            </Link>
          </div>
          {sla_breaches?.by_priority && Object.keys(sla_breaches.by_priority).length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-border">
              <p className="text-slate-muted text-xs mb-2">SLA Breaches by Priority (30d)</p>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(sla_breaches.by_priority).map(([priority, count]) => (
                  <span
                    key={priority}
                    className={cn(
                      'text-xs px-2 py-1 rounded-full',
                      priority === 'high' || priority === 'urgent' ? 'bg-rose-500/20 text-rose-400' :
                      priority === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-slate-500/20 text-slate-400'
                    )}
                  >
                    {priority}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Ticket Volume Trend */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Ticket Volume (6 Months)</h3>
            </div>
            <Link href="/support/analytics" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Analytics <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {volumeTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={volumeTrendData}>
                <defs>
                  <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="period" tick={{ fill: CHART_COLORS.label, fontSize: 10 }} />
                <YAxis tick={{ fill: CHART_COLORS.label, fontSize: 10 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Area
                  type="monotone"
                  dataKey="tickets"
                  stroke={CHART_COLORS.primary}
                  fill="url(#volumeGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">
              No volume data available
            </div>
          )}
        </div>

        {/* Ticket by Category */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Tickets by Category (30 Days)</h3>
            </div>
            <Link href="/support/analytics?tab=categories" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">
              No category data available
            </div>
          )}
        </div>
      </div>

      {/* SLA Performance Chart */}
      {slaPerformanceData.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">SLA Performance (6 Months)</h3>
            </div>
            <Link href="/support/sla" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View SLA Details <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={slaPerformanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
              <XAxis dataKey="period" tick={{ fill: CHART_COLORS.label, fontSize: 10 }} />
              <YAxis tick={{ fill: CHART_COLORS.label, fontSize: 10 }} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Legend />
              <Area type="monotone" dataKey="met" name="SLA Met" stroke={CHART_COLORS.success} fill={CHART_COLORS.success} fillOpacity={0.3} />
              <Area type="monotone" dataKey="breached" name="SLA Breached" stroke={CHART_COLORS.danger} fill={CHART_COLORS.danger} fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <QuickActionCard
          title="New Ticket"
          description="Create a support ticket"
          href="/support/tickets/new"
          icon={Ticket}
          colorClass="text-blue-400"
        />
        <QuickActionCard
          title="Ticket Queue"
          description="View all open tickets"
          href="/support/tickets"
          icon={MessageSquare}
          colorClass="text-emerald-400"
        />
        <QuickActionCard
          title="Analytics"
          description="Performance metrics"
          href="/support/analytics"
          icon={BarChart3}
          colorClass="text-amber-400"
        />
        <QuickActionCard
          title="SLA Policies"
          description="Manage SLA rules"
          href="/support/sla"
          icon={Zap}
          colorClass="text-purple-400"
        />
      </div>
    </div>
  );
}
