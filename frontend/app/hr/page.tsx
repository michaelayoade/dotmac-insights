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
import { useConsolidatedHRDashboard } from '@/hooks/useApi';
import type { HRDashboardResponse } from '@/lib/api/domains/dashboards';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  CalendarClock,
  Briefcase,
  GraduationCap,
  Wallet2,
  UserPlus,
  Clock3,
  Target,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

// Chart colors from centralized design tokens
const CHART_COLORS = [
  'var(--color-amber-warn)',
  'var(--color-purple-accent)',
  'var(--color-coral-alert)',
  'var(--color-teal-electric)',
  'var(--color-cyan-accent)',
  'var(--color-blue-info)',
];


function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="mb-4">
        <h3 className="text-foreground font-semibold">{title}</h3>
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
            status === 'complete' && 'bg-emerald-500 text-foreground'
          )}
        >
          {status === 'complete' ? <CheckCircle2 className="w-4 h-4" /> : step}
        </div>
        <Icon className={cn('w-5 h-5', status === 'active' ? 'text-amber-400' : status === 'complete' ? 'text-emerald-400' : 'text-slate-muted')} />
      </div>
      <h4 className="text-foreground font-medium text-sm">{title}</h4>
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
        <span className="text-sm text-foreground">{title}</span>
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
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('hr:read');
  const canFetch = !authLoading && !missingScope;

  const { data: dashboard, error, isLoading, mutate: refetchDashboard } = useConsolidatedHRDashboard(
    { isPaused: () => !canFetch }
  );
  const safeDashboard = dashboard as HRDashboardResponse | undefined;

  // Memoized chart data - must be called unconditionally before early returns
  const payroll30d = useMemo<HRDashboardResponse['payroll_30d']>(() => (
    safeDashboard?.payroll_30d || { slip_count: 0, gross_total: 0, deduction_total: 0, net_total: 0 }
  ), [safeDashboard]);

  // Transform leave trend data for chart
  const leaveTrendData = useMemo(() => {
    return (safeDashboard?.leave?.trend || []).map((item: any) => ({
      month: item.month,
      applications: item.count,
    }));
  }, [safeDashboard]);

  // Transform attendance trend data for chart
  const attendanceTrendData = useMemo(() => {
    return (safeDashboard?.attendance?.trend || []).slice(-7).map((item: any) => {
      const counts = item.status_counts || {};
      return {
        date: formatDate(item.date).split(',')[0],
        present: counts.present || counts.Present || 0,
        absent: counts.absent || counts.Absent || 0,
        late: counts.late || counts.Late || 0,
      };
    });
  }, [safeDashboard]);

  const attendanceStatusData = useMemo(() => {
    const statusCounts = safeDashboard?.attendance?.status_30d || {};
    return Object.entries(statusCounts).map(([status, count]) => ({
      label: status,
      value: count as number,
    }));
  }, [safeDashboard]);

  // Leave status distribution for pie chart
  const leaveStatusData = useMemo(() => {
    const leaveByStatus = safeDashboard?.leave?.by_status || {};
    return Object.entries(leaveByStatus).map(([status, count], idx) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count as number,
      color: CHART_COLORS[idx % CHART_COLORS.length],
    }));
  }, [safeDashboard]);

  // Recruitment funnel data
  const funnelData = useMemo(() => {
    const recruitmentFunnel: HRDashboardResponse['recruitment']['funnel'] = safeDashboard?.recruitment?.funnel ?? {
      applications: 0,
      screened: 0,
      interviewed: 0,
      offered: 0,
      hired: 0,
    };
    const stages = [
      { name: 'Applications', key: 'applications', color: '#8b5cf6' },
      { name: 'Screened', key: 'screened', color: '#06b6d4' },
      { name: 'Interviewed', key: 'interviewed', color: '#f59e0b' },
      { name: 'Offered', key: 'offered', color: '#10b981' },
      { name: 'Hired', key: 'hired', color: '#ec4899' },
    ] satisfies Array<{ name: string; key: keyof HRDashboardResponse['recruitment']['funnel']; color: string }>;
    return stages.map((stage) => ({
      ...stage,
      value: recruitmentFunnel[stage.key] ?? 0,
    }));
  }, [safeDashboard]);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view the HR dashboard."
        backHref="/"
        backLabel="Back to Home"
      />
    );
  }

  return (
    <DashboardShell
      isLoading={isLoading}
      error={error}
      onRetry={refetchDashboard}
      softError
    >
      <div className="space-y-6">
        {error && (
          <ErrorDisplay
            message="Failed to load HR overview data."
            error={error as Error}
            onRetry={refetchDashboard}
          />
        )}
        {/* Hero Section */}
        <div className="bg-gradient-to-br from-amber-500/10 via-violet-500/5 to-slate-card border border-amber-500/20 rounded-2xl p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-foreground">Overview</h2>
              <p className="text-slate-muted text-sm mt-1">People operations at a glance</p>
              {safeDashboard?.generated_at && (
                <p className="text-slate-muted text-xs mt-2">Updated {formatDate(safeDashboard.generated_at)}</p>
              )}
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
        <StatCard
          title="Open Leave Requests"
          value={safeDashboard?.leave?.pending_approvals || 0}
          icon={CalendarClock}
          colorClass="text-amber-400"
          trend={(safeDashboard?.leave?.pending_approvals || 0) > 5 ? { value: 1, label: 'Needs attention' } : { value: 0, label: 'Under control' }}
        />
        <StatCard
          title="Open Positions"
          value={safeDashboard?.recruitment?.open_positions || 0}
          icon={Briefcase}
          colorClass="text-amber-400"
          trend={{ value: 0, label: 'Active recruiting' }}
        />
        <StatCard
          title="Upcoming Trainings"
          value={safeDashboard?.training?.scheduled_events || 0}
          icon={GraduationCap}
          colorClass="text-amber-400"
          trend={{ value: 0, label: 'Scheduled' }}
        />
        <StatCard
          title="Active Onboardings"
          value={safeDashboard?.onboarding?.active_count || 0}
          icon={UserPlus}
          colorClass="text-amber-400"
          trend={(safeDashboard?.onboarding?.active_count || 0) > 0 ? { value: 1, label: 'New hires' } : { value: 0, label: 'No pending' }}
        />
      </div>

      {/* People Workflow */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-foreground font-semibold">People Workflow</h3>
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
            status={(safeDashboard?.onboarding?.active_count || 0) > 0 ? 'active' : 'pending'}
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
          <h3 className="text-foreground font-semibold mb-3">Pending Actions</h3>
          <div className="space-y-2">
            <ActionItem
              icon={CalendarClock}
              title="Leave requests awaiting approval"
              count={safeDashboard?.leave?.pending_approvals || 0}
              href="/hr/leave"
              urgency={(safeDashboard?.leave?.pending_approvals || 0) > 5 ? 'high' : (safeDashboard?.leave?.pending_approvals || 0) > 0 ? 'medium' : 'low'}
            />
            <ActionItem
              icon={Briefcase}
              title="Job openings to review"
              count={safeDashboard?.recruitment?.open_positions || 0}
              href="/hr/recruitment"
              urgency="medium"
            />
            <ActionItem
              icon={UserPlus}
              title="Employees in onboarding"
              count={safeDashboard?.onboarding?.active_count || 0}
              href="/hr/lifecycle"
              urgency={(safeDashboard?.onboarding?.active_count || 0) > 0 ? 'medium' : 'low'}
            />
            <ActionItem
              icon={GraduationCap}
              title="Upcoming training sessions"
              count={safeDashboard?.training?.scheduled_events || 0}
              href="/hr/training"
              urgency="low"
            />
          </div>
        </div>

        {/* Payroll Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-foreground font-semibold mb-1">Payroll (Last 30 Days)</h3>
          <p className="text-slate-muted text-sm mb-4">{payroll30d.slip_count || 0} salary slips processed</p>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
              <span className="text-slate-muted text-sm">Gross Pay</span>
              <span className="text-foreground font-mono font-medium">
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
          {attendanceStatusData.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3 text-xs text-slate-muted">
              {attendanceStatusData.map((item) => (
                <span key={item.label} className="px-2 py-0.5 rounded-full bg-slate-elevated">
                  {item.label}: {item.value}
                </span>
              ))}
            </div>
          )}
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
                <span className="text-2xl font-bold text-foreground mt-2">{stage.value}</span>
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

      {/* Upcoming Training & Recent Onboarding */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Upcoming Training" subtitle="Next scheduled sessions">
          {(safeDashboard?.training?.upcoming || []).length > 0 ? (
            <div className="space-y-3">
              {(safeDashboard?.training?.upcoming || []).map((event) => (
                <div key={event.id} className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
                  <div>
                    <p className="text-foreground text-sm font-medium">{event.event_name}</p>
                    <p className="text-slate-muted text-xs">{event.type || 'General'}</p>
                  </div>
                  <span className="text-slate-muted text-xs">
                    {event.start_time ? formatDate(event.start_time) : 'TBD'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No upcoming training</div>
          )}
          <Link
            href="/hr/training"
            className="mt-4 flex items-center justify-center gap-2 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            View Training Calendar <ArrowRight className="w-4 h-4" />
          </Link>
        </ChartCard>

        <ChartCard title="Recent Onboardings" subtitle="Active onboarding records">
          {(safeDashboard?.onboarding?.recent || []).length > 0 ? (
            <div className="space-y-3">
              {(safeDashboard?.onboarding?.recent || []).map((record) => (
                <div key={record.id} className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
                  <div>
                    <p className="text-foreground text-sm font-medium">{record.employee_name || 'Unnamed employee'}</p>
                    <p className="text-slate-muted text-xs">{record.status || 'Pending'}</p>
                  </div>
                  <span className="text-slate-muted text-xs">
                    {record.date_of_joining ? formatDate(record.date_of_joining) : 'TBD'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No active onboardings</div>
          )}
          <Link
            href="/hr/lifecycle"
            className="mt-4 flex items-center justify-center gap-2 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            View Lifecycle <ArrowRight className="w-4 h-4" />
          </Link>
        </ChartCard>
      </div>

      {/* Quick Stats Footer */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-foreground">{safeDashboard?.summary?.total_employees || 0}</p>
          <p className="text-slate-muted text-sm">Total Employees</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-foreground">{safeDashboard?.summary?.active_employees || 0}</p>
          <p className="text-slate-muted text-sm">Active Employees</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-foreground">{safeDashboard?.summary?.on_leave_today || 0}</p>
          <p className="text-slate-muted text-sm">On Leave Today</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-foreground">{safeDashboard?.summary?.present_today || 0}</p>
          <p className="text-slate-muted text-sm">Present Today</p>
        </div>
      </div>
    </div>
    </DashboardShell>
  );
}
