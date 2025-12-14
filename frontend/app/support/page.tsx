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
import {
  useSupportDashboard,
  useSupportAnalyticsVolumeTrend,
  useSupportAnalyticsSlaPerformance,
  useSupportAnalyticsByCategory,
  useSupportRoutingQueueHealth,
  useSupportSlaBreachesSummary,
  useSupportTeams,
  useSupportAgents,
} from '@/hooks/useApi';
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

const CHART_COLORS = ['#14b8a6', '#f59e0b', '#8b5cf6', '#ec4899', '#10b981', '#06b6d4'];

function MetricCard({
  label,
  value,
  icon: Icon,
  trend,
  trendLabel,
  colorClass = 'text-teal-electric',
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  colorClass?: string;
  loading?: boolean;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
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
    </div>
  );
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
        <p className="text-white font-semibold">{title}</p>
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
  const color = attainment >= 90 ? '#10B981' : attainment >= 70 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative w-32 h-32 mx-auto">
      <svg className="w-full h-full -rotate-90">
        <circle cx="64" cy="64" r={radius} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-white">{attainment.toFixed(0)}%</span>
        <span className="text-xs text-slate-muted">SLA</span>
      </div>
    </div>
  );
}

export default function SupportDashboardPage() {
  // Fetch dashboard data
  const { data: dashboard, isLoading: dashboardLoading } = useSupportDashboard();
  const { data: volumeTrend } = useSupportAnalyticsVolumeTrend({ months: 6 });
  const { data: slaPerformance } = useSupportAnalyticsSlaPerformance({ months: 6 });
  const { data: categoryBreakdown } = useSupportAnalyticsByCategory({ days: 30 });
  const { data: queueHealth } = useSupportRoutingQueueHealth();
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 });
  const { data: teamsData } = useSupportTeams();
  const { data: agentsData } = useSupportAgents();

  const teams = teamsData?.teams || [];
  const agents = agentsData?.agents || [];

  // Calculate SLA trend
  const latestSla = slaPerformance?.[slaPerformance.length - 1];
  const prevSla = slaPerformance?.[slaPerformance.length - 2];
  const slaTrend = latestSla && prevSla ? latestSla.attainment_rate - prevSla.attainment_rate : 0;

  // Format volume trend for chart
  const volumeChartData = useMemo(() => {
    if (!volumeTrend) return [];
    return volumeTrend.map((v: any) => ({
      period: v.period,
      total: v.total,
      resolved: v.resolved,
    }));
  }, [volumeTrend]);

  // Format category breakdown for pie chart
  const categoryChartData = useMemo(() => {
    if (!categoryBreakdown?.by_ticket_type) return [];
    return categoryBreakdown.by_ticket_type.slice(0, 5).map((c: any, idx: number) => ({
      name: c.type || 'Other',
      value: c.count,
      color: CHART_COLORS[idx % CHART_COLORS.length],
    }));
  }, [categoryBreakdown]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-br from-teal-500/10 via-amber-500/5 to-slate-card border border-teal-500/20 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center">
              <Headphones className="w-6 h-6 text-teal-electric" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Support Dashboard</h1>
              <p className="text-slate-muted text-sm">Ticket management, SLA tracking, and team performance</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/support/tickets/new"
              className="px-4 py-2 bg-teal-electric text-slate-950 rounded-lg text-sm font-semibold hover:bg-teal-electric/90 transition-colors"
            >
              New Ticket
            </Link>
            <Link
              href="/support/analytics"
              className="px-4 py-2 bg-slate-elevated text-white rounded-lg text-sm font-medium hover:bg-slate-border transition-colors"
            >
              View Analytics
            </Link>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <MetricCard
            label="Open Tickets"
            value={dashboard?.tickets?.open ?? 0}
            icon={Ticket}
            colorClass="text-amber-400"
            loading={dashboardLoading}
          />
          <MetricCard
            label="Resolved"
            value={dashboard?.tickets?.resolved ?? 0}
            icon={CheckCircle2}
            colorClass="text-emerald-400"
            loading={dashboardLoading}
          />
          <MetricCard
            label="Overdue"
            value={dashboard?.metrics?.overdue_tickets ?? slaBreach?.currently_overdue ?? 0}
            icon={AlertTriangle}
            colorClass="text-rose-400"
            loading={dashboardLoading}
          />
          <MetricCard
            label="Avg Resolution"
            value={`${(dashboard?.metrics?.avg_resolution_hours ?? 0).toFixed(1)}h`}
            icon={Clock}
            colorClass="text-violet-400"
            loading={dashboardLoading}
          />
          <MetricCard
            label="Unassigned"
            value={dashboard?.metrics?.unassigned_tickets ?? queueHealth?.unassigned_tickets ?? 0}
            icon={Users}
            colorClass="text-cyan-400"
            loading={dashboardLoading}
          />
        </div>
      </div>

      {/* SLA & Volume Row */}
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

        {/* Volume Trend */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              <h3 className="text-white font-semibold">Ticket Volume Trend</h3>
            </div>
            <span className="text-xs text-slate-muted">Last 6 months</span>
          </div>
          {volumeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={volumeChartData}>
                <defs>
                  <linearGradient id="totalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="resolvedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="period" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Area type="monotone" dataKey="total" stroke="#14b8a6" fill="url(#totalGradient)" strokeWidth={2} name="Total" />
                <Area type="monotone" dataKey="resolved" stroke="#10b981" fill="url(#resolvedGradient)" strokeWidth={2} name="Resolved" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No volume data</div>
          )}
        </div>
      </div>

      {/* Category Breakdown & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Category Breakdown */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">By Type (30d)</h3>
          </div>
          {categoryChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={categoryChartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {categoryChartData.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No category data</div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Quick Actions</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <QuickActionCard
              title="View Tickets"
              description="Browse and manage all tickets"
              href="/support/tickets"
              icon={Ticket}
              colorClass="text-teal-electric"
            />
            <QuickActionCard
              title="Analytics"
              description="Trends, SLA, and performance"
              href="/support/analytics"
              icon={BarChart3}
              colorClass="text-amber-400"
            />
            <QuickActionCard
              title="Manage Teams"
              description={`${teams.length} teams configured`}
              href="/support/teams"
              icon={Shield}
              colorClass="text-violet-400"
            />
            <QuickActionCard
              title="Manage Agents"
              description={`${agents.filter((a: any) => a.is_active).length} active agents`}
              href="/support/agents"
              icon={Users}
              colorClass="text-cyan-400"
            />
          </div>
        </div>
      </div>

      {/* Queue Health & Overdue Tickets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Queue Health */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Queue Health</h3>
          </div>
          {queueHealth ? (
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className={cn(
                  'text-2xl font-bold',
                  (queueHealth.unassigned_tickets ?? 0) > 10 ? 'text-rose-400' :
                  (queueHealth.unassigned_tickets ?? 0) > 5 ? 'text-amber-400' : 'text-white'
                )}>
                  {queueHealth.unassigned_tickets ?? 0}
                </p>
                <p className="text-xs text-slate-muted">Unassigned</p>
              </div>
              <div className="text-center">
                <p className={cn(
                  'text-2xl font-bold',
                  (queueHealth.avg_wait_hours ?? 0) > 4 ? 'text-rose-400' :
                  (queueHealth.avg_wait_hours ?? 0) > 2 ? 'text-amber-400' : 'text-emerald-400'
                )}>
                  {(queueHealth.avg_wait_hours ?? 0).toFixed(1)}h
                </p>
                <p className="text-xs text-slate-muted">Avg Wait</p>
              </div>
              <div className="text-center">
                <p className={cn(
                  'text-2xl font-bold',
                  (queueHealth.overall_utilization_pct ?? 0) > 90 ? 'text-rose-400' :
                  (queueHealth.overall_utilization_pct ?? 0) > 70 ? 'text-amber-400' : 'text-teal-electric'
                )}>
                  {(queueHealth.overall_utilization_pct ?? 0).toFixed(0)}%
                </p>
                <p className="text-xs text-slate-muted">Utilization</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-400">{queueHealth.total_agents ?? 0}</p>
                <p className="text-xs text-slate-muted">Agents</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-400">{queueHealth.total_capacity ?? 0}</p>
                <p className="text-xs text-slate-muted">Capacity</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-violet-400">{queueHealth.total_load ?? 0}</p>
                <p className="text-xs text-slate-muted">Current Load</p>
              </div>
            </div>
          ) : (
            <div className="h-[100px] flex items-center justify-center text-slate-muted text-sm">Loading queue health...</div>
          )}
        </div>

        {/* Overdue Tickets */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <h3 className="text-white font-semibold">Overdue Tickets</h3>
            </div>
            <Link href="/support/tickets?status=overdue" className="text-xs text-teal-electric hover:underline">
              View all
            </Link>
          </div>
          {(dashboard?.metrics?.overdue_tickets ?? 0) > 0 ? (
            <div className="h-[150px] flex flex-col items-center justify-center">
              <div className="text-center">
                <p className="text-4xl font-bold text-rose-400 mb-2">{dashboard?.metrics?.overdue_tickets ?? 0}</p>
                <p className="text-slate-muted text-sm">tickets need attention</p>
                <Link
                  href="/support/tickets?status=overdue"
                  className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-rose-500/20 text-rose-400 rounded-lg text-sm font-medium hover:bg-rose-500/30 transition-colors"
                >
                  <AlertTriangle className="w-4 h-4" />
                  Review Overdue
                </Link>
              </div>
            </div>
          ) : (
            <div className="h-[150px] flex items-center justify-center text-slate-muted text-sm">
              <div className="text-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                <p>No overdue tickets</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Resource Links */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="w-4 h-4 text-cyan-400" />
          <h3 className="text-white font-semibold">Resources</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <Link href="/support/kb" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">Knowledge Base</p>
            <p className="text-slate-muted text-xs">Articles & docs</p>
          </Link>
          <Link href="/support/canned-responses" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">Canned Responses</p>
            <p className="text-slate-muted text-xs">Templates</p>
          </Link>
          <Link href="/support/automation" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">Automation</p>
            <p className="text-slate-muted text-xs">Rules & workflows</p>
          </Link>
          <Link href="/support/sla" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">SLA Policies</p>
            <p className="text-slate-muted text-xs">Response times</p>
          </Link>
          <Link href="/support/routing" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">Routing</p>
            <p className="text-slate-muted text-xs">Assignment rules</p>
          </Link>
          <Link href="/support/settings" className="p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 text-center transition-colors">
            <p className="text-white text-sm font-medium">Settings</p>
            <p className="text-slate-muted text-xs">Configuration</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
