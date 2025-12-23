'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { FilterCard } from '@/components/FilterCard';
import { StatCard } from '@/components/StatCard';
import { useHrSalarySlips, useHrSalarySlipMutations, useHrDepartments } from '@/hooks/useApi';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill, LoadingState, BackButton } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  FileText,
  CheckCircle2,
  XCircle,
  Clock,
  DollarSign,
  Users,
  Send,
  Download,
  Wallet2,
  AlertTriangle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { HrSalarySlip } from '@/lib/api';

function extractList<T>(response: any): { items: T[]; total: number } {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
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

export default function PayslipsPage() {
  const { isLoading: authLoading, missingScope, hasScope } = useRequireScope('hr:read');
  const canWrite = hasScope('hr:write');

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  // Selected slips for bulk actions
  const [selectedSlips, setSelectedSlips] = useState<Set<number | string>>(new Set());

  // Data fetching
  const { data: slipsData, isLoading: slipsLoading, mutate: mutateSlips } = useHrSalarySlips({
    status: statusFilter || undefined,
    department: departmentFilter || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit,
    offset,
  });
  const { data: deptData } = useHrDepartments();
  const { markPaid, exportRegister } = useHrSalarySlipMutations();

  const [bulkLoading, setBulkLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { items: slips, total } = extractList<HrSalarySlip>(slipsData);
  const departments = deptData?.items || [];

  // Filter by search locally
  const filteredSlips = useMemo(() => {
    if (!search.trim()) return slips;
    const q = search.toLowerCase();
    return slips.filter(
      (s) =>
        s.employee_name?.toLowerCase().includes(q) ||
        s.employee?.toLowerCase().includes(q) ||
        String(s.id).includes(q)
    );
  }, [slips, search]);

  // Stats
  const stats = useMemo(() => {
    const draft = slips.filter((s) => s.status?.toLowerCase() === 'draft').length;
    const submitted = slips.filter((s) => s.status?.toLowerCase() === 'submitted').length;
    const paid = slips.filter((s) => s.status?.toLowerCase() === 'paid').length;
    const totalGross = slips.reduce((sum, s) => sum + (s.gross_pay || 0), 0);
    const totalNet = slips.reduce((sum, s) => sum + (s.net_pay || 0), 0);
    return { total: slips.length, draft, submitted, paid, totalGross, totalNet };
  }, [slips]);

  // Bulk actions
  const handleBulkMarkPaid = async () => {
    if (selectedSlips.size === 0) return;
    setBulkLoading(true);
    setError(null);
    try {
      for (const id of selectedSlips) {
        await markPaid(id, {});
      }
      setSelectedSlips(new Set());
      mutateSlips();
    } catch (err: any) {
      setError(err?.message || 'Failed to mark slips as paid');
    } finally {
      setBulkLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportRegister({
        status: statusFilter || undefined,
        department: departmentFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `salary-slips-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Failed to export');
    }
  };

  const toggleSelect = (id: number | string) => {
    const newSelected = new Set(selectedSlips);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedSlips(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedSlips.size === filteredSlips.length) {
      setSelectedSlips(new Set());
    } else {
      setSelectedSlips(new Set(filteredSlips.map((s) => s.id!)));
    }
  };

  // Permission guard
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view salary slips."
        backHref="/hr/payroll"
        backLabel="Back to Payroll"
      />
    );
  }

  const columns = [
    {
      header: (
        <input
          type="checkbox"
          checked={selectedSlips.size === filteredSlips.length && filteredSlips.length > 0}
          onChange={toggleSelectAll}
          className="rounded border-slate-border"
        />
      ),
      accessor: (row: HrSalarySlip) => (
        <input
          type="checkbox"
          checked={selectedSlips.has(row.id!)}
          onChange={() => toggleSelect(row.id!)}
          className="rounded border-slate-border"
        />
      ),
      className: 'w-10',
    },
    {
      header: 'Slip ID',
      accessor: (row: HrSalarySlip) => (
        <Link
          href={`/hr/payroll/payslips/${row.id}`}
          className="text-teal-electric hover:underline font-medium"
        >
          #{row.id}
        </Link>
      ),
    },
    {
      header: 'Employee',
      accessor: (row: HrSalarySlip) => (
        <div>
          <div className="font-medium text-foreground">{row.employee_name || row.employee}</div>
          {row.department && <div className="text-xs text-slate-muted">{row.department}</div>}
        </div>
      ),
    },
    {
      header: 'Pay Period',
      accessor: (row: HrSalarySlip) =>
        `${formatDate(row.start_date)} - ${formatDate(row.end_date)}`,
    },
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
    {
      header: 'Status',
      accessor: (row: HrSalarySlip) => <StatusBadge status={row.status || 'draft'} />,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/hr/payroll" label="Payroll" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Payroll</p>
            <h1 className="text-xl font-semibold text-foreground">Salary Slips</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleExport} className="flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard
          title="Total Slips"
          value={stats.total}
          icon={FileText}
          iconColor="text-violet-400"
        />
        <StatCard
          title="Draft"
          value={stats.draft}
          icon={Clock}
          iconColor="text-yellow-400"
        />
        <StatCard
          title="Submitted"
          value={stats.submitted}
          icon={Send}
          iconColor="text-blue-400"
        />
        <StatCard
          title="Paid"
          value={stats.paid}
          icon={CheckCircle2}
          iconColor="text-green-400"
        />
        <StatCard
          title="Total Gross"
          value={formatCurrency(stats.totalGross, 'NGN')}
          icon={DollarSign}
          iconColor="text-teal-electric"
        />
        <StatCard
          title="Total Net"
          value={formatCurrency(stats.totalNet, 'NGN')}
          icon={Wallet2}
          iconColor="text-green-400"
        />
      </div>

      {/* Filters */}
      <FilterCard>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search employee..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setOffset(0);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Status</option>
            <option value="Draft">Draft</option>
            <option value="Submitted">Submitted</option>
            <option value="Paid">Paid</option>
            <option value="Cancelled">Cancelled</option>
          </select>
          <select
            value={departmentFilter}
            onChange={(e) => {
              setDepartmentFilter(e.target.value);
              setOffset(0);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.name || d.department_name}>
                {d.name || d.department_name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value);
              setOffset(0);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <span className="text-slate-muted">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              setOffset(0);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          {(statusFilter || departmentFilter || startDate || endDate) && (
            <Button
              variant="ghost"
              onClick={() => {
                setStatusFilter('');
                setDepartmentFilter('');
                setStartDate('');
                setEndDate('');
                setOffset(0);
              }}
              className="text-slate-muted hover:text-foreground"
            >
              Clear
            </Button>
          )}
        </div>
      </FilterCard>

      {/* Bulk Actions */}
      {selectedSlips.size > 0 && canWrite && (
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 flex items-center justify-between">
          <span className="text-sm text-slate-muted">
            {selectedSlips.size} slip{selectedSlips.size > 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={handleBulkMarkPaid}
              disabled={bulkLoading}
              loading={bulkLoading}
              className="flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              Mark as Paid
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      {slipsLoading ? (
        <LoadingState message="Loading salary slips..." />
      ) : filteredSlips.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
          <FileText className="w-12 h-12 text-slate-muted mx-auto mb-3" />
          <h3 className="text-foreground font-semibold mb-1">No Salary Slips</h3>
          <p className="text-slate-muted text-sm">
            {statusFilter || departmentFilter || startDate || endDate
              ? 'No slips match your filters.'
              : 'Run payroll to generate salary slips.'}
          </p>
        </div>
      ) : (
        <>
          <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
            <DataTable columns={columns} data={filteredSlips} />
          </div>
          <Pagination
            total={total}
            limit={limit}
            offset={offset}
            onOffsetChange={setOffset}
            onLimitChange={(newLimit) => {
              setLimit(newLimit);
              setOffset(0);
            }}
          />
        </>
      )}
    </div>
  );
}
