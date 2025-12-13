'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrSalaryComponents,
  useHrSalaryStructures,
  useHrSalaryStructureAssignments,
  useHrPayrollEntries,
  useHrSalarySlips,
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

  const componentList = extractList(salaryComponents);
  const structureList = extractList(salaryStructures);
  const assignmentList = extractList(assignments);
  const payrollEntryList = extractList(payrollEntries);
  const salarySlipList = extractList(salarySlips);

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
