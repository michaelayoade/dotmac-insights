'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingBills, usePurchasingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { Button, FilterCard, FilterInput, FilterSelect, LoadingState } from '@/components/ui';
import {
  AlertTriangle,
  FileText,
  Calendar,
  DollarSign,
  Building2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
} from 'lucide-react';
import { formatCurrency, formatDate, formatNumber } from '@/lib/formatters';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function getDaysOverdue(dueDate: string | null | undefined): number {
  if (!dueDate) return 0;
  const due = new Date(dueDate);
  const today = new Date();
  const diff = Math.floor((today.getTime() - due.getTime()) / (1000 * 60 * 60 * 24));
  return diff > 0 ? diff : 0;
}

export default function PurchasingBillsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:read');
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [supplierId, setSupplierId] = useState<string>('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = usePurchasingBills(
    {
      status: status || undefined,
      supplier: supplierId || undefined,
      overdue_only: overdueOnly || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      search: search || undefined,
      currency,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    },
    { isPaused: () => !canFetch }
  );

  const { data: suppliersData } = usePurchasingSuppliers(
    { limit: 100, offset: 0 },
    { isPaused: () => !canFetch }
  );

  const bills = data?.bills || [];
  const total = data?.total || 0;
  const suppliers = suppliersData?.suppliers || [];
  const totalOutstanding = bills.reduce((sum: number, b: any) => sum + (b.outstanding_amount || 0), 0);
  const totalOverdue = bills
    .filter((b: any) => b.is_overdue)
    .reduce((sum: number, b: any) => sum + (b.outstanding_amount || 0), 0);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:read permission to view bills."
        backHref="/purchasing"
        backLabel="Back to Purchasing"
      />
    );
  }

  const getStatusConfig = (billStatus: string) => {
    const statusLower = billStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      paid: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Paid',
      },
      open: {
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: FileText,
        label: 'Open',
      },
      overdue: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: AlertCircle,
        label: 'Overdue',
      },
      partially_paid: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Partial',
      },
      draft: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: FileText,
        label: 'Draft',
      },
    };
    return configs[statusLower] || configs.draft;
  };

  const columns = [
    {
      key: 'bill_number',
      header: 'Bill #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-foreground font-medium">
            {item.erpnext_id || `#${item.id}`}
          </span>
        </div>
      ),
    },
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[180px]">
            {item.supplier_name || item.supplier || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Bill Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">{formatDate(item.posting_date)}</span>
        </div>
      ),
    },
    {
      key: 'due_date',
      header: 'Due Date',
      render: (item: any) => {
        const daysOverdue = getDaysOverdue(item.due_date);
        const isOverdue = daysOverdue > 0 && item.status !== 'paid';
        return (
          <div className="space-y-1">
            <div className="flex items-center gap-1 text-sm">
              <Clock className="w-3 h-3 text-slate-muted" />
              <span className={cn('text-foreground-secondary', isOverdue && 'text-red-400')}>
                {formatDate(item.due_date)}
              </span>
            </div>
            {isOverdue && (
              <span className="text-xs text-red-400">{daysOverdue} days overdue</span>
            )}
          </div>
        );
      },
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground font-medium">
          {formatCurrency(item.grand_total)}
        </span>
      ),
    },
    {
      key: 'balance',
      header: 'Balance Due',
      align: 'right' as const,
      render: (item: any) => {
        const balance = item.outstanding_amount || 0;
        return (
          <span
            className={cn('font-mono', balance > 0 ? 'text-orange-400' : 'text-green-400')}
          >
            {formatCurrency(balance)}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const billStatus = item.status || 'draft';
        const config = getStatusConfig(billStatus);
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
          <p className="text-red-400">Failed to load bills</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Vendor Bills</h1>
          <p className="text-slate-muted text-sm">Track payables, due dates, and write-back status</p>
        </div>
        <Button
          onClick={() => router.push('/purchasing/bills/new')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <FileText className="w-4 h-4" />
          New Bill
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Bills</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-orange-400" />
            <p className="text-orange-400 text-sm">Total Outstanding</p>
          </div>
          <p className="text-xl font-bold text-orange-400">
            {formatCurrency(totalOutstanding)}
          </p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <p className="text-red-400 text-sm">Overdue</p>
          </div>
          <p className="text-xl font-bold text-red-400">
            {formatCurrency(totalOverdue)}
          </p>
          <p className="text-xs text-red-400/70">
            {formatNumber(bills.filter((b: any) => b.is_overdue).length)} bills
          </p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Paid This Month</p>
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatCurrency(0)}
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={(search || status || supplierId || overdueOnly || startDate || endDate) && (
          <Button
            onClick={() => {
              setSearch('');
              setStatus('');
              setSupplierId('');
              setOverdueOnly(false);
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
            placeholder="Search bills..."
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
          <option value="open">Open</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="partially_paid">Partially Paid</option>
          <option value="draft">Draft</option>
        </FilterSelect>
        {suppliers.length > 0 && (
          <FilterSelect
            value={supplierId}
            onChange={(e) => {
              setSupplierId(e.target.value);
              setPage(1);
            }}
            className="focus:ring-2 focus:ring-teal-electric/50 max-w-[200px]"
          >
            <option value="">All Suppliers</option>
            {suppliers.map((supplier: any) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name || supplier.supplier_name}
              </option>
            ))}
          </FilterSelect>
        )}
        <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => {
              setOverdueOnly(e.target.checked);
              setPage(1);
            }}
            className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
          />
          Overdue only
        </label>
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
        data={bills}
        keyField="id"
        loading={isLoading}
        emptyMessage="No bills found"
        onRowClick={(item) => router.push(`/purchasing/bills/${(item as any).id}`)}
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
