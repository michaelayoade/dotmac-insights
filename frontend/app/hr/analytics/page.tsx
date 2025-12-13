'use client';

import { useState, useMemo } from 'react';
import { DataTable } from '@/components/DataTable';
import {
  useHrAnalyticsOverview,
  useHrAnalyticsLeaveTrend,
  useHrAnalyticsAttendanceTrend,
  useHrAnalyticsPayrollSummary,
  useHrAnalyticsPayrollTrend,
  useHrAnalyticsPayrollComponents,
  useHrAnalyticsRecruitmentFunnel,
  useHrAnalyticsAppraisalStatus,
  useHrAnalyticsLifecycleEvents,
} from '@/hooks/useApi';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { Activity, CalendarClock, ClipboardList, DollarSign, Factory, FileText, Users } from 'lucide-react';

function Stat({
  label,
  value,
  tone = 'text-teal-electric',
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-lg p-4 flex items-center justify-between">
      <span className="text-slate-muted text-sm">{label}</span>
      <span className={cn('text-lg font-mono font-semibold text-white', tone)}>{value}</span>
    </div>
  );
}

function PillList({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <p className="text-slate-muted text-sm">No data</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([k, v]) => (
        <span key={k} className="px-3 py-1 rounded-full border border-slate-border text-xs text-white bg-slate-elevated">
          <span className="text-slate-muted capitalize mr-1">{k}:</span>
          <span className="font-mono">{v}</span>
        </span>
      ))}
    </div>
  );
}

export default function HrAnalyticsPage() {
  const [company, setCompany] = useState('');
  const { data: overview } = useHrAnalyticsOverview({ company: company || undefined });
  const { data: leaveTrend } = useHrAnalyticsLeaveTrend({ company: company || undefined, months: 6 });
  const { data: attendanceTrend } = useHrAnalyticsAttendanceTrend({ company: company || undefined, days: 14 });
  const { data: payrollSummary } = useHrAnalyticsPayrollSummary({ company: company || undefined });
  const { data: payrollTrend } = useHrAnalyticsPayrollTrend({ company: company || undefined });
  const { data: payrollComponents } = useHrAnalyticsPayrollComponents({ company: company || undefined, limit: 20 });
  const { data: recruitmentFunnel } = useHrAnalyticsRecruitmentFunnel({ company: company || undefined });
  const { data: appraisalStatus } = useHrAnalyticsAppraisalStatus({ company: company || undefined });
  const { data: lifecycleEvents } = useHrAnalyticsLifecycleEvents({ company: company || undefined });

  const payrollComponentRows = useMemo(
    () => (payrollComponents || []).map((item, idx) => ({ ...item, id: item.salary_component || idx })),
    [payrollComponents]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Filter by company"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="Leave (30d)" value={Object.values(overview?.leave_by_status || {}).reduce((a, b) => a + b, 0)} tone="text-amber-300" />
        <Stat label="Attendance (30d)" value={Object.values(overview?.attendance_status_30d || {}).reduce((a, b) => a + b, 0)} tone="text-green-300" />
        <Stat label="Payroll Net (30d)" value={formatCurrency(overview?.payroll_30d?.net_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-teal-electric" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Leave by Status</h3>
          </div>
          <PillList data={overview?.leave_by_status || {}} />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Attendance (30d) by Status</h3>
          </div>
          <PillList data={overview?.attendance_status_30d || {}} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <CalendarClock className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Leave Trend (monthly)</h3>
          </div>
          <DataTable
            columns={[
              { key: 'month', header: 'Month', render: (item: any) => <span className="text-white">{item.month}</span> },
              { key: 'count', header: 'Applications', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{item.count}</span> },
            ]}
            data={(leaveTrend || []).map((row, idx) => ({ ...row, id: `${row.month}-${idx}` }))}
            keyField="id"
            emptyMessage="No leave trend data"
          />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Attendance Trend (daily)</h3>
          </div>
          <DataTable
            columns={[
              { key: 'date', header: 'Date', render: (item: any) => <span className="text-white">{formatDate(item.date)}</span> },
              { key: 'total', header: 'Total', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{item.total ?? Object.values(item.status_counts || {}).reduce((a: number, b: any) => a + (b as number), 0)}</span> },
            ]}
            data={(attendanceTrend || []).map((row, idx) => ({ ...row, id: `${row.date}-${idx}` }))}
            keyField="id"
            emptyMessage="No attendance trend data"
          />
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Payroll Summary</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Gross" value={formatCurrency(payrollSummary?.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })} />
          <Stat label="Deductions" value={formatCurrency(payrollSummary?.deduction_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-amber-300" />
          <Stat label="Net" value={formatCurrency(payrollSummary?.net_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-green-300" />
          <Stat label="Slips" value={payrollSummary?.slip_count ?? 0} tone="text-purple-300" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Payroll Trend</h3>
          </div>
          <DataTable
            columns={[
              { key: 'month', header: 'Month', render: (item: any) => <span className="text-white">{item.month}</span> },
              { key: 'net_total', header: 'Net', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.net_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
              { key: 'gross_total', header: 'Gross', align: 'right' as const, render: (item: any) => <span className="font-mono text-slate-muted">{formatCurrency(item.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
            ]}
            data={(payrollTrend || []).map((row, idx) => ({ ...row, id: `${row.month}-${idx}` }))}
            keyField="id"
            emptyMessage="No payroll trend data"
          />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Factory className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Payroll Components</h3>
          </div>
          <DataTable
            columns={[
              { key: 'salary_component', header: 'Component', render: (item: any) => <span className="text-white">{item.salary_component}</span> },
              { key: 'component_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.component_type}</span> },
              { key: 'amount', header: 'Amount', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.amount || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
              { key: 'count', header: '#', align: 'right' as const, render: (item: any) => <span className="font-mono text-slate-muted">{item.count ?? 0}</span> },
            ]}
            data={payrollComponentRows}
            keyField="id"
            emptyMessage="No payroll component data"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Recruitment Funnel</h3>
          <PillList data={recruitmentFunnel?.openings || {}} />
          <PillList data={recruitmentFunnel?.applicants || {}} />
          <PillList data={recruitmentFunnel?.offers || {}} />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Appraisal Status</h3>
          <PillList data={appraisalStatus?.status_counts || {}} />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Lifecycle Events</h3>
          <PillList data={lifecycleEvents?.onboarding || {}} />
          <PillList data={lifecycleEvents?.separation || {}} />
          <PillList data={lifecycleEvents?.promotion || {}} />
          <PillList data={lifecycleEvents?.transfer || {}} />
        </div>
      </div>
    </div>
  );
}
