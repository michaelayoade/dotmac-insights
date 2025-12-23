'use client';

import { useState, useMemo } from 'react';
import {
  BarChart3,
  Users,
  Clock,
  MessageSquare,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  User,
  Award,
  Loader2,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useInboxAnalyticsAgents } from '@/hooks/useInbox';
import { useTableSort } from '@/hooks/useTableSort';
import { Button, PageHeader, Select } from '@/components/ui';
import type { InboxAgentStats } from '@/lib/inbox.types';
import { formatInboxResponseTime, INBOX_PERIOD_OPTIONS } from '@/lib/config/inbox-analytics';
import {
  MetricCard,
  ChartSkeleton,
  NoDataFallback,
  SortHeader,
} from '@/components/inbox/analytics/shared';

type AgentSortField = 'name' | 'conversations' | 'messages_sent' | 'avg_response_time_hours';

export default function InboxAgentAnalyticsPage() {
  const [days, setDays] = useState(7);
  const dayOptions = INBOX_PERIOD_OPTIONS;

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useInboxAnalyticsAgents({ days });

  const agents = useMemo(() => data?.agents ?? [], [data?.agents]);

  // Use centralized sort hook
  const { sortedItems: sortedAgents, sortField, sortOrder, toggleSort } = useTableSort<
    AgentSortField,
    InboxAgentStats
  >(agents, { defaultField: 'conversations', defaultOrder: 'desc' });

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

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load agent analytics</p>
        <Button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
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
          value={formatInboxResponseTime(avgResponseTime)}
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
                {topPerformer.conversations} conversations handled with {formatInboxResponseTime(topPerformer.avg_response_time_hours)} avg response
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
                  <SortHeader field="name" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Agent</SortHeader>
                  <SortHeader field="conversations" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Conversations</SortHeader>
                  <SortHeader field="messages_sent" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Messages Sent</SortHeader>
                  <SortHeader field="avg_response_time_hours" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Avg Response</SortHeader>
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
                        {formatInboxResponseTime(agent.avg_response_time_hours)}
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
