'use client';

import React, { useState } from 'react';
import { Filter, TrendingUp, BarChart2, PieChart, Layers } from 'lucide-react';
import {
  useProjectsStatusTrend,
  useProjectsTaskDistribution,
  useProjectsPerformance,
  useProjectsDepartmentSummary,
  useProjectsDashboard,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function ProjectsAnalyticsPage() {
  const [months, setMonths] = useState(12);

  const { data: dashboard } = useProjectsDashboard();
  const { data: statusTrend } = useProjectsStatusTrend(months);
  const { data: taskDistribution } = useProjectsTaskDistribution();
  const { data: performance } = useProjectsPerformance();
  const { data: departmentSummary } = useProjectsDepartmentSummary(months);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Project Analytics</h1>
          <p className="text-slate-muted text-sm">Track delivery velocity, workload, and department performance</p>
        </div>
      </div>

      {dashboard?.cards && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Object.entries(dashboard.cards).map(([label, value]) => (
            <SummaryCard key={label} label={label} value={value as number} />
          ))}
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-muted flex items-center gap-2">
            Months:
            <select
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              {[3, 6, 12, 18, 24].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataPanel
          title="Status Trend"
          icon={TrendingUp}
          rows={statusTrend}
          columns={[
            { label: 'Period', render: (row: any) => row.period },
            { label: 'Open', render: (row: any) => row.open ?? row.open_count ?? '-' },
            { label: 'Completed', render: (row: any) => row.completed ?? row.completed_count ?? '-' },
            { label: 'On Hold', render: (row: any) => row.on_hold ?? row.on_hold_count ?? '-' },
          ]}
        />
        <DataPanel
          title="Task Distribution"
          icon={PieChart}
          rows={taskDistribution}
          columns={[
            { label: 'Status', render: (row: any) => row.status || row.bucket },
            { label: 'Tasks', render: (row: any) => row.count ?? row.tasks ?? '-' },
            { label: 'Hours', render: (row: any) => row.hours ?? '-' },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataPanel
          title="Project Performance"
          icon={BarChart2}
          rows={performance}
          columns={[
            { label: 'Project', render: (row: any) => row.project_name || row.name || row.erpnext_id || '-' },
            { label: 'Progress', render: (row: any) => `${row.percent_complete ?? 0}%` },
            { label: 'Gross Margin', render: (row: any) => row.gross_margin ?? '-' },
            { label: 'Write Back', render: (row: any) => row.write_back_status || '-' },
          ]}
        />
        <DataPanel
          title="Department Summary"
          icon={Layers}
          rows={departmentSummary}
          columns={[
            { label: 'Department', render: (row: any) => row.department || row.name || '-' },
            { label: 'Projects', render: (row: any) => row.count ?? row.projects ?? '-' },
            { label: 'Completed', render: (row: any) => row.completed ?? '-' },
            { label: 'On Hold', render: (row: any) => row.on_hold ?? '-' },
          ]}
        />
      </div>
    </div>
  );
}

function DataPanel({
  title,
  icon: Icon,
  rows,
  columns,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  rows?: any[];
  columns: { label: string; render: (row: any) => React.ReactNode }[];
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">{title}</h3>
        </div>
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

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <p className="text-slate-muted text-sm">{label}</p>
      <p className="text-2xl font-bold text-white mt-1">{value ?? 0}</p>
    </div>
  );
}
