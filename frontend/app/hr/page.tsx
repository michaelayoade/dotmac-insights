'use client';

import { useMemo } from 'react';
import { DataTable } from '@/components/DataTable';
import {
  useHrLeaveTypes,
  useHrHolidayLists,
  useHrLeaveApplications,
  useHrShiftAssignments,
  useHrJobOpenings,
  useHrPayrollEntries,
  useHrTrainingEvents,
  useHrEmployeeOnboardings,
  useHrAnalyticsOverview,
  useHrAnalyticsLeaveTrend,
  useHrAnalyticsAttendanceTrend,
} from '@/hooks/useApi';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { CalendarClock, Briefcase, ClipboardList, GraduationCap, Layers, Users } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'text-teal-electric',
  hint,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tone?: string;
  hint?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-start justify-between">
      <div>
        <p className="text-slate-muted text-sm">{label}</p>
        <p className={cn('text-2xl font-bold text-white', tone)}>{value}</p>
        {hint && <p className="text-slate-muted text-xs mt-1">{hint}</p>}
      </div>
      <div className="p-2 bg-slate-elevated rounded-lg">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

export default function HrOverviewPage() {
  const { data: leaveTypes } = useHrLeaveTypes({ limit: 50 });
  const { data: holidayLists } = useHrHolidayLists({ limit: 1 });
  const { data: leaveApplications } = useHrLeaveApplications({ status: 'open', limit: 10 });
  const { data: shiftAssignments } = useHrShiftAssignments({ limit: 10 });
  const { data: jobOpenings } = useHrJobOpenings({ status: 'open', limit: 10 });
  const { data: payrollEntries } = useHrPayrollEntries({ limit: 10 });
  const { data: trainingEvents } = useHrTrainingEvents({ status: 'scheduled', limit: 10 });
  const { data: onboardings } = useHrEmployeeOnboardings({ limit: 10 });
  const { data: analyticsOverview } = useHrAnalyticsOverview();
  const { data: leaveTrend } = useHrAnalyticsLeaveTrend({ months: 6 });
  const { data: attendanceTrend } = useHrAnalyticsAttendanceTrend({ days: 14 });

  const holidayList = useMemo(() => extractList(holidayLists).items?.[0] || null, [holidayLists]);
  const holidays = useMemo(
    () =>
      (holidayList?.holidays || [])
        .slice(0, 5)
        .map((h: any, idx: number) => ({ ...h, rowId: `${h.holiday_date}-${idx}` })),
    [holidayList]
  );

  const leaveAppList = extractList(leaveApplications);
  const leaveTypeList = extractList(leaveTypes);
  const jobOpeningList = extractList(jobOpenings);
  const payrollEntryList = extractList(payrollEntries);
  const trainingEventList = extractList(trainingEvents);
  const onboardingList = extractList(onboardings);
  const shiftAssignmentList = extractList(shiftAssignments);

  const openLeaveApplications = (leaveAppList.items || []).slice(0, 5).map((item: any) => ({
    ...item,
    rowId: item.id || `${item.employee}-${item.from_date}`,
  }));

  const openJobs = (jobOpeningList.items || []).slice(0, 5).map((item: any) => ({
    ...item,
    rowId: item.id || `${item.job_title}-${item.company || ''}`,
  }));

  const leaveByStatus = analyticsOverview?.leave_by_status || {};
  const attendanceStatus = analyticsOverview?.attendance_status_30d || {};
  const payroll30d = analyticsOverview?.payroll_30d || {};
  const recruitmentFunnel = analyticsOverview?.recruitment_funnel || {};

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Leave Types" value={leaveTypeList.total} icon={Layers} tone="text-blue-300" />
        <StatCard label="Open Leave Requests" value={leaveAppList.total} icon={CalendarClock} tone="text-amber-300" />
        <StatCard label="Open Job Openings" value={jobOpeningList.total} icon={Briefcase} tone="text-teal-electric" />
        <StatCard label="Active Shift Assignments" value={shiftAssignmentList.total} icon={ClipboardList} tone="text-purple-300" />
      </div>

      {/* Analytics snapshot */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Leave by Status</h3>
          <div className="space-y-2">
            {Object.keys(leaveByStatus).length === 0 && <p className="text-slate-muted text-sm">No data</p>}
            {Object.entries(leaveByStatus).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between text-sm">
                <span className="text-slate-muted capitalize">{status}</span>
                <span className="font-mono text-white">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Attendance (30d)</h3>
          <div className="space-y-2">
            {Object.keys(attendanceStatus).length === 0 && <p className="text-slate-muted text-sm">No data</p>}
            {Object.entries(attendanceStatus).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between text-sm">
                <span className="text-slate-muted capitalize">{status}</span>
                <span className="font-mono text-white">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <h3 className="text-white font-semibold">Payroll (30d)</h3>
          <div className="space-y-1 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Gross</span>
              <span className="font-mono text-white">{formatCurrency(payroll30d.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Deductions</span>
              <span className="font-mono text-white">{formatCurrency(payroll30d.deduction_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Net</span>
              <span className="font-mono text-white">{formatCurrency(payroll30d.net_total || 0, 'NGN', { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Slips</span>
              <span className="font-mono text-white">{payroll30d.slip_count ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Trends */}
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Upcoming Holidays</h3>
          </div>
          <p className="text-slate-muted text-sm">
            {holidayList ? `${holidayList.holiday_list_name || 'Holiday List'}` : 'No holiday list loaded'}
          </p>
          <DataTable
            columns={[
              { key: 'holiday_date', header: 'Date', render: (item: any) => <span className="text-white">{formatDate(item.holiday_date)}</span> },
              { key: 'description', header: 'Description', render: (item: any) => <span className="text-slate-muted text-sm">{item.description || '—'}</span> },
              {
                key: 'weekly_off',
                header: 'Weekly Off',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border', item.weekly_off ? 'text-green-400 border-green-500/40 bg-green-500/10' : 'text-slate-muted border-slate-border')}>
                    {item.weekly_off ? 'Yes' : 'No'}
                  </span>
                ),
              },
            ]}
            data={holidays}
            keyField="rowId"
            emptyMessage="No holidays scheduled"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Open Positions</h3>
          </div>
          <DataTable
            columns={[
              { key: 'job_title', header: 'Role', render: (item: any) => <span className="text-white">{item.job_title}</span> },
              { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
              { key: 'posting_date', header: 'Posted', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span> },
              { key: 'vacancies', header: 'Slots', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{item.vacancies ?? '—'}</span> },
            ]}
            data={openJobs}
            keyField="rowId"
            emptyMessage="No open job openings"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Pending Leave Requests</h3>
          </div>
          <DataTable
            columns={[
              { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
              { key: 'leave_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm">{item.leave_type || '—'}</span> },
              { key: 'from_date', header: 'From', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.from_date)}</span> },
              { key: 'to_date', header: 'To', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.to_date)}</span> },
              {
                key: 'status',
                header: 'Status',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', 'border-amber-400/40 text-amber-300 bg-amber-500/10')}>
                    {item.status || 'open'}
                  </span>
                ),
              },
            ]}
            data={openLeaveApplications}
            keyField="rowId"
            emptyMessage="No pending requests"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Upcoming Trainings"
          value={trainingEventList.total}
          icon={GraduationCap}
          tone="text-cyan-300"
          hint="Scheduled training events"
        />
        <StatCard
          label="Payroll Runs"
          value={payrollEntryList.total}
          icon={ClipboardList}
          tone="text-green-300"
          hint="Payroll entries created"
        />
        <StatCard
          label="Active Onboardings"
          value={onboardingList.total}
          icon={Users}
          tone="text-purple-300"
          hint="Employees in onboarding flow"
        />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <ClipboardList className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Recent Payroll Entries</h3>
        </div>
        <DataTable
          columns={[
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-white">{item.company}</span> },
            { key: 'posting_date', header: 'Posting', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span> },
            { key: 'payroll_frequency', header: 'Frequency', render: (item: any) => <span className="text-slate-muted text-sm">{item.payroll_frequency || '—'}</span> },
            { key: 'start_date', header: 'Period', render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span> },
            { key: 'status', header: 'Status', render: (item: any) => <span className="text-teal-electric text-sm capitalize">{item.status || 'draft'}</span> },
          ]}
          data={(payrollEntryList.items || []).slice(0, 6).map((item: any) => ({ ...item, rowId: item.id || item.posting_date }))}
          keyField="rowId"
          emptyMessage="No payroll entries yet"
        />
      </div>
    </div>
  );
}
