'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrSalaryComponents,
  useHrSalaryStructures,
  useHrSalaryStructureAssignments,
  useHrPayrollEntries,
  useHrSalarySlips,
  useHrPayrollEntryMutations,
  useHrSalarySlipMutations,
} from '@/hooks/useApi';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { Banknote, Briefcase, ClipboardList, CreditCard, Wallet2 } from 'lucide-react';

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
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-slate-muted text-sm">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
      <div className="p-2 rounded-lg bg-slate-elevated">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

export default function HrPayrollPage() {
  const [company, setCompany] = useState('');
  const [assignmentLimit, setAssignmentLimit] = useState(20);
  const [assignmentOffset, setAssignmentOffset] = useState(0);
  const [slipLimit, setSlipLimit] = useState(20);
  const [slipOffset, setSlipOffset] = useState(0);
  const [generateForm, setGenerateForm] = useState({
    entryId: '',
    company: '',
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

  const { data: salaryComponents, isLoading: componentsLoading } = useHrSalaryComponents({ company: company || undefined });
  const { data: salaryStructures, isLoading: structuresLoading } = useHrSalaryStructures({ company: company || undefined });
  const { data: assignments, isLoading: assignmentsLoading } = useHrSalaryStructureAssignments({
    company: company || undefined,
    limit: assignmentLimit,
    offset: assignmentOffset,
  });
  const { data: payrollEntries, isLoading: payrollEntriesLoading } = useHrPayrollEntries({ company: company || undefined });
  const { data: salarySlips, isLoading: salarySlipsLoading } = useHrSalarySlips({
    company: company || undefined,
    limit: slipLimit,
    offset: slipOffset,
  });
  const payrollEntryMutations = useHrPayrollEntryMutations();
  const salarySlipMutations = useHrSalarySlipMutations();

  const componentList = extractList(salaryComponents);
  const structureList = extractList(salaryStructures);
  const assignmentList = extractList(assignments);
  const payrollEntryList = extractList(payrollEntries);
  const salarySlipList = extractList(salarySlips);

  const handleGenerateSlips = async () => {
    setActionError(null);
    if (!generateForm.entryId || !generateForm.start_date || !generateForm.end_date || !(generateForm.company || company)) {
      setActionError('Payroll entry, company, and period are required.');
      return;
    }
    try {
      await payrollEntryMutations.generateSlips(generateForm.entryId, {
        company: generateForm.company || company,
        department: generateForm.department || null,
        branch: generateForm.branch || null,
        designation: generateForm.designation || null,
        start_date: generateForm.start_date,
        end_date: generateForm.end_date,
        regenerate: generateForm.regenerate,
      });
      setGenerateForm({
        entryId: '',
        company: '',
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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Salary Components" value={componentList.total} icon={Banknote} tone="text-green-300" />
        <StatCard label="Structures" value={structureList.total} icon={ClipboardList} tone="text-teal-electric" />
        <StatCard label="Assignments" value={assignmentList.total} icon={Briefcase} tone="text-purple-300" />
        <StatCard label="Salary Slips" value={salarySlipList.total} icon={CreditCard} tone="text-amber-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setAssignmentOffset(0);
            setSlipOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="space-y-3">
          <p className="text-white font-semibold">Payroll Entry Actions</p>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Generate Salary Slips</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Payroll Entry ID"
                value={generateForm.entryId}
                onChange={(e) => setGenerateForm({ ...generateForm, entryId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Company"
                value={generateForm.company}
                onChange={(e) => setGenerateForm({ ...generateForm, company: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={generateForm.start_date}
                onChange={(e) => setGenerateForm({ ...generateForm, start_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="date"
                value={generateForm.end_date}
                onChange={(e) => setGenerateForm({ ...generateForm, end_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <input
                type="text"
                placeholder="Department"
                value={generateForm.department}
                onChange={(e) => setGenerateForm({ ...generateForm, department: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Branch"
                value={generateForm.branch}
                onChange={(e) => setGenerateForm({ ...generateForm, branch: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Designation"
                value={generateForm.designation}
                onChange={(e) => setGenerateForm({ ...generateForm, designation: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-muted">
              <input
                type="checkbox"
                checked={generateForm.regenerate}
                onChange={(e) => setGenerateForm({ ...generateForm, regenerate: e.target.checked })}
              />
              Regenerate existing drafts
            </label>
            <button
              onClick={handleGenerateSlips}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Generate Slips
            </button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Regenerate Slips</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Payroll Entry ID"
                value={regenerateForm.entryId}
                onChange={(e) => setRegenerateForm({ ...regenerateForm, entryId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <label className="flex items-center gap-2 text-sm text-slate-muted">
                <input
                  type="checkbox"
                  checked={regenerateForm.overwrite_drafts}
                  onChange={(e) => setRegenerateForm({ ...regenerateForm, overwrite_drafts: e.target.checked })}
                />
                Overwrite drafts
              </label>
            </div>
            <button
              onClick={handleRegenerateSlips}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Regenerate
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-white font-semibold">Salary Slip Actions</p>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Mark Paid</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Salary Slip ID"
                value={slipActionForm.slipId}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, slipId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Payment Ref"
                value={slipActionForm.payment_reference}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, payment_reference: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={slipActionForm.payment_mode}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, payment_mode: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cash">Cash</option>
                <option value="cheque">Cheque</option>
              </select>
              <input
                type="datetime-local"
                value={slipActionForm.paid_at}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, paid_at: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <button
              onClick={handleMarkSlipPaid}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Mark Paid
            </button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Void Slip</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Salary Slip ID"
                value={slipActionForm.slipId}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, slipId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Void reason"
                value={slipActionForm.void_reason}
                onChange={(e) => setSlipActionForm({ ...slipActionForm, void_reason: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <input
              type="datetime-local"
              value={slipActionForm.voided_at}
              onChange={(e) => setSlipActionForm({ ...slipActionForm, voided_at: e.target.value })}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <button
              onClick={handleVoidSlip}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Void Slip
            </button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Export Register (CSV)</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Company"
                value={exportFilters.company}
                onChange={(e) => setExportFilters({ ...exportFilters, company: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <select
                value={exportFilters.status}
                onChange={(e) => setExportFilters({ ...exportFilters, status: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="">Any status</option>
                <option value="draft">Draft</option>
                <option value="submitted">Submitted</option>
                <option value="paid">Paid</option>
                <option value="void">Void</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={exportFilters.start_date}
                onChange={(e) => setExportFilters({ ...exportFilters, start_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="date"
                value={exportFilters.end_date}
                onChange={(e) => setExportFilters({ ...exportFilters, end_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <input
              type="text"
              placeholder="Payroll Entry"
              value={exportFilters.payroll_entry}
              onChange={(e) => setExportFilters({ ...exportFilters, payroll_entry: e.target.value })}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <button
              onClick={handleExportRegister}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors disabled:opacity-60"
              disabled={exporting}
            >
              {exporting ? 'Exporting...' : 'Download CSV'}
            </button>
          </div>
        </div>
      </div>
      {actionError && <p className="text-red-400 text-sm">{actionError}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataTable
          columns={[
            { key: 'salary_component', header: 'Component', render: (item: any) => <span className="text-white">{item.salary_component}</span> },
            { key: 'type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.type}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'depends_on_payment_days',
              header: 'Prorated',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border', item.depends_on_payment_days ? 'border-blue-400 text-blue-300 bg-blue-500/10' : 'border-slate-border text-slate-muted')}>
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

        <DataTable
          columns={[
            { key: 'name', header: 'Structure', render: (item: any) => <span className="text-white">{item.name}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'currency', header: 'Currency', render: (item: any) => <span className="text-slate-muted text-sm">{item.currency || '—'}</span> },
            {
              key: 'is_active',
              header: 'Active',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_active ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-slate-border text-slate-muted')}>
                  {item.is_active ? 'Yes' : 'No'}
                </span>
              ),
            },
            {
              key: 'earnings',
              header: 'Earnings',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.earnings?.length ?? 0}</span>,
            },
            {
              key: 'deductions',
              header: 'Deductions',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.deductions?.length ?? 0}</span>,
            },
          ]}
          data={(structureList.items || []).map((item: any) => ({ ...item, id: item.id || item.name }))}
          keyField="id"
          loading={structuresLoading}
          emptyMessage="No salary structures"
        />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Salary Structure Assignments</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'salary_structure', header: 'Structure', render: (item: any) => <span className="text-slate-muted text-sm">{item.salary_structure}</span> },
            {
              key: 'from_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date)} – ${formatDate(item.to_date)}`}</span>,
            },
            { key: 'base', header: 'Base', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.base ?? 0)}</span> },
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

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Payroll Entries</h3>
        </div>
        <DataTable
          columns={[
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-white">{item.company}</span> },
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
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'draft' ? 'border-amber-400 text-amber-300 bg-amber-500/10' : 'border-green-400 text-green-300 bg-green-500/10')}>
                  {item.status || 'draft'}
                </span>
              ),
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <button
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
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Generate
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      payrollEntryMutations.regenerateSlips(item.id, { overwrite_drafts: true }).catch((err: any) => setActionError(err?.message || 'Regenerate failed'));
                    }}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                  >
                    Regenerate
                  </button>
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

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Wallet2 className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Salary Slips</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            {
              key: 'period',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span>,
            },
            { key: 'posting_date', header: 'Posting', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span> },
            { key: 'net_pay', header: 'Net Pay', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.net_pay ?? 0, item.currency || 'USD')}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'submitted' || item.status === 'paid' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'draft'}
                </span>
              ),
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      salarySlipMutations.markPaid(item.id, {
                        payment_reference: 'UI',
                        payment_mode: 'bank_transfer',
                        paid_at: new Date().toISOString(),
                      }).catch((err: any) => setActionError(err?.message || 'Mark paid failed'));
                    }}
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Mark Paid
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      salarySlipMutations.void(item.id, { void_reason: 'Voided from list' }).catch((err: any) => setActionError(err?.message || 'Void failed'));
                    }}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                  >
                    Void
                  </button>
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
