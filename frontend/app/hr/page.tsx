'use client';

import { useMemo } from 'react';
import Link from 'next/link';
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
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatusFromArray } from '@/hooks/useSWRStatus';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import {
  CalendarClock,
  Briefcase,
  ClipboardList,
  GraduationCap,
  Users,
  TrendingUp,
  Wallet2,
  UserPlus,
  Clock3,
  Target,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Timer,
} from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

// Warm People color palette
const HR_COLORS = {
  primary: '#f59e0b', // Amber
  secondary: '#8b5cf6', // Violet
  accent: '#ec4899', // Pink
  success: '#10b981', // Emerald
  warning: '#f97316', // Orange
  info: '#06b6d4', // Cyan
};

const CHART_COLORS = ['#f59e0b', '#8b5cf6', '#ec4899', '#10b981', '#f97316', '#06b6d4'];

function MetricCard({
  label,
  value,
  icon: Icon,
  trend,
  trendLabel,
  className,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  className?: string;
}) {
  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl p-5', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
          {trendLabel && (
            <div className="flex items-center gap-1 mt-2">
              {trend === 'up' && <TrendingUp className="w-3 h-3 text-emerald-400" />}
              {trend === 'down' && <TrendingUp className="w-3 h-3 text-rose-400 rotate-180" />}
              <span className={cn('text-xs', trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-rose-400' : 'text-slate-muted')}>
                {trendLabel}
              </span>
            </div>
          )}
        </div>
        <div className="p-3 bg-amber-500/10 rounded-xl">
          <Icon className="w-6 h-6 text-amber-400" />
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="mb-4">
        <h3 className="text-white font-semibold">{title}</h3>
        {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function WorkflowStep({
  step,
  title,
  description,
  icon: Icon,
  href,
  status,
}: {
  step: number;
  title: string;
  description: string;
  icon: React.ElementType;
  href: string;
  status: 'active' | 'pending' | 'complete';
}) {
  return (
    <Link
      href={href}
      className={cn(
        'relative flex flex-col p-4 rounded-xl border transition-all group',
        status === 'active' && 'bg-amber-500/10 border-amber-500/40 hover:border-amber-400',
        status === 'pending' && 'bg-slate-card border-slate-border hover:border-violet-500/40',
        status === 'complete' && 'bg-emerald-500/10 border-emerald-500/40'
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
            status === 'active' && 'bg-amber-500 text-slate-900',
            status === 'pending' && 'bg-slate-elevated text-slate-muted',
            status === 'complete' && 'bg-emerald-500 text-white'
          )}
        >
          {status === 'complete' ? <CheckCircle2 className="w-4 h-4" /> : step}
        </div>
        <Icon className={cn('w-5 h-5', status === 'active' ? 'text-amber-400' : status === 'complete' ? 'text-emerald-400' : 'text-slate-muted')} />
      </div>
      <h4 className="text-white font-medium text-sm">{title}</h4>
      <p className="text-slate-muted text-xs mt-1">{description}</p>
      <ArrowRight className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted opacity-0 group-hover:opacity-100 transition-opacity" />
    </Link>
  );
}

function ActionItem({
  icon: Icon,
  title,
  count,
  href,
  urgency,
}: {
  icon: React.ElementType;
  title: string;
  count: number;
  href: string;
  urgency: 'high' | 'medium' | 'low';
}) {
  if (count === 0) return null;
  return (
    <Link
      href={href}
      className="flex items-center justify-between p-3 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors group"
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'p-2 rounded-lg',
            urgency === 'high' && 'bg-rose-500/10',
            urgency === 'medium' && 'bg-amber-500/10',
            urgency === 'low' && 'bg-slate-card'
          )}
        >
          <Icon
            className={cn(
              'w-4 h-4',
              urgency === 'high' && 'text-rose-400',
              urgency === 'medium' && 'text-amber-400',
              urgency === 'low' && 'text-slate-muted'
            )}
          />
        </div>
        <span className="text-sm text-white">{title}</span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium',
            urgency === 'high' && 'bg-rose-500/20 text-rose-300',
            urgency === 'medium' && 'bg-amber-500/20 text-amber-300',
            urgency === 'low' && 'bg-slate-card text-slate-muted'
          )}
        >
          {count}
        </span>
        <ArrowRight className="w-4 h-4 text-slate-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </Link>
  );
}

export default function HrOverviewPage() {
  const { data: leaveTypes, error: leaveTypesError, isLoading: leaveTypesLoading, mutate: refetchLeaveTypes } = useHrLeaveTypes({ limit: 50 });
  const { data: holidayLists, error: holidayError, isLoading: holidayLoading, mutate: refetchHoliday } = useHrHolidayLists({ limit: 1 });
  const { data: leaveApplications, error: leaveAppsError, isLoading: leaveAppsLoading, mutate: refetchLeaveApps } = useHrLeaveApplications({ status: 'open', limit: 10 });
  const { data: shiftAssignments, error: shiftError, isLoading: shiftLoading, mutate: refetchShift } = useHrShiftAssignments({ limit: 10 });
  const { data: jobOpenings, error: jobsError, isLoading: jobsLoading, mutate: refetchJobs } = useHrJobOpenings({ status: 'open', limit: 10 });
  const { data: payrollEntries, error: payrollError, isLoading: payrollLoading, mutate: refetchPayroll } = useHrPayrollEntries({ limit: 10 });
  const { data: trainingEvents, error: trainingError, isLoading: trainingLoading, mutate: refetchTraining } = useHrTrainingEvents({ status: 'scheduled', limit: 10 });
  const { data: onboardings, error: onboardingError, isLoading: onboardingLoading, mutate: refetchOnboarding } = useHrEmployeeOnboardings({ limit: 10 });
  const { data: analyticsOverview, error: analyticsError, isLoading: analyticsLoading, mutate: refetchAnalytics } = useHrAnalyticsOverview();
  const { data: leaveTrend, error: leaveTrendError, isLoading: leaveTrendLoading, mutate: refetchLeaveTrend } = useHrAnalyticsLeaveTrend({ months: 6 });
  const { data: attendanceTrend, error: attendanceError, isLoading: attendanceLoading, mutate: refetchAttendance } = useHrAnalyticsAttendanceTrend({ days: 14 });

  const swrStates = [
    { error: leaveTypesError, isLoading: leaveTypesLoading, mutate: refetchLeaveTypes },
    { error: holidayError, isLoading: holidayLoading, mutate: refetchHoliday },
    { error: leaveAppsError, isLoading: leaveAppsLoading, mutate: refetchLeaveApps },
    { error: shiftError, isLoading: shiftLoading, mutate: refetchShift },
    { error: jobsError, isLoading: jobsLoading, mutate: refetchJobs },
    { error: payrollError, isLoading: payrollLoading, mutate: refetchPayroll },
    { error: trainingError, isLoading: trainingLoading, mutate: refetchTraining },
    { error: onboardingError, isLoading: onboardingLoading, mutate: refetchOnboarding },
    { error: analyticsError, isLoading: analyticsLoading, mutate: refetchAnalytics },
    { error: leaveTrendError, isLoading: leaveTrendLoading, mutate: refetchLeaveTrend },
    { error: attendanceError, isLoading: attendanceLoading, mutate: refetchAttendance },
  ];

  const { isLoading, error } = useSWRStatusFromArray(swrStates);
  const retryAll = () => swrStates.forEach((state) => state.mutate && state.mutate());

  // Memoized chart data - must be called unconditionally before early returns
  const payroll30d = useMemo(() => analyticsOverview?.payroll_30d || {}, [analyticsOverview]);

  // Transform leave trend data for chart
  const leaveTrendData = useMemo(() => {
    return (leaveTrend || []).map((item: any) => ({
      month: item.month,
      applications: item.count,
    }));
  }, [leaveTrend]);

  // Transform attendance trend data for chart
  const attendanceTrendData = useMemo(() => {
    return (attendanceTrend || []).slice(-7).map((item: any) => {
      const counts = item.status_counts || {};
      return {
        date: formatDate(item.date).split(',')[0],
        present: counts.present || counts.Present || 0,
        absent: counts.absent || counts.Absent || 0,
        late: counts.late || counts.Late || 0,
      };
    });
  }, [attendanceTrend]);

  // Leave status distribution for pie chart
  const leaveStatusData = useMemo(() => {
    const leaveByStatus = analyticsOverview?.leave_by_status || {};
    return Object.entries(leaveByStatus).map(([status, count], idx) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count as number,
      color: CHART_COLORS[idx % CHART_COLORS.length],
    }));
  }, [analyticsOverview]);

  // Recruitment funnel data
  const funnelData = useMemo(() => {
    const recruitmentFunnel = analyticsOverview?.recruitment_funnel || {};
    const stages = [
      { name: 'Applications', key: 'applications', color: '#8b5cf6' },
      { name: 'Screened', key: 'screened', color: '#06b6d4' },
      { name: 'Interviewed', key: 'interviewed', color: '#f59e0b' },
      { name: 'Offered', key: 'offered', color: '#10b981' },
      { name: 'Hired', key: 'hired', color: '#ec4899' },
    ];
    return stages.map((stage) => ({
      ...stage,
      value: recruitmentFunnel[stage.key] || 0,
    }));
  }, [analyticsOverview]);

  const leaveAppList = extractList(leaveApplications);
  const leaveTypeList = extractList(leaveTypes);
  const jobOpeningList = extractList(jobOpenings);
  const payrollEntryList = extractList(payrollEntries);
  const trainingEventList = extractList(trainingEvents);
  const onboardingList = extractList(onboardings);
  const shiftAssignmentList = extractList(shiftAssignments);

  const attendanceStatus = analyticsOverview?.attendance_status_30d || {};

  return (
    <DashboardShell
      isLoading={isLoading}
      error={error}
      onRetry={retryAll}
      errorMessage="Failed to load HR overview data"
    >
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-amber-500/10 via-violet-500/5 to-slate-card border border-amber-500/20 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white">Overview</h2>
            <p className="text-slate-muted text-sm mt-1">People operations at a glance</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/hr/leave"
              className="px-4 py-2 bg-amber-500/20 text-amber-300 rounded-lg text-sm font-medium hover:bg-amber-500/30 transition-colors flex items-center gap-2"
            >
              <CalendarClock className="w-4 h-4" />
              Manage Leave
            </Link>
            <Link
              href="/hr/payroll"
              className="px-4 py-2 bg-violet-500/20 text-violet-300 rounded-lg text-sm font-medium hover:bg-violet-500/30 transition-colors flex items-center gap-2"
            >
              <Wallet2 className="w-4 h-4" />
              Run Payroll
            </Link>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Open Leave Requests"
          value={leaveAppList.total}
          icon={CalendarClock}
          trend={leaveAppList.total > 5 ? 'up' : 'neutral'}
          trendLabel={leaveAppList.total > 5 ? 'Needs attention' : 'Under control'}
        />
        <MetricCard
          label="Open Positions"
          value={jobOpeningList.total}
          icon={Briefcase}
          trend="neutral"
          trendLabel="Active recruiting"
        />
        <MetricCard
          label="Upcoming Trainings"
          value={trainingEventList.total}
          icon={GraduationCap}
          trend="neutral"
          trendLabel="Scheduled"
        />
        <MetricCard
          label="Active Onboardings"
          value={onboardingList.total}
          icon={UserPlus}
          trend={onboardingList.total > 0 ? 'up' : 'neutral'}
          trendLabel={onboardingList.total > 0 ? 'New hires' : 'No pending'}
        />
      </div>

      {/* People Workflow */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-white font-semibold">People Workflow</h3>
            <p className="text-slate-muted text-sm">Employee lifecycle management</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <WorkflowStep
            step={1}
            title="Recruit"
            description="Source and hire talent"
            icon={Briefcase}
            href="/hr/recruitment"
            status="active"
          />
          <WorkflowStep
            step={2}
            title="Onboard"
            description="Welcome new employees"
            icon={UserPlus}
            href="/hr/lifecycle"
            status={onboardingList.total > 0 ? 'active' : 'pending'}
          />
          <WorkflowStep
            step={3}
            title="Manage"
            description="Leave, attendance, shifts"
            icon={Clock3}
            href="/hr/attendance"
            status="pending"
          />
          <WorkflowStep
            step={4}
            title="Develop"
            description="Training & appraisals"
            icon={Target}
            href="/hr/training"
            status="pending"
          />
          <WorkflowStep
            step={5}
            title="Compensate"
            description="Run payroll cycles"
            icon={Wallet2}
            href="/hr/payroll"
            status="pending"
          />
        </div>
      </div>

      {/* Pending Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-white font-semibold mb-3">Pending Actions</h3>
          <div className="space-y-2">
            <ActionItem
              icon={CalendarClock}
              title="Leave requests awaiting approval"
              count={leaveAppList.total}
              href="/hr/leave"
              urgency={leaveAppList.total > 5 ? 'high' : leaveAppList.total > 0 ? 'medium' : 'low'}
            />
            <ActionItem
              icon={Briefcase}
              title="Job openings to review"
              count={jobOpeningList.total}
              href="/hr/recruitment"
              urgency="medium"
            />
            <ActionItem
              icon={UserPlus}
              title="Employees in onboarding"
              count={onboardingList.total}
              href="/hr/lifecycle"
              urgency={onboardingList.total > 0 ? 'medium' : 'low'}
            />
            <ActionItem
              icon={GraduationCap}
              title="Upcoming training sessions"
              count={trainingEventList.total}
              href="/hr/training"
              urgency="low"
            />
          </div>
        </div>

        {/* Payroll Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-white font-semibold mb-1">Payroll (Last 30 Days)</h3>
          <p className="text-slate-muted text-sm mb-4">{payroll30d.slip_count || 0} salary slips processed</p>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
              <span className="text-slate-muted text-sm">Gross Pay</span>
              <span className="text-white font-mono font-medium">
                {formatCurrency(payroll30d.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
              <span className="text-slate-muted text-sm">Deductions</span>
              <span className="text-rose-400 font-mono font-medium">
                -{formatCurrency(payroll30d.deduction_total || 0, 'NGN', { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
              <span className="text-emerald-400 text-sm font-medium">Net Pay</span>
              <span className="text-emerald-400 font-mono font-bold">
                {formatCurrency(payroll30d.net_total || 0, 'NGN', { maximumFractionDigits: 0 })}
              </span>
            </div>
          </div>
          <Link
            href="/hr/payroll"
            className="mt-4 flex items-center justify-center gap-2 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            View Payroll Details <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Leave Status Distribution */}
        <ChartCard title="Leave Status" subtitle="Current distribution">
          {leaveStatusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={leaveStatusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {leaveStatusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f8fafc' }}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No leave data</div>
          )}
        </ChartCard>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Leave Trend */}
        <ChartCard title="Leave Applications" subtitle="Monthly trend">
          {leaveTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={leaveTrendData}>
                <defs>
                  <linearGradient id="leaveGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="month" stroke="#64748b" tick={{ fontSize: 12 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f8fafc' }}
                />
                <Area
                  type="monotone"
                  dataKey="applications"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fill="url(#leaveGradient)"
                  name="Applications"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">No trend data</div>
          )}
        </ChartCard>

        {/* Attendance Trend */}
        <ChartCard title="Attendance" subtitle="Last 7 days">
          {attendanceTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={attendanceTrendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 12 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#f8fafc' }}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs capitalize">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Bar dataKey="present" stackId="a" fill="#10b981" name="Present" radius={[0, 0, 0, 0]} />
                <Bar dataKey="late" stackId="a" fill="#f59e0b" name="Late" radius={[0, 0, 0, 0]} />
                <Bar dataKey="absent" stackId="a" fill="#ef4444" name="Absent" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">No attendance data</div>
          )}
        </ChartCard>
      </div>

      {/* Recruitment Funnel */}
      <ChartCard title="Recruitment Funnel" subtitle="Candidate progression">
        <div className="grid grid-cols-5 gap-2">
          {funnelData.map((stage, idx) => {
            const maxVal = Math.max(...funnelData.map((s) => s.value), 1);
            const height = (stage.value / maxVal) * 100;
            return (
              <div key={stage.key} className="flex flex-col items-center">
                <div className="h-32 w-full flex items-end justify-center">
                  <div
                    className="w-full max-w-[60px] rounded-t-lg transition-all duration-500"
                    style={{
                      height: `${Math.max(height, 10)}%`,
                      backgroundColor: stage.color,
                      opacity: stage.value > 0 ? 1 : 0.3,
                    }}
                  />
                </div>
                <span className="text-2xl font-bold text-white mt-2">{stage.value}</span>
                <span className="text-xs text-slate-muted text-center">{stage.name}</span>
              </div>
            );
          })}
        </div>
        <Link
          href="/hr/recruitment"
          className="mt-4 flex items-center justify-center gap-2 text-sm text-violet-400 hover:text-violet-300 transition-colors"
        >
          View Recruitment Pipeline <ArrowRight className="w-4 h-4" />
        </Link>
      </ChartCard>

      {/* Quick Stats Footer */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-white">{leaveTypeList.total}</p>
          <p className="text-slate-muted text-sm">Leave Types</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-white">{shiftAssignmentList.total}</p>
          <p className="text-slate-muted text-sm">Shift Assignments</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-white">{payrollEntryList.total}</p>
          <p className="text-slate-muted text-sm">Payroll Runs</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-white">{attendanceStatus.present || attendanceStatus.Present || 0}</p>
          <p className="text-slate-muted text-sm">Present Today</p>
        </div>
      </div>
    </div>
    </DashboardShell>
  );
}
