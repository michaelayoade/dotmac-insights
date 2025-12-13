'use client';

import { useState } from 'react';
import { Filter, Activity, TrendingUp, Clock, AlertTriangle, Users, Target } from 'lucide-react';
import { useSupportOverview } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatHours(value?: number) {
  return value !== undefined && value !== null ? `${value.toFixed(1)}h` : '-';
}

export default function SupportAnalyticsPage() {
  const [priority, setPriority] = useState<string>('');
  const [ticketType, setTicketType] = useState<string>('');
  const { data, isLoading, error } = useSupportOverview({
    priority: (priority as any) || undefined,
    ticket_type: ticketType || undefined,
    limit_overdue: 50,
  });

  const summary = data?.summary;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Support Analytics</h1>
          <p className="text-slate-muted text-sm">Ticket volumes, SLA performance, and backlog health</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">Priority: All</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
          <input
            value={ticketType}
            onChange={(e) => setTicketType(e.target.value)}
            placeholder="Ticket type"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3">
          Failed to load analytics
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: summary?.total ?? 0, icon: Activity },
          { label: 'Open', value: (summary?.open ?? 0) + (summary?.replied ?? 0), icon: AlertTriangle },
          { label: 'Resolved', value: summary?.resolved ?? 0, icon: TrendingUp },
          { label: 'SLA Attainment', value: `${summary?.sla_attainment_pct?.toFixed?.(1) ?? '0'}%`, icon: Target },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="bg-slate-card border border-slate-border rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <Icon className="w-4 h-4 text-teal-electric" />
                <p className="text-slate-muted text-sm">{card.label}</p>
              </div>
              <p className="text-2xl font-bold text-white">{card.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <DataPanel title="By Priority" rows={data?.by_priority} columns={[
          { label: 'Priority', render: (row: any) => row.priority },
          { label: 'Open', render: (row: any) => row.open },
          { label: 'Total', render: (row: any) => row.total },
          { label: 'SLA Breach', render: (row: any) => `${row.sla_breach_pct?.toFixed?.(1) ?? 0}%` },
        ]} />
        <DataPanel title="By Type" rows={data?.by_type} columns={[
          { label: 'Type', render: (row: any) => row.ticket_type },
          { label: 'Open', render: (row: any) => row.open },
          { label: 'Total', render: (row: any) => row.total },
          { label: 'Avg Resolution', render: (row: any) => formatHours(row.avg_resolution_hours) },
        ]} />
        <DataPanel title="Backlog Age" rows={data?.backlog_age} columns={[
          { label: 'Bucket', render: (row: any) => row.bucket },
          { label: 'Count', render: (row: any) => row.count },
        ]} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataPanel title="Agent Performance" rows={data?.agent_performance} columns={[
          { label: 'Agent', render: (row: any) => row.agent },
          { label: 'Open', render: (row: any) => row.open },
          { label: 'Resolved', render: (row: any) => row.resolved },
          { label: 'SLA', render: (row: any) => `${row.sla_attainment_pct?.toFixed?.(1) ?? 0}%` },
          { label: 'CSAT', render: (row: any) => row.csat_avg ?? '-' },
        ]} />
        <DataPanel title="Team Performance" rows={data?.team_performance} columns={[
          { label: 'Team', render: (row: any) => row.team },
          { label: 'Open', render: (row: any) => row.open },
          { label: 'Resolved', render: (row: any) => row.resolved },
          { label: 'SLA', render: (row: any) => `${row.sla_attainment_pct?.toFixed?.(1) ?? 0}%` },
          { label: 'Avg Res', render: (row: any) => formatHours(row.avg_resolution_hours) },
        ]} />
      </div>

      <DataPanel title="Overdue Detail" rows={data?.overdue_detail} columns={[
        { label: 'Ticket', render: (row: any) => row.ticket_number || row.id },
        { label: 'Priority', render: (row: any) => row.priority },
        { label: 'Assigned', render: (row: any) => row.assigned_to || '-' },
        { label: 'Resolution By', render: (row: any) => row.resolution_by || '-' },
        { label: 'Age (h)', render: (row: any) => row.age_hours?.toFixed?.(1) ?? '-' },
      ]} />
    </div>
  );
}

function DataPanel({
  title,
  rows,
  columns,
}: {
  title: string;
  rows?: any[];
  columns: { label: string; render: (row: any) => React.ReactNode }[];
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold">{title}</h3>
        <span className="text-slate-muted text-xs">{rows?.length ?? 0} rows</span>
      </div>
      {!rows?.length ? (
        <p className="text-slate-muted text-sm">No data</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-muted">
              <tr>
                {columns.map((col) => (
                  <th key={col.label} className="text-left px-2 py-2">{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx} className={cn('border-t border-slate-border/60', idx === 0 && 'border-t-0')}>
                  {columns.map((col) => (
                    <td key={col.label} className="px-2 py-2 text-slate-200">{col.render(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
