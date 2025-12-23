'use client';

import { useState, useMemo } from 'react';
import {
  MessageSquare,
  Clock,
  TrendingUp,
  MessageCircle,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useInboxAnalyticsChannels } from '@/hooks/useInbox';
import { useTableSort } from '@/hooks/useTableSort';
import { Button, PageHeader, Select } from '@/components/ui';
import type { InboxChannelStats } from '@/lib/inbox.types';
import {
  formatInboxResponseTime,
  INBOX_CHANNEL_COLOR_CLASSES,
  INBOX_CHANNEL_ICON_MAP,
  INBOX_PERIOD_OPTIONS,
} from '@/lib/config/inbox-analytics';
import { MetricCard, SortHeader } from '@/components/inbox/analytics/shared';

type ChannelSortField = 'name' | 'type' | 'conversation_count' | 'avg_response_time_hours';

export default function InboxChannelAnalyticsPage() {
  const [days, setDays] = useState(7);
  const dayOptions = INBOX_PERIOD_OPTIONS;

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useInboxAnalyticsChannels({ days });

  const channels = useMemo(() => data?.channels ?? [], [data?.channels]);

  // Use centralized sort hook
  const { sortedItems: sortedChannels, sortField, sortOrder, toggleSort } = useTableSort<
    ChannelSortField,
    InboxChannelStats
  >(channels, { defaultField: 'conversation_count', defaultOrder: 'desc' });

  // Compute summary stats
  const totalChannels = channels.length;
  const totalConversations = channels.reduce((sum, c) => sum + (c.conversation_count || 0), 0);
  const avgResponseTime = channels.length > 0
    ? channels.reduce((sum, c) => sum + (c.avg_response_time_hours || 0), 0) / channels.length
    : 0;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load channel analytics</p>
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
          title="Channel Analytics"
          subtitle={`Performance metrics by communication channel (${days} days)`}
          icon={MessageSquare}
        />
        <Select
          value={String(days)}
          onChange={(value) => setDays(Number(value))}
          className="w-32"
          options={dayOptions}
        />
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Total Channels"
          value={totalChannels}
          icon={MessageSquare}
          colorClass="text-blue-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Total Conversations"
          value={totalConversations.toLocaleString()}
          icon={TrendingUp}
          colorClass="text-emerald-400"
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

      {/* Channel Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-border">
          <h2 className="text-lg font-semibold">Channel Performance</h2>
        </div>

    {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
          </div>
        ) : channels.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-muted">
            <MessageSquare className="w-12 h-12 mb-4 opacity-50" />
            <p>No channel data available</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-elevated border-b border-slate-border">
                <tr>
                  <SortHeader field="name" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Channel</SortHeader>
                  <SortHeader field="type" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Type</SortHeader>
                  <SortHeader field="conversation_count" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Conversations</SortHeader>
                  <SortHeader field="avg_response_time_hours" currentField={sortField} sortOrder={sortOrder} onSort={toggleSort}>Avg Response</SortHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {sortedChannels.map((channel: InboxChannelStats) => {
                  const Icon = INBOX_CHANNEL_ICON_MAP[channel.type] || MessageCircle;
                  const colorClasses = INBOX_CHANNEL_COLOR_CLASSES[channel.type] || 'text-slate-400 bg-slate-500/10';

                  return (
                    <tr key={channel.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-3">
                          <div className={cn('p-2 rounded-lg', colorClasses)}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="font-medium">{channel.name}</span>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <span className="px-2.5 py-1 bg-slate-elevated rounded-full text-xs capitalize">
                          {channel.type}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className="text-emerald-400 font-medium">
                          {channel.conversation_count?.toLocaleString() || 0}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className="text-slate-muted">
                          {formatInboxResponseTime(channel.avg_response_time_hours)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
