'use client';

import { useState, useMemo, useEffect } from 'react';
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
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrSalaryComponents,
  useHrSalaryStructures,
  useHrSalaryStructureAssignments,
  useHrPayrollEntries,
  useHrSalarySlips,
  useHrPayrollEntryMutations,
  useHrSalarySlipMutations,
  useHrAnalyticsOverview,
} from '@/hooks/useApi';
import type { HrPayrollPayoutRequest } from '@/lib/api';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { CHART_COLORS } from '@/lib/design-tokens';
import { Button, StatusPill, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  Banknote,
  Briefcase,
  ClipboardList,
  CreditCard,
  Wallet2,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  Download,
  CheckCircle2,
  XCircle,
  Clock,
  FileSpreadsheet,
  DollarSign,
  Users,
  ArrowRight,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

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
          <Icon className="w-5 h-5 text-violet-400" />
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
    paid: { tone: 'success', icon: CheckCircle2 },
    submitted: { tone: 'info', icon: CheckCircle2 },
    void: { tone: 'danger', icon: XCircle },
    draft: { tone: 'warning', icon: Clock },
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

export default function HrPayrollPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('hr:read');
  const [assignmentLimit, setAssignmentLimit] = useState(20);
  const [assignmentOffset, setAssignmentOffset] = useState(0);
  const [slipLimit, setSlipLimit] = useState(20);
  const [slipOffset, setSlipOffset] = useState(0);
  const [generateForm, setGenerateForm] = useState({
    entryId: '',
    start_date: '',
    end_date: '',
    department: '',
    branch: '',
    designation: '',
    regenerate: false,
  });
  const [regenerateForm, setRegenerateForm] = useState({ entryId: '', overwrite_drafts: true });
  const [slipActionForm, setSlipActionForm] = useState({
    slipId: '',
    payment_reference: '',
    payment_mode: 'bank_transfer',
    paid_at: '',
    void_reason: '',
    voided_at: '',
  });
  const [exportFilters, setExportFilters] = useState({ company: '', start_date: '', end_date: '', status: '', payroll_entry: '' });
  const [actionError, setActionError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [payoutForm, setPayoutForm] = useState<{ entryId: string; provider: string; currency: string }>({
    entryId: '',
    provider: '',
    currency: 'NGN',
  });
  const [payoutRows, setPayoutRows] = useState<
    Record<
      string,
      { slipId: number; accountNumber: string; bankCode: string; accountName: string }
    >
  >({});
  const [payoutStatus, setPayoutStatus] = useState<{ state: 'idle' | 'submitting' | 'success' | 'error'; message?: string }>({
    state: 'idle',
  });
  const company = SINGLE_COMPANY;
  const canFetch = !authLoading && !missingScope;

  const { data: salaryComponents, isLoading: componentsLoading } = useHrSalaryComponents(
    { company: SINGLE_COMPANY || undefined },
    { isPaused: () => !canFetch }
  );
  const { data: salaryStructures, isLoading: structuresLoading } = useHrSalaryStructures(
    { company: SINGLE_COMPANY || undefined },
    { isPaused: () => !canFetch }
  );
  const { data: assignments, isLoading: assignmentsLoading } = useHrSalaryStructureAssignments(
    {
      company: SINGLE_COMPANY || undefined,
      limit: assignmentLimit,
      offset: assignmentOffset,
    },
    { isPaused: () => !canFetch }
  );
  const { data: payrollEntries, isLoading: payrollEntriesLoading } = useHrPayrollEntries(
    { company: SINGLE_COMPANY || undefined },
    { isPaused: () => !canFetch }
  );
  const { data: salarySlips, isLoading: salarySlipsLoading } = useHrSalarySlips(
    {
      company: SINGLE_COMPANY || undefined,
      limit: slipLimit,
      offset: slipOffset,
      payroll_entry: payoutForm.entryId ? `PAYROLL-${payoutForm.entryId}` : undefined,
    },
    { isPaused: () => !canFetch }
  );
  const { data: analyticsOverview } = useHrAnalyticsOverview(undefined, { isPaused: () => !canFetch });
  const payrollEntryMutations = useHrPayrollEntryMutations();
  const salarySlipMutations = useHrSalarySlipMutations();

  // Prefill payout rows when slips change for selected entry
  useEffect(() => {
    if (!salarySlips?.data) return;
    const next: Record<string, { slipId: number; accountNumber: string; bankCode: string; accountName: string }> = {};
    salarySlips.data.forEach((slip: any) => {
      next[String(slip.id)] = {
        slipId: slip.id,
        accountNumber: slip.bank_account_no || '',
        bankCode: '',
        accountName: slip.employee_name || slip.employee || '',
      };
    });
    setPayoutRows(next);
  }, [salarySlips?.data]);

  const handlePayoutChange = (slipId: number, field: 'accountNumber' | 'bankCode' | 'accountName', value: string) => {
    setPayoutRows(prev => ({
      ...prev,
      [String(slipId)]: {
        ...(prev[String(slipId)] || { slipId, accountNumber: '', bankCode: '', accountName: '' }),
        [field]: value,
      },
    }));
  };

  const submitPayouts = async () => {
    if (!payoutForm.entryId) {
      setPayoutStatus({ state: 'error', message: 'Select a payroll entry first.' });
      return;
    }
    const payouts = Object.values(payoutRows)
      .filter(p => p.accountNumber && p.bankCode)
      .map(p => ({
        salary_slip_id: p.slipId,
        account_number: p.accountNumber,
        bank_code: p.bankCode,
        account_name: p.accountName || undefined,
      }));

    if (!payouts.length) {
      setPayoutStatus({ state: 'error', message: 'Add at least one payout with account and bank code.' });
      return;
    }

    const payload: HrPayrollPayoutRequest = {
      payouts,
      provider: payoutForm.provider || undefined,
      currency: payoutForm.currency || 'NGN',
    };

    try {
      setPayoutStatus({ state: 'submitting' });
      await salarySlipMutations.handoffPayrollEntry(Number(payoutForm.entryId), payload);
      setPayoutStatus({ state: 'success', message: `Sent ${payouts.length} slips to Books for payment.` });
    } catch (e: any) {
      setPayoutStatus({ state: 'error', message: e?.message || 'Failed to initiate payouts' });
    }
  };

  const componentList = extractList(salaryComponents);
  const structureList = extractList(salaryStructures);
  const assignmentList = extractList(assignments);
  const payrollEntryList = extractList(payrollEntries);
  const salarySlipList = extractList(salarySlips);

  const payroll30d = useMemo(() => analyticsOverview?.payroll_30d || {}, [analyticsOverview]);

  // Calculate payroll summary from slips
  const payrollSummary = useMemo(() => {
    const slips = salarySlipList.items || [];
    const totalGross = slips.reduce((sum: number, s: any) => sum + (s.gross_pay || 0), 0);
    const totalDeductions = slips.reduce((sum: number, s: any) => sum + (s.total_deduction || 0), 0);
    const totalNet = slips.reduce((sum: number, s: any) => sum + (s.net_pay || 0), 0);
    const paidCount = slips.filter((s: any) => s.status === 'paid').length;
    const draftCount = slips.filter((s: any) => s.status === 'draft').length;
    return { totalGross, totalDeductions, totalNet, paidCount, draftCount, total: slips.length };
  }, [salarySlipList.items]);

  // Payroll breakdown for pie chart
  const payrollBreakdown = useMemo(() => {
    return [
      { name: 'Net Pay', value: payroll30d.net_total || payrollSummary.totalNet, color: CHART_COLORS.success },
      { name: 'Deductions', value: payroll30d.deduction_total || payrollSummary.totalDeductions, color: CHART_COLORS.warning },
    ].filter(d => d.value > 0);
  }, [payroll30d, payrollSummary]);

  // Component type breakdown
  const componentBreakdown = useMemo(() => {
    const components = componentList.items || [];
    const earnings = components.filter((c: any) => c.type === 'earning').length;
    const deductions = components.filter((c: any) => c.type === 'deduction').length;
    return [
      { name: 'Earnings', value: earnings, color: CHART_COLORS.success },
      { name: 'Deductions', value: deductions, color: CHART_COLORS.warning },
    ];
  }, [componentList.items]);

  // Salary slip status breakdown
  const slipStatusBreakdown = useMemo(() => {
    const slips = salarySlipList.items || [];
    const statusCounts: Record<string, number> = {};
    slips.forEach((s: any) => {
      const status = s.status || 'draft';
      statusCounts[status] = (statusCounts[status] || 0) + 1;
    });
    return Object.entries(statusCounts).map(([status, count], idx) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count,
      color: status === 'paid' ? CHART_COLORS.success : status === 'submitted' ? CHART_COLORS.info : status === 'void' ? CHART_COLORS.danger : CHART_COLORS.warning,
    }));
  }, [salarySlipList.items]);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view payroll."
        backHref="/hr"
        backLabel="Back to HR"
      />
    );
  }

  const handleGenerateSlips = async () => {
    setActionError(null);
    if (!generateForm.entryId || !generateForm.start_date || !generateForm.end_date) {
      setActionError('Payroll entry and period are required.');
      return;
    }
    try {
      await payrollEntryMutations.generateSlips(generateForm.entryId, {
        company,
        department: generateForm.department || null,
        branch: generateForm.branch || null,
        designation: generateForm.designation || null,
        start_date: generateForm.start_date,
        end_date: generateForm.end_date,
        regenerate: generateForm.regenerate,
      });
      setGenerateForm({
        entryId: '',
        start_date: '',
        end_date: '',
        department: '',
        branch: '',
        designation: '',
        regenerate: false,
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to generate slips');
    }
  };

  const handleRegenerateSlips = async () => {
    setActionError(null);
    if (!regenerateForm.entryId) {
      setActionError('Payroll entry ID is required.');
      return;
    }
    try {
      await payrollEntryMutations.regenerateSlips(regenerateForm.entryId, { overwrite_drafts: regenerateForm.overwrite_drafts });
      setRegenerateForm({ entryId: '', overwrite_drafts: true });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to regenerate slips');
    }
  };

  const handleMarkSlipPaid = async () => {
    setActionError(null);
    if (!slipActionForm.slipId) {
      setActionError('Salary slip ID is required.');
      return;
    }
    try {
      await salarySlipMutations.markPaid(slipActionForm.slipId, {
        payment_reference: slipActionForm.payment_reference || undefined,
        payment_mode: slipActionForm.payment_mode || undefined,
        paid_at: slipActionForm.paid_at || new Date().toISOString(),
      });
      setSlipActionForm({
        slipId: '',
        payment_reference: '',
        payment_mode: 'bank_transfer',
        paid_at: '',
        void_reason: '',
        voided_at: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to mark paid');
    }
  };

  const handleVoidSlip = async () => {
    setActionError(null);
    if (!slipActionForm.slipId || !slipActionForm.void_reason) {
      setActionError('Salary slip ID and reason are required.');
      return;
    }
    try {
      await salarySlipMutations.void(slipActionForm.slipId, {
        void_reason: slipActionForm.void_reason,
        voided_at: slipActionForm.voided_at || new Date().toISOString(),
      });
      setSlipActionForm({
        slipId: '',
        payment_reference: '',
        payment_mode: 'bank_transfer',
        paid_at: '',
        void_reason: '',
        voided_at: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to void slip');
    }
  };

  const handleExportRegister = async () => {
    setActionError(null);
    try {
      setExporting(true);
      const blob = await salarySlipMutations.exportRegister({
        company: exportFilters.company || company || undefined,
        start_date: exportFilters.start_date || undefined,
        end_date: exportFilters.end_date || undefined,
        status: exportFilters.status || undefined,
        payroll_entry: exportFilters.payroll_entry || undefined,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'salary-slip-register.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setActionError(err?.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-violet-500/10 via-emerald-500/5 to-slate-card border border-violet-500/20 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">Payroll Management</h2>
            <p className="text-slate-muted text-sm mt-1">Salary structures, entries, and slips</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={handleExportRegister}
              disabled={exporting}
              className="px-4 py-2 bg-violet-500/20 text-violet-300 rounded-lg text-sm font-medium hover:bg-violet-500/30 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exporting ? 'Exporting...' : 'Export Register'}
            </Button>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Gross Pay (30d)"
            value={formatCurrency(payroll30d.gross_total || 0, 'NGN', { maximumFractionDigits: 0 })}
            icon={DollarSign}
            colorClass="text-violet-400"
            trend={{ value: 0, label: `${payroll30d.slip_count || 0} slips` }}
          />
          <StatCard
            title="Net Pay (30d)"
            value={formatCurrency(payroll30d.net_total || 0, 'NGN', { maximumFractionDigits: 0 })}
            icon={Wallet2}
            colorClass="text-violet-400"
            trend={{ value: 1, label: "After deductions" }}
          />
          <StatCard
            title="Salary Structures"
            value={String(structureList.total)}
            icon={ClipboardList}
            colorClass="text-violet-400"
          />
          <StatCard
            title="Active Assignments"
            value={String(assignmentList.total)}
            icon={Users}
            colorClass="text-violet-400"
          />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pay Breakdown */}
        <ChartCard title="Pay Breakdown" subtitle="Net vs Deductions">
          {payrollBreakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={payrollBreakdown}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={70}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {payrollBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(value: number) => formatCurrency(value, 'NGN', { maximumFractionDigits: 0 })}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">No payroll data</div>
          )}
        </ChartCard>

        {/* Component Types */}
        <ChartCard title="Salary Components" subtitle="Earnings vs Deductions">
          <div className="space-y-4">
            {componentBreakdown.map((item) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-slate-muted text-sm">{item.name}</span>
                </div>
                <span className="text-foreground font-mono font-bold">{item.value}</span>
              </div>
            ))}
            <div className="pt-3 border-t border-slate-border">
              <div className="flex items-center justify-between">
                <span className="text-slate-muted text-sm">Total Components</span>
                <span className="text-foreground font-mono font-bold">{componentList.total}</span>
              </div>
            </div>
          </div>
        </ChartCard>

        {/* Slip Status */}
        <ChartCard title="Salary Slips" subtitle="Status breakdown">
          {slipStatusBreakdown.length > 0 ? (
            <div className="space-y-3">
              {slipStatusBreakdown.map((item) => (
                <div key={item.name} className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-foreground text-sm">{item.name}</span>
                  </div>
                  <span className="text-foreground font-mono font-bold">{item.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[140px] flex items-center justify-center text-slate-muted text-sm">No slips yet</div>
          )}
        </ChartCard>
      </div>

      {/* Quick Actions */}
      <CollapsibleSection title="Payroll Actions" icon={ClipboardList} defaultOpen={false}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
          {/* Generate Slips */}
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-3">
            <p className="text-foreground font-semibold">Generate Salary Slips</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Payroll Entry ID"
                value={generateForm.entryId}
                onChange={(e) => setGenerateForm({ ...generateForm, entryId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <div />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={generateForm.start_date}
                onChange={(e) => setGenerateForm({ ...generateForm, start_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="date"
                value={generateForm.end_date}
                onChange={(e) => setGenerateForm({ ...generateForm, end_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <input
                type="text"
                placeholder="Department"
                value={generateForm.department}
                onChange={(e) => setGenerateForm({ ...generateForm, department: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="text"
                placeholder="Branch"
                value={generateForm.branch}
                onChange={(e) => setGenerateForm({ ...generateForm, branch: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="text"
                placeholder="Designation"
                value={generateForm.designation}
                onChange={(e) => setGenerateForm({ ...generateForm, designation: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-muted">
              <input
                type="checkbox"
                checked={generateForm.regenerate}
                onChange={(e) => setGenerateForm({ ...generateForm, regenerate: e.target.checked })}
                className="rounded"
              />
              Regenerate existing drafts
            </label>
            <Button
              onClick={handleGenerateSlips}
              className="bg-violet-500 text-foreground px-4 py-2 rounded-lg text-sm font-semibold hover:bg-violet-400 transition-colors"
            >
              Generate Slips
            </Button>
          </div>

          {/* Salary Slip Actions */}
          <div className="space-y-3">
            <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-3">
              <p className="text-foreground font-semibold">Mark Slip as Paid</p>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Salary Slip ID"
                  value={slipActionForm.slipId}
                  onChange={(e) => setSlipActionForm({ ...slipActionForm, slipId: e.target.value })}
                  className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                />
                <input
                  type="text"
                  placeholder="Payment Reference"
                  value={slipActionForm.payment_reference}
                  onChange={(e) => setSlipActionForm({ ...slipActionForm, payment_reference: e.target.value })}
                  className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={slipActionForm.payment_mode}
                  onChange={(e) => setSlipActionForm({ ...slipActionForm, payment_mode: e.target.value })}
                  className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                >
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="cash">Cash</option>
                  <option value="cheque">Cheque</option>
                </select>
                <Button
                  onClick={handleMarkSlipPaid}
                  className="bg-emerald-500 text-foreground px-4 py-2 rounded-lg text-sm font-semibold hover:bg-emerald-400 transition-colors"
                >
                  Mark Paid
                </Button>
              </div>
            </div>

            <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-3">
              <p className="text-foreground font-semibold">Void Slip</p>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Salary Slip ID"
                  value={slipActionForm.slipId}
                  onChange={(e) => setSlipActionForm({ ...slipActionForm, slipId: e.target.value })}
                  className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                />
                <input
                  type="text"
                  placeholder="Void Reason"
                  value={slipActionForm.void_reason}
                  onChange={(e) => setSlipActionForm({ ...slipActionForm, void_reason: e.target.value })}
                  className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                />
              </div>
              <Button
                onClick={handleVoidSlip}
                className="bg-rose-500 text-foreground px-4 py-2 rounded-lg text-sm font-semibold hover:bg-rose-400 transition-colors"
              >
                Void Slip
              </Button>
            </div>
          </div>
        </div>
        {actionError && <p className="text-rose-400 text-sm mt-3">{actionError}</p>}
      </CollapsibleSection>

      {/* Salary Components & Structures */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Banknote className="w-5 h-5 text-emerald-400" />
            <h3 className="text-foreground font-semibold">Salary Components</h3>
          </div>
          <DataTable
            columns={[
              { key: 'salary_component', header: 'Component', render: (item: any) => <span className="text-foreground">{item.salary_component}</span> },
              {
                key: 'type',
                header: 'Type',
                render: (item: any) => (
                  <span className={cn(
                    'px-2 py-1 rounded-full text-xs border',
                    item.type === 'earning' ? 'border-emerald-400/40 text-emerald-300 bg-emerald-500/10' : 'border-amber-400/40 text-amber-300 bg-amber-500/10'
                  )}>
                    {item.type}
                  </span>
                ),
              },
              {
                key: 'depends_on_payment_days',
                header: 'Prorated',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border', item.depends_on_payment_days ? 'border-violet-400/40 text-violet-300 bg-violet-500/10' : 'border-slate-border text-slate-muted')}>
                    {item.depends_on_payment_days ? 'Yes' : 'No'}
                  </span>
                ),
              },
            ]}
            data={(componentList.items || []).map((item: any) => ({ ...item, id: item.id || item.salary_component }))}
            keyField="id"
            loading={componentsLoading}
            emptyMessage="No salary components"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <ClipboardList className="w-5 h-5 text-violet-400" />
            <h3 className="text-foreground font-semibold">Salary Structures</h3>
          </div>
          <DataTable
            columns={[
              { key: 'name', header: 'Structure', render: (item: any) => <span className="text-foreground">{item.name}</span> },
              { key: 'currency', header: 'Currency', render: (item: any) => <span className="text-slate-muted text-sm">{item.currency || '—'}</span> },
              {
                key: 'is_active',
                header: 'Active',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_active ? 'border-emerald-400/40 text-emerald-300 bg-emerald-500/10' : 'border-slate-border text-slate-muted')}>
                    {item.is_active ? 'Yes' : 'No'}
                  </span>
                ),
              },
              {
                key: 'earnings',
                header: 'E/D',
                align: 'right' as const,
                render: (item: any) => (
                  <span className="text-slate-muted text-sm">
                    <span className="text-emerald-400">{item.earnings?.length ?? 0}</span>
                    {' / '}
                    <span className="text-amber-400">{item.deductions?.length ?? 0}</span>
                  </span>
                ),
              },
            ]}
            data={(structureList.items || []).map((item: any) => ({ ...item, id: item.id || item.name }))}
            keyField="id"
            loading={structuresLoading}
            emptyMessage="No salary structures"
          />
        </div>
      </div>

      {/* Salary Structure Assignments */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Briefcase className="w-5 h-5 text-cyan-400" />
          <h3 className="text-foreground font-semibold">Salary Structure Assignments</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground">{item.employee_name || item.employee}</span> },
            { key: 'salary_structure', header: 'Structure', render: (item: any) => <span className="text-slate-muted text-sm">{item.salary_structure}</span> },
            {
              key: 'from_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date)} – ${formatDate(item.to_date)}`}</span>,
            },
            { key: 'base', header: 'Base', align: 'right' as const, render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.base ?? 0)}</span> },
            { key: 'variable', header: 'Variable', align: 'right' as const, render: (item: any) => <span className="font-mono text-slate-muted">{formatCurrency(item.variable ?? 0)}</span> },
          ]}
          data={(assignmentList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.salary_structure}` }))}
          keyField="id"
          loading={assignmentsLoading}
          emptyMessage="No salary assignments"
        />
        {assignmentList.total > assignmentLimit && (
          <Pagination
            total={assignmentList.total}
            limit={assignmentLimit}
            offset={assignmentOffset}
            onPageChange={setAssignmentOffset}
            onLimitChange={(val) => {
              setAssignmentLimit(val);
              setAssignmentOffset(0);
            }}
          />
        )}
      </div>

      {/* Payroll Entries */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <FileSpreadsheet className="w-5 h-5 text-amber-400" />
          <h3 className="text-foreground font-semibold">Payroll Entries</h3>
        </div>
        <DataTable
          columns={[
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-foreground">{item.company}</span> },
            { key: 'posting_date', header: 'Posting', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span> },
            { key: 'payroll_frequency', header: 'Frequency', render: (item: any) => <span className="text-slate-muted text-sm">{item.payroll_frequency}</span> },
            {
              key: 'period',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status || 'draft'} />,
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      payrollEntryMutations.generateSlips(item.id, {
                        company: item.company,
                        start_date: item.start_date,
                        end_date: item.end_date,
                        department: null,
                        branch: null,
                        designation: null,
                        regenerate: false,
                      }).catch((err: any) => setActionError(err?.message || 'Generate failed'));
                    }}
                    className="px-2 py-1 rounded border border-violet-500/40 text-violet-300 hover:bg-violet-500/10 transition-colors"
                  >
                    Generate
                  </Button>
                </div>
              ),
            },
          ]}
          data={(payrollEntryList.items || []).map((item: any) => ({ ...item, id: item.id || item.posting_date }))}
          keyField="id"
          loading={payrollEntriesLoading}
          emptyMessage="No payroll entries"
        />
      </div>

      {/* Payroll Payouts */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex flex-col gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Banknote className="w-5 h-5 text-emerald-400" />
            <h3 className="text-foreground font-semibold">Send Payroll to Books for Payment</h3>
          </div>
          <p className="text-slate-muted text-sm">
            Select a payroll entry, review bank details, and hand off salary slips to the Books payment queue. Accounting will pay via Paystack/Flutterwave.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <label className="flex flex-col gap-1 text-sm text-slate-muted">
            Payroll entry
            <select
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
              value={payoutForm.entryId}
              onChange={(e) => setPayoutForm(prev => ({ ...prev, entryId: e.target.value }))}
            >
              <option value="">Select entry</option>
              {(payrollEntries?.data || payrollEntries?.items || []).map((entry: any) => (
                <option key={entry.id} value={entry.id}>
                  #{entry.id} • {formatDate(entry.start_date)} – {formatDate(entry.end_date)} • {entry.company || 'Company'}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-muted">
            Provider
            <select
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
              value={payoutForm.provider}
              onChange={(e) => setPayoutForm(prev => ({ ...prev, provider: e.target.value }))}
            >
              <option value="">Default</option>
              <option value="paystack">Paystack</option>
              <option value="flutterwave">Flutterwave</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-muted">
            Currency
            <input
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
              value={payoutForm.currency}
              onChange={(e) => setPayoutForm(prev => ({ ...prev, currency: e.target.value }))}
            />
          </label>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-border">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-elevated/60 text-slate-muted">
              <tr>
                <th className="text-left px-3 py-2">Employee</th>
                <th className="text-left px-3 py-2">Net Pay</th>
                <th className="text-left px-3 py-2">Account Number</th>
                <th className="text-left px-3 py-2">Bank Code</th>
                <th className="text-left px-3 py-2">Account Name</th>
              </tr>
            </thead>
            <tbody>
              {(salarySlipList.items || []).map((slip: any) => {
                const row = payoutRows[String(slip.id)] || { accountNumber: '', bankCode: '', accountName: '' };
                return (
                  <tr key={slip.id} className="border-t border-slate-border/60">
                    <td className="px-3 py-2 text-foreground">
                      <div className="font-medium">{slip.employee_name || slip.employee}</div>
                      <div className="text-xs text-slate-muted">{formatDate(slip.start_date)} – {formatDate(slip.end_date)}</div>
                    </td>
                    <td className="px-3 py-2 text-emerald-400 font-mono">{formatCurrency(slip.net_pay ?? 0, slip.currency || 'NGN')}</td>
                    <td className="px-3 py-2">
                      <input
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
                        value={row.accountNumber}
                        onChange={(e) => handlePayoutChange(slip.id, 'accountNumber', e.target.value)}
                        placeholder="0123456789"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
                        value={row.bankCode}
                        onChange={(e) => handlePayoutChange(slip.id, 'bankCode', e.target.value)}
                        placeholder="058"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
                        value={row.accountName}
                        onChange={(e) => handlePayoutChange(slip.id, 'accountName', e.target.value)}
                        placeholder="Account name"
                      />
                    </td>
                  </tr>
                );
              })}
              {!salarySlipList.items?.length && (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-slate-muted">
                    Select a payroll entry to load slips.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between mt-4">
          <div className="text-sm">
            {payoutStatus.state === 'error' && <span className="text-rose-400">{payoutStatus.message}</span>}
            {payoutStatus.state === 'success' && <span className="text-emerald-400">{payoutStatus.message}</span>}
            {payoutStatus.state === 'submitting' && <span className="text-slate-muted">Submitting payouts…</span>}
          </div>
          <Button
            onClick={submitPayouts}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 text-foreground hover:bg-emerald-400 transition-colors disabled:opacity-50"
            disabled={payoutStatus.state === 'submitting'}
          >
            <ArrowRight className="w-4 h-4" />
            Send to Books
          </Button>
        </div>
      </div>

      {/* Salary Slips */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Wallet2 className="w-5 h-5 text-emerald-400" />
            <h3 className="text-foreground font-semibold">Salary Slips</h3>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-muted">
              Paid: <span className="text-emerald-400 font-mono">{payrollSummary.paidCount}</span>
            </span>
            <span className="text-slate-muted">
              Draft: <span className="text-amber-400 font-mono">{payrollSummary.draftCount}</span>
            </span>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground">{item.employee_name || item.employee}</span> },
            {
              key: 'period',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span>,
            },
            { key: 'gross_pay', header: 'Gross', align: 'right' as const, render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.gross_pay ?? 0, item.currency || 'NGN')}</span> },
            { key: 'total_deduction', header: 'Deductions', align: 'right' as const, render: (item: any) => <span className="font-mono text-amber-400">-{formatCurrency(item.total_deduction ?? 0, item.currency || 'NGN')}</span> },
            { key: 'net_pay', header: 'Net Pay', align: 'right' as const, render: (item: any) => <span className="font-mono text-emerald-400 font-bold">{formatCurrency(item.net_pay ?? 0, item.currency || 'NGN')}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status || 'draft'} />,
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      salarySlipMutations.markPaid(item.id, {
                        payment_reference: 'UI',
                        payment_mode: 'bank_transfer',
                        paid_at: new Date().toISOString(),
                      }).catch((err: any) => setActionError(err?.message || 'Mark paid failed'));
                    }}
                    className="px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors"
                  >
                    Pay
                  </Button>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      salarySlipMutations.void(item.id, { void_reason: 'Voided from list' }).catch((err: any) => setActionError(err?.message || 'Void failed'));
                    }}
                    className="px-2 py-1 rounded border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 transition-colors"
                  >
                    Void
                  </Button>
                </div>
              ),
            },
          ]}
          data={(salarySlipList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.posting_date}` }))}
          keyField="id"
          loading={salarySlipsLoading}
          emptyMessage="No salary slips"
        />
        {salarySlipList.total > slipLimit && (
          <Pagination
            total={salarySlipList.total}
            limit={slipLimit}
            offset={slipOffset}
            onPageChange={setSlipOffset}
            onLimitChange={(val) => {
              setSlipLimit(val);
              setSlipOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
