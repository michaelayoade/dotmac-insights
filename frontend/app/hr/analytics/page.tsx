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
import { Activity, CalendarClock, ClipboardList, DollarSign, Factory, FileText, Users, UserPlus, Award, ArrowRightLeft, TrendingUp } from 'lucide-react';

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs text-slate-muted mb-1">{children}</label>;
}

function Stat({
  label,
  value,
  tone = 'text-amber-400',
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-lg p-4 flex items-center justify-between">
      <span className="text-slate-muted text-sm">{label}</span>
      <span className={cn('text-lg font-mono font-semibold', tone)}>{value}</span>
    </div>
  );
}

function PillList({ data, label }: { data: Record<string, number>; label?: string }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <p className="text-slate-muted text-sm">No data</p>;
  return (
    <div>
      {label && <p className="text-xs text-slate-muted mb-2">{label}</p>}
      <div className="flex flex-wrap gap-2">
        {entries.map(([k, v]) => (
          <span key={k} className="px-3 py-1 rounded-full border border-slate-border text-xs text-white bg-slate-elevated">
            <span className="text-slate-muted capitalize mr-1">{k.replace(/_/g, ' ')}:</span>
            <span className="font-mono">{v}</span>
          </span>
        ))}
      </div>
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
      {/* Filter */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <p className="text-xs text-slate-muted mb-3">Filter Analytics</p>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <FormLabel>Company</FormLabel>
            <input
              type="text"
              placeholder="All companies"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="Leave Applications (30d)" value={Object.values(overview?.leave_by_status || {}).reduce((a, b) => a + b, 0)} tone="text-amber-300" />
        <Stat label="Attendance Records (30d)" value={Object.values(overview?.attendance_status_30d || {}).reduce((a, b) => a + b, 0)} tone="text-emerald-300" />
        <Stat label="Net Payroll (30d)" value={formatCurrency(overview?.payroll_30d?.net_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-violet-300" />
      </div>

      {/* Leave & Attendance Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Leave by Status</h3>
          </div>
          <PillList data={overview?.leave_by_status || {}} />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-emerald-400" />
            <h3 className="text-white font-semibold">Attendance Status (30d)</h3>
          </div>
          <PillList data={overview?.attendance_status_30d || {}} />
        </div>
      </div>

      {/* Trends */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Leave Trend (Monthly)</h3>
          </div>
          <DataTable
            columns={[
              { key: 'month', header: 'Month', render: (item: any) => <span className="text-white font-medium">{item.month}</span> },
              { key: 'count', header: 'Applications', align: 'right' as const, render: (item: any) => <span className="font-mono text-amber-300">{item.count}</span> },
            ]}
            data={(leaveTrend || []).map((row, idx) => ({ ...row, id: `${row.month}-${idx}` }))}
            keyField="id"
            emptyMessage="No leave trend data"
          />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <h3 className="text-white font-semibold">Attendance Trend (Daily)</h3>
          </div>
          <DataTable
            columns={[
              { key: 'date', header: 'Date', render: (item: any) => <span className="text-white font-medium">{formatDate(item.date)}</span> },
              { key: 'total', header: 'Total Records', align: 'right' as const, render: (item: any) => <span className="font-mono text-emerald-300">{item.total ?? Object.values(item.status_counts || {}).reduce((a: number, b: any) => a + (b as number), 0)}</span> },
            ]}
            data={(attendanceTrend || []).map((row, idx) => ({ ...row, id: `${row.date}-${idx}` }))}
            keyField="id"
            emptyMessage="No attendance trend data"
          />
        </div>
      </div>

      {/* Payroll Summary */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-violet-400" />
          <h3 className="text-white font-semibold">Payroll Summary</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Gross Total" value={formatCurrency(payrollSummary?.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-white" />
          <Stat label="Deductions" value={formatCurrency(payrollSummary?.deduction_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-rose-300" />
          <Stat label="Net Total" value={formatCurrency(payrollSummary?.net_total || 0, 'NGN', { maximumFractionDigits: 0 })} tone="text-emerald-300" />
          <Stat label="Salary Slips" value={payrollSummary?.slip_count ?? 0} tone="text-violet-300" />
        </div>
      </div>

      {/* Payroll Trends & Components */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Payroll Trend (Monthly)</h3>
          </div>
          <DataTable
            columns={[
              { key: 'month', header: 'Month', render: (item: any) => <span className="text-white font-medium">{item.month}</span> },
              { key: 'net_total', header: 'Net Pay', align: 'right' as const, render: (item: any) => <span className="font-mono text-emerald-300">{formatCurrency(item.net_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
              { key: 'gross_total', header: 'Gross Pay', align: 'right' as const, render: (item: any) => <span className="font-mono text-slate-muted">{formatCurrency(item.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
            ]}
            data={(payrollTrend || []).map((row, idx) => ({ ...row, id: `${row.month}-${idx}` }))}
            keyField="id"
            emptyMessage="No payroll trend data"
          />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Factory className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Payroll Components</h3>
          </div>
          <DataTable
            columns={[
              { key: 'salary_component', header: 'Component Name', render: (item: any) => <span className="text-white font-medium">{item.salary_component}</span> },
              { key: 'component_type', header: 'Type', render: (item: any) => <span className={cn('text-xs px-2 py-0.5 rounded-full border', item.component_type === 'earning' ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10' : 'border-rose-500/40 text-rose-300 bg-rose-500/10')}>{(item.component_type || '').replace(/_/g, ' ')}</span> },
              { key: 'amount', header: 'Total Amount', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.amount || 0, 'NGN', { maximumFractionDigits: 0 })}</span> },
              { key: 'count', header: 'Count', align: 'right' as const, render: (item: any) => <span className="font-mono text-slate-muted">{item.count ?? 0}</span> },
            ]}
            data={payrollComponentRows}
            keyField="id"
            emptyMessage="No payroll component data"
          />
        </div>
      </div>

      {/* HR Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <UserPlus className="w-4 h-4 text-emerald-400" />
            <h3 className="text-white font-semibold">Recruitment Funnel</h3>
          </div>
          <PillList data={recruitmentFunnel?.openings || {}} label="Job Openings" />
          <PillList data={recruitmentFunnel?.applicants || {}} label="Applicants" />
          <PillList data={recruitmentFunnel?.offers || {}} label="Offers" />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Appraisal Status</h3>
          </div>
          <PillList data={appraisalStatus?.status_counts || {}} label="By Status" />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Lifecycle Events</h3>
          </div>
          <PillList data={lifecycleEvents?.onboarding || {}} label="Onboarding" />
          <PillList data={lifecycleEvents?.separation || {}} label="Separation" />
          <PillList data={lifecycleEvents?.promotion || {}} label="Promotions" />
          <PillList data={lifecycleEvents?.transfer || {}} label="Transfers" />
        </div>
      </div>
    </div>
  );
}
