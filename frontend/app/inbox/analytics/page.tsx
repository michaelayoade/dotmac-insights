'use client';

import { useState } from 'react';
import {
  BarChart3,
  Clock,
  MessageSquare,
  Users,
  CheckCircle,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
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
import { cn } from '@/lib/utils';
import {
  useInboxAnalyticsSummary,
  useInboxAnalyticsVolume,
  useInboxAnalyticsAgents,
  useInboxAnalyticsChannels,
} from '@/hooks/useInbox';
import { PageHeader, Select } from '@/components/ui';
import { INBOX_CHANNEL_CHART_COLORS, INBOX_PERIOD_OPTIONS } from '@/lib/config/inbox-analytics';
import { ChartErrorState, ChartSkeleton, MetricCard } from '@/components/inbox/analytics/shared';


export default function InboxAnalyticsPage() {
  const [days, setDays] = useState(7);

  const {
    data: summary,
    error: summaryError,
    isLoading: summaryLoading,
    mutate: refreshSummary,
  } = useInboxAnalyticsSummary({ days });

  const {
    data: volumeData,
    error: volumeError,
    isLoading: volumeLoading,
    mutate: refreshVolume,
  } = useInboxAnalyticsVolume({ days });

  const {
    data: agentsData,
    error: agentsError,
    isLoading: agentsLoading,
    mutate: refreshAgents,
  } = useInboxAnalyticsAgents({ days });

  const {
    data: channelsData,
    error: channelsError,
    isLoading: channelsLoading,
    mutate: refreshChannels,
  } = useInboxAnalyticsChannels({ days });

  // Transform volume data for charts
  const dailyVolumeChartData = (volumeData?.daily_volume || []).map((d) => ({
    date: new Date(d.date).toLocaleDateString(undefined, { weekday: 'short' }),
    count: d.count,
  }));

  // Transform channel data for pie chart
  const channelBreakdown = Object.entries(summary?.by_channel || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: value as number,
    color: INBOX_CHANNEL_CHART_COLORS[name] || '#64748b',
  }));

  // Calculate resolution stats from summary
  const totalConvs = summary?.total_conversations || 0;
  const resolvedToday = summary?.resolved_today || 0;
  const openCount = summary?.open_count || 0;
  const pendingCount = summary?.pending_count || 0;

  const resolutionStats = totalConvs > 0
    ? [
        { name: 'Resolved Today', value: Math.round((resolvedToday / Math.max(totalConvs, 1)) * 100), color: 'bg-emerald-500' },
        { name: 'Open', value: Math.round((openCount / Math.max(totalConvs, 1)) * 100), color: 'bg-amber-500' },
        { name: 'Pending', value: Math.round((pendingCount / Math.max(totalConvs, 1)) * 100), color: 'bg-slate-500' },
      ]
    : [];

  const periodOptions = INBOX_PERIOD_OPTIONS;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox Analytics"
        subtitle="Conversation metrics and performance"
        icon={BarChart3}
        iconClassName="bg-amber-500/10 border border-amber-500/30"
        actions={
          <Select
            value={String(days)}
            onChange={(val) => setDays(Number(val))}
            options={periodOptions}
            aria-label="Select time period"
          />
        }
      />

      {/* Key metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Conversations"
          value={summary?.total_conversations?.toLocaleString() || '0'}
          icon={MessageSquare}
          colorClass="text-blue-400"
          iconWrapperClassName="bg-blue-500/10"
          isLoading={summaryLoading}
        />
        <MetricCard
          label="Avg Response Time"
          value={summary?.avg_first_response_hours ? `${summary.avg_first_response_hours}h` : 'N/A'}
          icon={Clock}
          colorClass="text-emerald-400"
          isLoading={summaryLoading}
        />
        <MetricCard
          label="Resolved Today"
          value={summary?.resolved_today?.toString() || '0'}
          icon={CheckCircle}
          colorClass="text-violet-400"
          isLoading={summaryLoading}
        />
        <MetricCard
          label="Total Unread"
          value={summary?.total_unread?.toString() || '0'}
          icon={Users}
          colorClass="text-amber-400"
          isLoading={summaryLoading}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Volume trend */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-4">Conversation Volume</h3>
          {volumeLoading ? (
            <ChartSkeleton />
          ) : volumeError ? (
            <ChartErrorState message="Failed to load volume data" onRetry={() => refreshVolume()} />
          ) : dailyVolumeChartData.length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-slate-muted">
              <p className="text-sm">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={dailyVolumeChartData}>
                <defs>
                  <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                  formatter={(value: number) => [value, 'Conversations']}
                />
                <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="url(#volumeGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Channel performance */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-4">Channel Performance</h3>
          {channelsLoading ? (
            <ChartSkeleton />
          ) : channelsError ? (
            <ChartErrorState message="Failed to load channel data" onRetry={() => refreshChannels()} />
          ) : (channelsData?.channels || []).length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-slate-muted">
              <p className="text-sm">No channel data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={channelsData?.channels || []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: '#64748b', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={80}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                  formatter={(value: number, name: string) => {
                    if (name === 'conversation_count') return [value, 'Conversations'];
                    if (name === 'avg_response_time_hours') return [`${value}h`, 'Avg Response'];
                    return [value, name];
                  }}
                />
                <Bar dataKey="conversation_count" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Conversations" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Channel breakdown */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-4">Channel Breakdown</h3>
          {summaryLoading ? (
            <ChartSkeleton height={220} />
          ) : summaryError ? (
            <ChartErrorState message="Failed to load data" onRetry={() => refreshSummary()} />
          ) : channelBreakdown.length === 0 ? (
            <div className="flex items-center justify-center h-[220px] text-slate-muted">
              <p className="text-sm">No channel data</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={channelBreakdown}
                  cx="50%"
                  cy="40%"
                  innerRadius={40}
                  outerRadius={65}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {channelBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  formatter={(value: number) => [value, 'Conversations']}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: '10px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top performing agents */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-4">Top Agents</h3>
          {agentsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center justify-between animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-slate-elevated rounded-full" />
                    <div className="w-24 h-4 bg-slate-elevated rounded" />
                  </div>
                  <div className="w-16 h-4 bg-slate-elevated rounded" />
                </div>
              ))}
            </div>
          ) : agentsError ? (
            <ChartErrorState message="Failed to load agents" onRetry={() => refreshAgents()} />
          ) : (agentsData?.agents || []).length === 0 ? (
            <div className="flex items-center justify-center h-32 text-slate-muted">
              <p className="text-sm">No agent data available</p>
            </div>
          ) : (
            <div className="space-y-3">
              {(agentsData?.agents || []).slice(0, 5).map((agent, idx) => (
                <div key={agent.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={cn(
                      'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                      idx === 0 && 'bg-amber-500/20 text-amber-400',
                      idx === 1 && 'bg-slate-500/20 text-slate-400',
                      idx === 2 && 'bg-amber-700/20 text-amber-600',
                      idx > 2 && 'bg-slate-elevated text-slate-muted'
                    )}>
                      {idx + 1}
                    </span>
                    <span className="text-foreground truncate max-w-[120px]">{agent.name}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-foreground font-medium">{agent.conversations}</p>
                    <p className="text-xs text-slate-muted">
                      {agent.avg_response_time_hours ? `${agent.avg_response_time_hours}h avg` : 'N/A'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Resolution stats */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-4">Status Distribution</h3>
          {summaryLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse">
                  <div className="flex items-center justify-between mb-1">
                    <div className="w-24 h-3 bg-slate-elevated rounded" />
                    <div className="w-8 h-3 bg-slate-elevated rounded" />
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full" />
                </div>
              ))}
            </div>
          ) : summaryError ? (
            <ChartErrorState message="Failed to load data" onRetry={() => refreshSummary()} />
          ) : resolutionStats.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-slate-muted">
              <p className="text-sm">No status data available</p>
            </div>
          ) : (
            <>
              <div className="space-y-4">
                {resolutionStats.map((item) => (
                  <div key={item.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-slate-200 text-sm">{item.name}</span>
                      <span className="text-foreground font-medium">{item.value}%</span>
                    </div>
                    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', item.color)}
                        style={{ width: `${item.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-slate-border/50">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-muted">Unassigned</span>
                  <span className="text-amber-400 font-semibold">{summary?.unassigned_count || 0}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
