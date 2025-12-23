'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrPayrollEntries,
  useHrPayrollEntryMutations,
  useHrEmployees,
  useHrDepartments,
  useHrSalarySlips,
} from '@/hooks/useApi';
import { hrApi } from '@/lib/api/domains/hr';
import { useSWRConfig } from 'swr';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill, LoadingState, BackButton, Modal } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  Play,
  Calendar,
  Users,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  DollarSign,
  Wallet2,
  Building2,
  Briefcase,
  RefreshCcw,
  Send,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { HrPayrollEntry, HrEmployee, HrSalarySlip } from '@/lib/api';

function extractList<T>(response: any): { items: T[]; total: number } {
  const items = response?.data || response?.items || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

type Step = 1 | 2 | 3 | 4;

const STEPS = [
  { step: 1 as Step, label: 'Setup', icon: Calendar },
  { step: 2 as Step, label: 'Select Employees', icon: Users },
  { step: 3 as Step, label: 'Generate Slips', icon: FileSpreadsheet },
  { step: 4 as Step, label: 'Review & Submit', icon: CheckCircle2 },
];

const FREQUENCIES = [
  { value: 'Monthly', label: 'Monthly' },
  { value: 'Bi-weekly', label: 'Bi-weekly' },
  { value: 'Weekly', label: 'Weekly' },
];

function StepIndicator({ currentStep }: { currentStep: Step }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {STEPS.map(({ step, label, icon: Icon }, idx) => (
        <div key={step} className="flex items-center">
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
              currentStep === step
                ? 'bg-teal-electric text-white'
                : currentStep > step
                ? 'bg-green-500/20 text-green-400'
                : 'bg-slate-elevated text-slate-muted'
            )}
          >
            <Icon className="w-4 h-4" />
            <span className="text-sm font-medium hidden sm:inline">{label}</span>
          </div>
          {idx < STEPS.length - 1 && (
            <ArrowRight className="w-4 h-4 text-slate-muted mx-2" />
          )}
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { tone: StatusTone; icon: LucideIcon }> = {
    paid: { tone: 'success', icon: CheckCircle2 },
    submitted: { tone: 'info', icon: CheckCircle2 },
    void: { tone: 'danger', icon: XCircle },
    cancelled: { tone: 'danger', icon: XCircle },
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

export default function PayrollRunPage() {
  const router = useRouter();
  const { mutate: globalMutate } = useSWRConfig();
  const { isLoading: authLoading, missingScope, hasScope } = useRequireScope('hr:write');

  // Step state
  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Step 1: Setup
  const [payrollEntry, setPayrollEntry] = useState<HrPayrollEntry | null>(null);
  const [entryForm, setEntryForm] = useState({
    company: 'dotMac Technologies',
    payroll_frequency: 'Monthly',
    start_date: '',
    end_date: '',
    posting_date: new Date().toISOString().slice(0, 10),
  });

  // Step 2: Employee selection
  const [selectedEmployees, setSelectedEmployees] = useState<Set<number>>(new Set());
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [employeeSearch, setEmployeeSearch] = useState('');

  // Step 3: Generate
  const [generating, setGenerating] = useState(false);
  const [generatedCount, setGeneratedCount] = useState(0);

  // Data fetching
  const { data: entriesData, mutate: mutateEntries } = useHrPayrollEntries();
  const { data: employeesData, isLoading: employeesLoading } = useHrEmployees({ status: 'Active' });
  const { data: deptData } = useHrDepartments();
  const { data: slipsData, isLoading: slipsLoading, mutate: mutateSlips } = useHrSalarySlips(
    payrollEntry ? { payroll_entry: String(payrollEntry.id) } : undefined
  );

  const { items: employees } = extractList<HrEmployee>(employeesData);
  const { items: slips } = extractList<HrSalarySlip>(slipsData);
  const departments = deptData?.items || [];

  const { generateSlips, submitEntry } = useHrPayrollEntryMutations();

  // Loading states
  const [actionLoading, setActionLoading] = useState(false);

  // Filtered employees
  const filteredEmployees = useMemo(() => {
    let result = employees;
    if (departmentFilter) {
      result = result.filter((e) => e.department === departmentFilter);
    }
    if (employeeSearch.trim()) {
      const q = employeeSearch.toLowerCase();
      result = result.filter(
        (e) =>
          e.name?.toLowerCase().includes(q) ||
          e.employee_number?.toLowerCase().includes(q) ||
          e.email?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [employees, departmentFilter, employeeSearch]);

  // Summary stats
  const slipStats = useMemo(() => {
    const totalGross = slips.reduce((sum, s) => sum + (s.gross_pay || 0), 0);
    const totalDeductions = slips.reduce((sum, s) => sum + (s.total_deduction || 0), 0);
    const totalNet = slips.reduce((sum, s) => sum + (s.net_pay || 0), 0);
    const draftCount = slips.filter((s) => s.status?.toLowerCase() === 'draft').length;
    return { totalGross, totalDeductions, totalNet, draftCount, count: slips.length };
  }, [slips]);

  // Step handlers
  const handleCreateEntry = async () => {
    if (!entryForm.start_date || !entryForm.end_date) {
      setError('Please select start and end dates');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const created = await hrApi.createPayrollEntry({
        company: entryForm.company,
        payroll_frequency: entryForm.payroll_frequency,
        start_date: entryForm.start_date,
        end_date: entryForm.end_date,
        posting_date: entryForm.posting_date,
      });
      setPayrollEntry(created);
      mutateEntries();
      setStep(2);
    } catch (err: any) {
      setError(err?.message || 'Failed to create payroll entry');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSelectAllEmployees = () => {
    if (selectedEmployees.size === filteredEmployees.length) {
      setSelectedEmployees(new Set());
    } else {
      setSelectedEmployees(new Set(filteredEmployees.map((e) => e.id)));
    }
  };

  const handleToggleEmployee = (id: number) => {
    const newSelected = new Set(selectedEmployees);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedEmployees(newSelected);
  };

  const handleGenerateSlips = async () => {
    if (!payrollEntry) return;
    if (selectedEmployees.size === 0) {
      setError('Please select at least one employee');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      await generateSlips(payrollEntry.id!, {
        company: entryForm.company,
        start_date: entryForm.start_date,
        end_date: entryForm.end_date,
        department: departmentFilter || null,
      });
      setGeneratedCount(selectedEmployees.size);
      await mutateSlips();
      setStep(4);
    } catch (err: any) {
      setError(err?.message || 'Failed to generate salary slips');
    } finally {
      setGenerating(false);
    }
  };

  const handleSubmitPayroll = async () => {
    if (!payrollEntry) return;
    setActionLoading(true);
    setError(null);
    try {
      await submitEntry(payrollEntry.id!);
      setSuccess('Payroll submitted successfully!');
      mutateEntries();
      mutateSlips();
      setTimeout(() => {
        router.push('/hr/payroll/payslips');
      }, 1500);
    } catch (err: any) {
      setError(err?.message || 'Failed to submit payroll');
    } finally {
      setActionLoading(false);
    }
  };

  // Permission guard
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:write permission to run payroll."
        backHref="/hr/payroll"
        backLabel="Back to Payroll"
      />
    );
  }

  const employeeColumns = [
    {
      header: (
        <input
          type="checkbox"
          checked={selectedEmployees.size === filteredEmployees.length && filteredEmployees.length > 0}
          onChange={handleSelectAllEmployees}
          className="rounded border-slate-border"
        />
      ),
      accessor: (row: HrEmployee) => (
        <input
          type="checkbox"
          checked={selectedEmployees.has(row.id)}
          onChange={() => handleToggleEmployee(row.id)}
          className="rounded border-slate-border"
        />
      ),
      className: 'w-10',
    },
    { header: 'Employee', accessor: (row: HrEmployee) => row.name },
    { header: 'ID', accessor: (row: HrEmployee) => row.employee_number || '-' },
    { header: 'Department', accessor: (row: HrEmployee) => row.department || '-' },
    { header: 'Designation', accessor: (row: HrEmployee) => row.designation || '-' },
  ];

  const slipColumns = [
    { header: 'Employee', accessor: (row: HrSalarySlip) => row.employee_name || row.employee },
    { header: 'Department', accessor: (row: HrSalarySlip) => row.department || '-' },
    {
      header: 'Gross Pay',
      accessor: (row: HrSalarySlip) => formatCurrency(row.gross_pay || 0, row.currency || 'NGN'),
      className: 'text-right',
    },
    {
      header: 'Deductions',
      accessor: (row: HrSalarySlip) => formatCurrency(row.total_deduction || 0, row.currency || 'NGN'),
      className: 'text-right',
    },
    {
      header: 'Net Pay',
      accessor: (row: HrSalarySlip) => (
        <span className="font-semibold text-green-400">
          {formatCurrency(row.net_pay || 0, row.currency || 'NGN')}
        </span>
      ),
      className: 'text-right',
    },
    { header: 'Status', accessor: (row: HrSalarySlip) => <StatusBadge status={row.status || 'draft'} /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/hr/payroll" label="Payroll" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Payroll</p>
            <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
              <Play className="w-5 h-5 text-teal-electric" />
              Run Payroll
            </h1>
          </div>
        </div>
      </div>

      {/* Step Indicator */}
      <StepIndicator currentStep={step} />

      {/* Alerts */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{success}</span>
        </div>
      )}

      {/* Step 1: Setup */}
      {step === 1 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 max-w-2xl mx-auto">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-teal-electric" />
            Payroll Setup
          </h2>
          <div className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Company</label>
              <input
                type="text"
                value={entryForm.company}
                onChange={(e) => setEntryForm({ ...entryForm, company: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Payroll Frequency</label>
              <select
                value={entryForm.payroll_frequency}
                onChange={(e) => setEntryForm({ ...entryForm, payroll_frequency: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                {FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Start Date *</label>
                <input
                  type="date"
                  value={entryForm.start_date}
                  onChange={(e) => setEntryForm({ ...entryForm, start_date: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">End Date *</label>
                <input
                  type="date"
                  value={entryForm.end_date}
                  onChange={(e) => setEntryForm({ ...entryForm, end_date: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Posting Date</label>
              <input
                type="date"
                value={entryForm.posting_date}
                onChange={(e) => setEntryForm({ ...entryForm, posting_date: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="flex justify-end pt-4">
              <Button onClick={handleCreateEntry} disabled={actionLoading} loading={actionLoading} className="flex items-center gap-2">
                Continue
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Select Employees */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Users className="w-5 h-5 text-violet-400" />
                Select Employees
              </h2>
              <span className="text-sm text-slate-muted">
                {selectedEmployees.size} of {filteredEmployees.length} selected
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-4 mb-4">
              <input
                type="text"
                placeholder="Search employees..."
                value={employeeSearch}
                onChange={(e) => setEmployeeSearch(e.target.value)}
                className="flex-1 min-w-[200px] bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
              <select
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">All Departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.name || d.department_name}>
                    {d.name || d.department_name}
                  </option>
                ))}
              </select>
            </div>
            {employeesLoading ? (
              <LoadingState message="Loading employees..." />
            ) : filteredEmployees.length === 0 ? (
              <div className="text-center py-8">
                <Users className="w-12 h-12 text-slate-muted mx-auto mb-3" />
                <p className="text-slate-muted">No active employees found.</p>
              </div>
            ) : (
              <div className="bg-slate-elevated rounded-lg overflow-hidden">
                <DataTable columns={employeeColumns} data={filteredEmployees} />
              </div>
            )}
          </div>
          <div className="flex justify-between">
            <Button variant="secondary" onClick={() => setStep(1)} className="flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
            <Button
              onClick={() => setStep(3)}
              disabled={selectedEmployees.size === 0}
              className="flex items-center gap-2"
            >
              Continue ({selectedEmployees.size} employees)
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Generate Slips */}
      {step === 3 && (
        <div className="space-y-4 max-w-2xl mx-auto">
          <div className="bg-slate-card border border-slate-border rounded-xl p-6 text-center">
            <FileSpreadsheet className="w-16 h-16 text-teal-electric mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-foreground mb-2">Generate Salary Slips</h2>
            <p className="text-slate-muted mb-4">
              Generate salary slips for {selectedEmployees.size} selected employee{selectedEmployees.size > 1 ? 's' : ''}.
            </p>
            <div className="bg-slate-elevated rounded-lg p-4 mb-6 text-left">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-muted">Period:</span>
                  <span className="ml-2 text-foreground">{formatDate(entryForm.start_date)} - {formatDate(entryForm.end_date)}</span>
                </div>
                <div>
                  <span className="text-slate-muted">Frequency:</span>
                  <span className="ml-2 text-foreground">{entryForm.payroll_frequency}</span>
                </div>
                <div>
                  <span className="text-slate-muted">Company:</span>
                  <span className="ml-2 text-foreground">{entryForm.company}</span>
                </div>
                <div>
                  <span className="text-slate-muted">Employees:</span>
                  <span className="ml-2 text-foreground">{selectedEmployees.size}</span>
                </div>
              </div>
            </div>
            <Button
              onClick={handleGenerateSlips}
              disabled={generating}
              loading={generating}
              className="flex items-center gap-2 mx-auto"
              size="lg"
            >
              <RefreshCcw className="w-5 h-5" />
              {generating ? 'Generating...' : 'Generate Salary Slips'}
            </Button>
          </div>
          <div className="flex justify-between">
            <Button variant="secondary" onClick={() => setStep(2)} className="flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
          </div>
        </div>
      )}

      {/* Step 4: Review & Submit */}
      {step === 4 && (
        <div className="space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              title="Slips Generated"
              value={slipStats.count}
              icon={FileSpreadsheet}
              iconColor="text-violet-400"
            />
            <StatCard
              title="Total Gross"
              value={formatCurrency(slipStats.totalGross, 'NGN')}
              icon={DollarSign}
              iconColor="text-teal-electric"
            />
            <StatCard
              title="Total Deductions"
              value={formatCurrency(slipStats.totalDeductions, 'NGN')}
              icon={DollarSign}
              iconColor="text-red-400"
            />
            <StatCard
              title="Total Net Pay"
              value={formatCurrency(slipStats.totalNet, 'NGN')}
              icon={Wallet2}
              iconColor="text-green-400"
            />
          </div>

          {/* Slips Table */}
          <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-border">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-teal-electric" />
                Generated Salary Slips
              </h2>
            </div>
            {slipsLoading ? (
              <LoadingState message="Loading slips..." />
            ) : slips.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-slate-muted">No salary slips generated yet.</p>
              </div>
            ) : (
              <DataTable columns={slipColumns} data={slips} />
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-between">
            <Button variant="secondary" onClick={() => setStep(3)} className="flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Regenerate
            </Button>
            <div className="flex items-center gap-3">
              <Link href="/hr/payroll/payslips">
                <Button variant="secondary">View All Payslips</Button>
              </Link>
              <Button
                onClick={handleSubmitPayroll}
                disabled={actionLoading || slips.length === 0}
                loading={actionLoading}
                className="bg-green-600 hover:bg-green-700 flex items-center gap-2"
              >
                <Send className="w-4 h-4" />
                Submit Payroll
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
