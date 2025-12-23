'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingExpenses, usePurchasingExpenseTypes } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { formatCurrency, formatNumber, formatDate } from '@/lib/formatters';
import { Button, FilterCard, FilterInput, FilterSelect, LoadingState } from '@/components/ui';
import {
  AlertTriangle,
  Receipt,
  Calendar,
  DollarSign,
  Building2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
  User,
  Briefcase,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function PurchasingExpensesPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:read');
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [expenseType, setExpenseType] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = usePurchasingExpenses(
    {
      status: status || undefined,
      expense_type: expenseType || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      search: search || undefined,
      currency,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    },
    { isPaused: () => !canFetch }
  );

  const { data: typesData } = usePurchasingExpenseTypes(
    {
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    },
    { isPaused: () => !canFetch }
  );

  const expenses = data?.expenses || [];
  const total = data?.total || 0;
  const expenseTypes = typesData?.expense_types || [];
  const totalClaimed = expenses.reduce((sum: number, e: any) => sum + (e.total_claimed_amount || e.amount || 0), 0);
  const totalReimbursed = expenses.reduce((sum: number, e: any) => sum + (e.total_amount_reimbursed || 0), 0);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:read permission to view expenses."
        backHref="/purchasing"
        backLabel="Back to Purchasing"
      />
    );
  }

  const getStatusConfig = (expenseStatus: string) => {
    const statusLower = expenseStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      approved: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Approved',
      },
      pending: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Pending',
      },
      rejected: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: AlertCircle,
        label: 'Rejected',
      },
      draft: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: Receipt,
        label: 'Draft',
      },
      submitted: {
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: Receipt,
        label: 'Submitted',
      },
      paid: {
        color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        icon: CheckCircle2,
        label: 'Paid',
      },
    };
    return configs[statusLower] || configs.draft;
  };

  const columns = [
    {
      key: 'voucher_no',
      header: 'Expense #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-foreground font-medium">
            {item.voucher_no || `#${item.id}`}
          </span>
        </div>
      ),
    },
    {
      key: 'party',
      header: 'Employee / Party',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[180px]">
            {item.party || item.employee_name || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'purpose',
      header: 'Purpose',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[200px]">
            {item.purpose || item.account || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">{formatDate(item.posting_date)}</span>
        </div>
      ),
    },
    {
      key: 'claimed',
      header: 'Claimed',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground font-medium">
          {formatCurrency(item.total_claimed_amount || item.amount)}
        </span>
      ),
    },
    {
      key: 'reimbursed',
      header: 'Reimbursed',
      align: 'right' as const,
      render: (item: any) => {
        const reimbursed = item.total_amount_reimbursed || 0;
        return (
          <span
            className={cn('font-mono', reimbursed > 0 ? 'text-green-400' : 'text-slate-muted')}
          >
            {formatCurrency(reimbursed)}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const expenseStatus = item.status || 'draft';
        const config = getStatusConfig(expenseStatus);
        const StatusIcon = config.icon;
        return (
          <span
            className={cn(
              'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
              config.color
            )}
          >
            <StatusIcon className="w-3 h-3" />
            {config.label}
          </span>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load expenses</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Expenses</h1>
          <p className="text-slate-muted text-sm">Track expense claims, reimbursements, and approvals</p>
        </div>
        <Button
          onClick={() => router.push('/purchasing/expenses/new')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Receipt className="w-4 h-4" />
          New Expense
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Receipt className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Expenses</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-amber-400" />
            <p className="text-amber-400 text-sm">Total Claimed</p>
          </div>
          <p className="text-xl font-bold text-amber-400">
            {formatCurrency(totalClaimed)}
          </p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Reimbursed</p>
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatCurrency(totalReimbursed)}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="w-4 h-4 text-violet-400" />
            <p className="text-slate-muted text-sm">Expense Types</p>
          </div>
          <p className="text-xl font-bold text-foreground">
            {formatNumber(expenseTypes.length)}
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={(search || status || expenseType || startDate || endDate) && (
          <Button
            onClick={() => {
              setSearch('');
              setStatus('');
              setExpenseType('');
              setStartDate('');
              setEndDate('');
              setPage(1);
            }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        contentClassName="flex flex-wrap gap-4 items-center"
      >
        <div className="flex-1 min-w-[200px] max-w-md relative">
          <Search className="w-4 h-4 text-slate-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <FilterInput
            type="text"
            placeholder="Search expenses..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-10 pr-4 placeholder:text-slate-muted focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <FilterSelect
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="paid">Paid</option>
        </FilterSelect>
        {expenseTypes.length > 0 && (
          <FilterSelect
            value={expenseType}
            onChange={(e) => {
              setExpenseType(e.target.value);
              setPage(1);
            }}
            className="focus:ring-2 focus:ring-teal-electric/50 max-w-[200px]"
          >
            <option value="">All Types</option>
            {expenseTypes.map((type: any) => (
              <option key={type.account} value={type.account}>
                {type.account_name || type.account}
              </option>
            ))}
          </FilterSelect>
        )}
        <div className="flex items-center gap-2">
          <FilterInput
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 focus:ring-2 focus:ring-teal-electric/50"
            placeholder="Start date"
          />
          <span className="text-slate-muted">to</span>
          <FilterInput
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 focus:ring-2 focus:ring-teal-electric/50"
            placeholder="End date"
          />
        </div>
      </FilterCard>

      {/* Table */}
      <DataTable
        columns={columns}
        data={expenses}
        keyField="id"
        loading={isLoading}
        emptyMessage="No expenses found"
        onRowClick={(item) => router.push(`/purchasing/expenses/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
