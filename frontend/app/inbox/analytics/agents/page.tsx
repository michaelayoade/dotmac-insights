'use client';

import { useState, useMemo } from 'react';
import {
  BarChart3,
  Users,
  Clock,
  MessageSquare,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ArrowUpDown,
  ChevronLeft,
  User,
  Award,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useInboxAnalyticsAgents } from '@/hooks/useInbox';
import { PageHeader, Select } from '@/components/ui';
import type { InboxAgentStats } from '@/lib/inbox.types';

type SortField = 'name' | 'conversations' | 'messages_sent' | 'avg_response_time_hours';
type SortOrder = 'asc' | 'desc';

function MetricCard({
  label,
  value,
  icon: Icon,
  colorClass = 'text-blue-400',
  isLoading = false,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
  isLoading?: boolean;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          {isLoading ? (
            <div className="h-9 w-20 bg-slate-elevated rounded mt-1 animate-pulse" />
          ) : (
            <p className={cn('text-3xl font-bold mt-1', colorClass)}>{value}</p>
          )}
        </div>
        <div className={cn('p-3 rounded-xl bg-slate-elevated')}>
          <Icon className={cn('w-6 h-6', colorClass)} />
        </div>
      </div>
    </div>
  );
}

function formatResponseTime(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '-';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export default function InboxAgentAnalyticsPage() {
  const [days, setDays] = useState(7);
  const [sortField, setSortField] = useState<SortField>('conversations');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const dayOptions = [
    { value: '7', label: 'Last 7 days' },
    { value: '30', label: 'Last 30 days' },
    { value: '90', label: 'Last 90 days' },
  ];

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useInboxAnalyticsAgents({ days });

  const agents = useMemo(() => data?.agents ?? [], [data?.agents]);

  // Compute summary stats
  const totalAgents = agents.length;
  const totalConversations = agents.reduce((sum, a) => sum + (a.conversations || 0), 0);
  const totalMessages = agents.reduce((sum, a) => sum + (a.messages_sent || 0), 0);
  const avgResponseTime = agents.length > 0
    ? agents.reduce((sum, a) => sum + (a.avg_response_time_hours || 0), 0) / agents.length
    : 0;

  // Top performer
  const topPerformer = agents.length > 0
    ? [...agents].sort((a, b) => (b.conversations || 0) - (a.conversations || 0))[0]
    : null;

  // Sort agents
  const sortedAgents = useMemo(() => {
    return [...agents].sort((a, b) => {
      let aVal: string | number = a[sortField] ?? '';
      let bVal: string | number = b[sortField] ?? '';

      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [agents, sortField, sortOrder]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <th
      className="text-left py-3 px-4 text-sm font-medium text-slate-muted cursor-pointer hover:text-foreground transition-colors"
      onClick={() => toggleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        <ArrowUpDown className={cn('w-3.5 h-3.5', sortField === field ? 'text-blue-400' : 'opacity-50')} />
      </div>
    </th>
  );

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load agent analytics</p>
        <button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/inbox/analytics"
        className="inline-flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to Analytics
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Agent Analytics"
          subtitle={`Agent performance metrics (${days} days)`}
          icon={BarChart3}
        />
        <Select
          value={String(days)}
          onChange={(value) => setDays(Number(value))}
          className="w-32"
          options={dayOptions}
        />
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Agents"
          value={totalAgents}
          icon={Users}
          colorClass="text-blue-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Conversations Handled"
          value={totalConversations.toLocaleString()}
          icon={MessageSquare}
          colorClass="text-emerald-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Messages Sent"
          value={totalMessages.toLocaleString()}
          icon={MessageSquare}
          colorClass="text-violet-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Avg Response Time"
          value={formatResponseTime(avgResponseTime)}
          icon={Clock}
          colorClass="text-amber-400"
          isLoading={isLoading}
        />
      </div>

      {/* Top Performer Card */}
      {topPerformer && !isLoading && (
        <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20 rounded-xl p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-amber-500/20 rounded-xl">
              <Award className="w-8 h-8 text-amber-400" />
            </div>
            <div>
              <p className="text-sm text-amber-400 font-medium">Top Performer</p>
              <p className="text-xl font-bold text-foreground">{topPerformer.name}</p>
              <p className="text-sm text-slate-muted">
                {topPerformer.conversations} conversations handled with {formatResponseTime(topPerformer.avg_response_time_hours)} avg response
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Agent Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-border">
          <h2 className="text-lg font-semibold">Agent Performance</h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
          </div>
        ) : agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-muted">
            <Users className="w-12 h-12 mb-4 opacity-50" />
            <p>No agent data available</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-elevated border-b border-slate-border">
                <tr>
                  <SortHeader field="name">Agent</SortHeader>
                  <SortHeader field="conversations">Conversations</SortHeader>
                  <SortHeader field="messages_sent">Messages Sent</SortHeader>
                  <SortHeader field="avg_response_time_hours">Avg Response</SortHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {sortedAgents.map((agent: InboxAgentStats, index: number) => (
                  <tr key={agent.id} className="hover:bg-slate-elevated/50 transition-colors">
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium',
                          index === 0 ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-elevated text-slate-muted'
                        )}>
                          {index === 0 ? (
                            <Award className="w-5 h-5" />
                          ) : (
                            <User className="w-5 h-5" />
                          )}
                        </div>
                        <span className="font-medium">{agent.name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-emerald-400 font-medium">
                        {agent.conversations?.toLocaleString() || 0}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-violet-400">
                        {agent.messages_sent?.toLocaleString() || 0}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-slate-muted">
                        {formatResponseTime(agent.avg_response_time_hours)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
