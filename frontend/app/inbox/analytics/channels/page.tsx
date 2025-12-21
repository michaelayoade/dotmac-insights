'use client';

import { useState, useMemo } from 'react';
import {
  MessageSquare,
  Clock,
  TrendingUp,
  Mail,
  MessageCircle,
  Phone,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ArrowUpDown,
  ChevronLeft,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useInboxAnalyticsChannels } from '@/hooks/useInbox';
import { PageHeader, Select } from '@/components/ui';
import type { InboxChannelStats } from '@/lib/inbox.types';

const CHANNEL_ICONS: Record<string, React.ElementType> = {
  email: Mail,
  chat: MessageCircle,
  whatsapp: MessageCircle,
  phone: Phone,
  sms: MessageCircle,
  social: MessageCircle,
};

const CHANNEL_COLORS: Record<string, string> = {
  email: 'text-blue-400 bg-blue-500/10',
  chat: 'text-emerald-400 bg-emerald-500/10',
  whatsapp: 'text-green-400 bg-green-500/10',
  phone: 'text-violet-400 bg-violet-500/10',
  sms: 'text-cyan-400 bg-cyan-500/10',
  social: 'text-pink-400 bg-pink-500/10',
};

type SortField = 'name' | 'type' | 'conversation_count' | 'avg_response_time_hours';
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

export default function InboxChannelAnalyticsPage() {
  const [days, setDays] = useState(7);
  const [sortField, setSortField] = useState<SortField>('conversation_count');
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
  } = useInboxAnalyticsChannels({ days });

  const channels = useMemo(() => data?.channels ?? [], [data?.channels]);

  // Compute summary stats
  const totalChannels = channels.length;
  const totalConversations = channels.reduce((sum, c) => sum + (c.conversation_count || 0), 0);
  const avgResponseTime = channels.length > 0
    ? channels.reduce((sum, c) => sum + (c.avg_response_time_hours || 0), 0) / channels.length
    : 0;

  // Sort channels
  const sortedChannels = useMemo(() => {
    return [...channels].sort((a, b) => {
      let aVal: string | number = a[sortField] ?? '';
      let bVal: string | number = b[sortField] ?? '';

      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [channels, sortField, sortOrder]);

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
        <p className="text-lg text-rose-400 mb-4">Failed to load channel analytics</p>
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
          value={formatResponseTime(avgResponseTime)}
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
                  <SortHeader field="name">Channel</SortHeader>
                  <SortHeader field="type">Type</SortHeader>
                  <SortHeader field="conversation_count">Conversations</SortHeader>
                  <SortHeader field="avg_response_time_hours">Avg Response</SortHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {sortedChannels.map((channel: InboxChannelStats) => {
                  const Icon = CHANNEL_ICONS[channel.type] || MessageCircle;
                  const colorClasses = CHANNEL_COLORS[channel.type] || 'text-slate-400 bg-slate-500/10';

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
                          {formatResponseTime(channel.avg_response_time_hours)}
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
