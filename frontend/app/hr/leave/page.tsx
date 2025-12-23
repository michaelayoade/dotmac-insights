'use client';

import { useState, useMemo } from 'react';
import {
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
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrLeaveTypes,
  useHrHolidayLists,
  useHrLeavePolicies,
  useHrLeaveAllocations,
  useHrLeaveApplications,
  useHrLeaveAllocationMutations,
  useHrLeaveApplicationMutations,
  useHrAnalyticsLeaveTrend,
} from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { CHART_COLORS } from '@/lib/design-tokens';
import { Button, FilterCard, FilterInput, FilterSelect, StatusPill, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  CalendarClock,
  FileSpreadsheet,
  Layers,
  ShieldCheck,
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Calendar,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

const CHART_PALETTE = CHART_COLORS.palette;
const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

function ChartCard({ title, subtitle, children, className }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl p-5', className)}>
      <div className="mb-4">
        <h3 className="text-foreground font-semibold">{title}</h3>
        {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl">
      <Button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated/50 transition-colors rounded-xl"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-5 h-5 text-amber-400" />
          <span className="text-foreground font-semibold">{title}</span>
        </div>
        {isOpen ? <ChevronUp className="w-5 h-5 text-slate-muted" /> : <ChevronDown className="w-5 h-5 text-slate-muted" />}
      </Button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { tone: StatusTone; icon: LucideIcon }> = {
    approved: { tone: 'success', icon: CheckCircle2 },
    rejected: { tone: 'danger', icon: XCircle },
    open: { tone: 'warning', icon: Clock },
    draft: { tone: 'default', icon: FileSpreadsheet },
  };
  const config = statusConfig[status.toLowerCase()] || statusConfig.draft;
  return (
    <StatusPill
      label={formatStatusLabel(status || 'draft')}
      tone={config.tone}
      icon={config.icon}
      className="border border-current/30"
    />
  );
}

const SINGLE_COMPANY = '';

export default function HrLeavePage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('hr:read');
  const [company, setCompany] = useState<string>(SINGLE_COMPANY);
  const [allocationStatus, setAllocationStatus] = useState('');
  const [applicationStatus, setApplicationStatus] = useState('');
  const [allocLimit, setAllocLimit] = useState(20);
  const [allocOffset, setAllocOffset] = useState(0);
  const [appLimit, setAppLimit] = useState(20);
  const [appOffset, setAppOffset] = useState(0);
  const [leaveSearch, setLeaveSearch] = useState('');
  const canFetch = !authLoading && !missingScope;

  const { data: leaveTypes, isLoading: leaveTypesLoading } = useHrLeaveTypes(
    {
      search: leaveSearch || undefined,
      limit: 100,
    },
    { isPaused: () => !canFetch }
  );
  const { data: holidayLists, isLoading: holidayListsLoading } = useHrHolidayLists(
    {
      company: company || SINGLE_COMPANY || undefined,
    },
    { isPaused: () => !canFetch }
  );
  const { data: leavePolicies, isLoading: leavePoliciesLoading } = useHrLeavePolicies(
    undefined,
    { isPaused: () => !canFetch }
  );
  const { data: leaveAllocations, isLoading: allocLoading } = useHrLeaveAllocations(
    {
      status: allocationStatus || undefined,
      company: company || SINGLE_COMPANY || undefined,
      limit: allocLimit,
      offset: allocOffset,
    },
    { isPaused: () => !canFetch }
  );
  const { data: leaveApplications, isLoading: appLoading } = useHrLeaveApplications(
    {
      status: applicationStatus || undefined,
      company: company || SINGLE_COMPANY || undefined,
      limit: appLimit,
      offset: appOffset,
    },
    { isPaused: () => !canFetch }
  );
  const { data: leaveTrend } = useHrAnalyticsLeaveTrend({ months: 6 }, { isPaused: () => !canFetch });
  const { bulkCreate } = useHrLeaveAllocationMutations();
  const leaveApplicationMutations = useHrLeaveApplicationMutations();

  const leaveTypeList = extractList(leaveTypes);
  const holidayList = extractList(holidayLists);
  const leavePolicyList = extractList(leavePolicies);
  const allocationList = extractList(leaveAllocations);
  const applicationList = extractList(leaveApplications);

  // Leave type distribution
  const leaveTypeData = useMemo(() => {
    const types = leaveTypeList.items || [];
    return types.slice(0, 6).map((type: any, idx: number) => ({
      name: type.leave_type || type.name || 'Unknown',
      value: 1,
      color: CHART_PALETTE[idx % CHART_PALETTE.length],
      isLWP: type.is_lwp,
      carryForward: type.is_carry_forward,
    }));
  }, [leaveTypeList.items]);

  // Leave trend chart data
  const trendData = useMemo(() => {
    return (leaveTrend || []).map((item: any) => ({
      month: item.month,
      applications: item.count,
    }));
  }, [leaveTrend]);

  // Allocation summary
  const allocationSummary = useMemo(() => {
    const allocations = allocationList.items || [];
    const totalAllocated = allocations.reduce((sum: number, a: any) => sum + (a.total_leaves_allocated || a.new_leaves_allocated || 0), 0);
    const totalUnused = allocations.reduce((sum: number, a: any) => sum + (a.unused_leaves || 0), 0);
    const used = totalAllocated - totalUnused;
    return { totalAllocated, totalUnused, used };
  }, [allocationList.items]);

  // Application status breakdown
  const applicationStatusData = useMemo(() => {
    const apps = applicationList.items || [];
    const statusCounts: Record<string, number> = {};
    apps.forEach((app: any) => {
      const status = app.status || 'open';
      statusCounts[status] = (statusCounts[status] || 0) + 1;
    });
    return Object.entries(statusCounts).map(([status, count], idx) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count,
      color: status === 'approved' ? CHART_COLORS.success : status === 'rejected' ? CHART_COLORS.danger : CHART_COLORS.warning,
    }));
  }, [applicationList.items]);

  const [bulkIds, setBulkIds] = useState('');
  const [bulkPolicyId, setBulkPolicyId] = useState('');
  const [bulkFrom, setBulkFrom] = useState('');
  const [bulkTo, setBulkTo] = useState('');
  const [appForm, setAppForm] = useState({
    employee: '',
    employee_id: '',
    employee_name: '',
    leave_type: '',
    leave_type_id: '',
    from_date: '',
    to_date: '',
    company: '',
    description: '',
  });
  const [bulkActionIds, setBulkActionIds] = useState('');
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject'>('approve');
  const [actionError, setActionError] = useState<string | null>(null);

  const handleBulkAllocate = async () => {
    setActionError(null);
    const ids = bulkIds.split(',').map((s) => Number(s.trim())).filter(Boolean);
    if (!ids.length || !bulkPolicyId || !bulkFrom || !bulkTo) {
      setActionError('Provide employee ids, policy, and dates.');
      return;
    }
    try {
      await bulkCreate({
        employee_ids: ids,
        leave_policy_id: Number(bulkPolicyId),
        from_date: bulkFrom,
        to_date: bulkTo,
        company: company || undefined,
      });
      setBulkIds('');
      setBulkPolicyId('');
    } catch (err: any) {
      setActionError(err?.message || 'Bulk allocation failed');
    }
  };

  const handleCreateApplication = async () => {
    setActionError(null);
    if (!appForm.employee || !appForm.leave_type || !appForm.from_date || !appForm.to_date) {
      setActionError('Employee, leave type, and dates are required.');
      return;
    }
    try {
      const payload: any = {
        employee: appForm.employee,
        employee_id: appForm.employee_id ? Number(appForm.employee_id) : undefined,
        employee_name: appForm.employee_name || appForm.employee,
        leave_type: appForm.leave_type,
        leave_type_id: appForm.leave_type_id ? Number(appForm.leave_type_id) : undefined,
        from_date: appForm.from_date,
        to_date: appForm.to_date,
        posting_date: new Date().toISOString().slice(0, 10),
        half_day: false,
        half_day_date: null,
        total_leave_days: undefined,
        description: appForm.description || undefined,
        leave_approver: undefined,
        leave_approver_name: undefined,
        status: 'open',
        docstatus: 0,
        company: appForm.company || company || undefined,
      };
      await leaveApplicationMutations.create(payload);
      setAppForm({
        employee: '',
        employee_id: '',
        employee_name: '',
        leave_type: '',
        leave_type_id: '',
        from_date: '',
        to_date: '',
        company: '',
        description: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to create application');
    }
  };

  const handleBulkAppAction = async () => {
    setActionError(null);
    const ids = bulkActionIds.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) {
      setActionError('Provide application ids.');
      return;
    }
    try {
      if (bulkAction === 'approve') {
        await leaveApplicationMutations.bulkApprove(ids);
      } else {
        await leaveApplicationMutations.bulkReject(ids);
      }
      setBulkActionIds('');
    } catch (err: any) {
      setActionError(err?.message || 'Bulk action failed');
    }
  };

  const pendingCount = applicationList.items?.filter((a: any) => a.status === 'open').length || 0;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view leave management."
        backHref="/hr"
        backLabel="Back to HR"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with key metrics */}
      <div className="bg-gradient-to-br from-amber-500/10 via-violet-500/5 to-slate-card border border-amber-500/20 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">Leave Management</h2>
            <p className="text-slate-muted text-sm mt-1">Types, allocations, and applications</p>
          </div>
          {pendingCount > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/20 border border-amber-500/40 rounded-lg">
              <AlertCircle className="w-4 h-4 text-amber-400" />
              <span className="text-amber-300 text-sm font-medium">{pendingCount} pending approval{pendingCount > 1 ? 's' : ''}</span>
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Leave Types" value={leaveTypeList.total} icon={Layers} colorClass="text-violet-400" />
          <StatCard title="Holiday Lists" value={holidayList.total} icon={Calendar} colorClass="text-amber-400" />
          <StatCard title="Active Allocations" value={allocationList.total} icon={ShieldCheck} colorClass="text-emerald-400" />
          <StatCard title="Applications" value={applicationList.total} icon={Users} colorClass="text-cyan-400" />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Leave Trend */}
        <ChartCard title="Leave Applications" subtitle="6-month trend" className="lg:col-span-2">
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="month" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} />
                <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="applications" fill={CHART_COLORS.warning} radius={[4, 4, 0, 0]} name="Applications" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">No trend data available</div>
          )}
        </ChartCard>

        {/* Allocation Summary */}
        <ChartCard title="Leave Balance" subtitle="Allocated vs Used">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Total Allocated</span>
              <span className="text-foreground font-mono font-bold">{allocationSummary.totalAllocated}</span>
            </div>
            <div className="h-3 bg-slate-elevated rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-amber-500 to-amber-400 rounded-full transition-all"
                style={{ width: `${allocationSummary.totalAllocated > 0 ? (allocationSummary.used / allocationSummary.totalAllocated) * 100 : 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-slate-muted">Used: {allocationSummary.used}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-slate-elevated" />
                <span className="text-slate-muted">Remaining: {allocationSummary.totalUnused}</span>
              </div>
            </div>
          </div>
        </ChartCard>
      </div>

      {/* Filters */}
      <FilterCard contentClassName="flex flex-wrap gap-3 items-center" iconClassName="text-amber-400">
        <FilterInput
          type="text"
          placeholder="Filter by company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setAllocOffset(0);
            setAppOffset(0);
          }}
        />
        <FilterInput
          type="text"
          placeholder="Search leave types"
          value={leaveSearch}
          onChange={(e) => setLeaveSearch(e.target.value)}
        />
        <FilterSelect
          value={allocationStatus}
          onChange={(e) => {
            setAllocationStatus(e.target.value);
            setAllocOffset(0);
          }}
        >
          <option value="">All Allocation Status</option>
          <option value="draft">Draft</option>
          <option value="open">Open</option>
          <option value="approved">Approved</option>
        </FilterSelect>
        <FilterSelect
          value={applicationStatus}
          onChange={(e) => {
            setApplicationStatus(e.target.value);
            setAppOffset(0);
          }}
        >
          <option value="">All Application Status</option>
          <option value="open">Open</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </FilterSelect>
      </FilterCard>

      {/* Quick Actions */}
      <CollapsibleSection title="Quick Actions" icon={ShieldCheck} defaultOpen={false}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-3">
            <p className="text-foreground font-semibold">Bulk Allocate Leave</p>
            <input
              type="text"
              placeholder="Employee IDs (comma-separated)"
              value={bulkIds}
              onChange={(e) => setBulkIds(e.target.value)}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                placeholder="Policy ID"
                value={bulkPolicyId}
                onChange={(e) => setBulkPolicyId(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="text"
                placeholder="Company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={bulkFrom}
                onChange={(e) => setBulkFrom(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="date"
                value={bulkTo}
                onChange={(e) => setBulkTo(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <Button
              onClick={handleBulkAllocate}
              className="bg-amber-500 text-slate-900 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-amber-400 transition-colors"
            >
              Create Allocations
            </Button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-3">
            <p className="text-foreground font-semibold">New Leave Application</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Employee"
                value={appForm.employee}
                onChange={(e) => setAppForm({ ...appForm, employee: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="text"
                placeholder="Leave Type"
                value={appForm.leave_type}
                onChange={(e) => setAppForm({ ...appForm, leave_type: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                placeholder="From"
                value={appForm.from_date}
                onChange={(e) => setAppForm({ ...appForm, from_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="date"
                placeholder="To"
                value={appForm.to_date}
                onChange={(e) => setAppForm({ ...appForm, to_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <textarea
              placeholder="Description (optional)"
              value={appForm.description}
              onChange={(e) => setAppForm({ ...appForm, description: e.target.value })}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground h-16"
            />
            <Button
              onClick={handleCreateApplication}
              className="bg-violet-500 text-foreground px-4 py-2 rounded-lg text-sm font-semibold hover:bg-violet-400 transition-colors"
            >
              Submit Application
            </Button>
          </div>
        </div>
        {actionError && <p className="text-rose-400 text-sm mt-3">{actionError}</p>}
      </CollapsibleSection>

      {/* Leave Types & Holiday Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="w-5 h-5 text-violet-400" />
            <h3 className="text-foreground font-semibold">Leave Types</h3>
          </div>
          <DataTable
            columns={[
              { key: 'leave_type', header: 'Leave Type', sortable: true, render: (item: any) => <span className="text-foreground">{item.leave_type || item.name}</span> },
              {
                key: 'is_lwp',
                header: 'LWP',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_lwp ? 'border-rose-400/40 text-rose-300 bg-rose-500/10' : 'border-emerald-400/40 text-emerald-300 bg-emerald-500/10')}>
                    {item.is_lwp ? 'Yes' : 'No'}
                  </span>
                ),
              },
              {
                key: 'is_carry_forward',
                header: 'Carry Fwd',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_carry_forward ? 'border-violet-400/40 text-violet-300 bg-violet-500/10' : 'border-slate-border text-slate-muted')}>
                    {item.is_carry_forward ? 'Yes' : 'No'}
                  </span>
                ),
              },
            ]}
            data={(leaveTypeList.items || []).map((item: any) => ({ ...item, id: item.id || item.leave_type }))}
            keyField="id"
            loading={leaveTypesLoading}
            emptyMessage="No leave types defined"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-5 h-5 text-amber-400" />
            <h3 className="text-foreground font-semibold">Holiday Lists</h3>
          </div>
          <DataTable
            columns={[
              { key: 'holiday_list_name', header: 'Holiday List', render: (item: any) => <span className="text-foreground">{item.holiday_list_name}</span> },
              { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
              {
                key: 'holidays',
                header: 'Holidays',
                align: 'right' as const,
                render: (item: any) => <span className="font-mono text-foreground">{item.holidays?.length ?? 0}</span>,
              },
            ]}
            data={(holidayList.items || []).map((item: any) => ({ ...item, id: item.id || item.holiday_list_name }))}
            keyField="id"
            loading={holidayListsLoading}
            emptyMessage="No holiday lists"
          />
        </div>
      </div>

      {/* Leave Policies */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
          <h3 className="text-foreground font-semibold">Leave Policies</h3>
        </div>
        <DataTable
          columns={[
            { key: 'leave_policy_name', header: 'Policy', render: (item: any) => <span className="text-foreground">{item.leave_policy_name}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'details',
              header: 'Leave Types',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-foreground">{item.details?.length ?? 0}</span>,
            },
          ]}
          data={(leavePolicyList.items || []).map((item: any) => ({ ...item, id: item.id || item.leave_policy_name }))}
          keyField="id"
          loading={leavePoliciesLoading}
          emptyMessage="No leave policies"
        />
      </div>

      {/* Leave Allocations */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <h3 className="text-foreground font-semibold">Leave Allocations</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground">{item.employee_name || item.employee}</span> },
            { key: 'leave_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm">{item.leave_type}</span> },
            { key: 'from_date', header: 'From', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.from_date)}</span> },
            { key: 'to_date', header: 'To', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.to_date)}</span> },
            {
              key: 'total_leaves_allocated',
              header: 'Allocated',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-foreground">{item.total_leaves_allocated ?? item.new_leaves_allocated ?? 0}</span>,
            },
            {
              key: 'unused_leaves',
              header: 'Unused',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-emerald-400">{item.unused_leaves ?? 0}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status || 'draft'} />,
            },
          ]}
          data={(allocationList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
          keyField="id"
          loading={allocLoading}
          emptyMessage="No leave allocations"
        />
        {allocationList.total > allocLimit && (
          <Pagination
            total={allocationList.total}
            limit={allocLimit}
            offset={allocOffset}
            onPageChange={setAllocOffset}
            onLimitChange={(val) => {
              setAllocLimit(val);
              setAllocOffset(0);
            }}
          />
        )}
      </div>

      {/* Leave Applications */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-amber-400" />
            <h3 className="text-foreground font-semibold">Leave Applications</h3>
          </div>
          {applicationStatusData.length > 0 && (
            <div className="flex items-center gap-3">
              {applicationStatusData.map((s) => (
                <div key={s.name} className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="text-xs text-slate-muted">{s.name}: {s.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground">{item.employee_name || item.employee}</span> },
            { key: 'leave_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm">{item.leave_type}</span> },
            { key: 'from_date', header: 'From', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.from_date)}</span> },
            { key: 'to_date', header: 'To', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.to_date)}</span> },
            {
              key: 'total_leave_days',
              header: 'Days',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-foreground">{item.total_leave_days ?? 0}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status || 'open'} />,
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <Button
                    onClick={(e) => { e.stopPropagation(); leaveApplicationMutations.approve(item.id); }}
                    className="px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors"
                  >
                    Approve
                  </Button>
                  <Button
                    onClick={(e) => { e.stopPropagation(); leaveApplicationMutations.reject(item.id); }}
                    className="px-2 py-1 rounded border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 transition-colors"
                  >
                    Reject
                  </Button>
                </div>
              ),
            },
          ]}
          data={(applicationList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.from_date}` }))}
          keyField="id"
          loading={appLoading}
          emptyMessage="No leave applications"
        />
        {applicationList.total > appLimit && (
          <Pagination
            total={applicationList.total}
            limit={appLimit}
            offset={appOffset}
            onPageChange={setAppOffset}
            onLimitChange={(val) => {
              setAppLimit(val);
              setAppOffset(0);
            }}
          />
        )}

        {/* Bulk Actions */}
        <div className="mt-4 p-4 bg-slate-elevated border border-slate-border rounded-lg">
          <p className="text-foreground font-semibold mb-3">Bulk Approve/Reject</p>
          <div className="flex flex-wrap gap-3 items-end">
            <input
              type="text"
              placeholder="Application IDs (comma-separated)"
              value={bulkActionIds}
              onChange={(e) => setBulkActionIds(e.target.value)}
              className="flex-1 min-w-[200px] bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
            <select
              value={bulkAction}
              onChange={(e) => setBulkAction(e.target.value as 'approve' | 'reject')}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            >
              <option value="approve">Approve</option>
              <option value="reject">Reject</option>
            </select>
            <Button
              onClick={handleBulkAppAction}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-semibold transition-colors',
                bulkAction === 'approve' ? 'bg-emerald-500 text-foreground hover:bg-emerald-400' : 'bg-rose-500 text-foreground hover:bg-rose-400'
              )}
            >
              Run Bulk {bulkAction === 'approve' ? 'Approve' : 'Reject'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
