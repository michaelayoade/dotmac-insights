'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingPayments, usePurchasingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { Button, FilterCard, FilterInput, FilterSelect, LoadingState } from '@/components/ui';
import {
  AlertTriangle,
  CreditCard,
  Calendar,
  DollarSign,
  Building2,
  CheckCircle2,
  Clock,
  XCircle,
  Search,
  Banknote,
  Receipt,
} from 'lucide-react';
import { formatCurrency, formatDate, formatNumber } from '@/lib/formatters';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function PurchasingPaymentsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:read');
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [supplierId, setSupplierId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = usePurchasingPayments(
    {
      supplier: supplierId || undefined,
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

  const payments = data?.payments || [];
  const total = data?.total || 0;
  const totalPaid = payments.reduce((sum: number, p: any) => sum + (p.amount || 0), 0);
  const suppliers = suppliersData?.suppliers || [];

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:read permission to view payments."
        backHref="/purchasing"
        backLabel="Back to Purchasing"
      />
    );
  }

  const getStatusConfig = (paymentStatus: string) => {
    const statusLower = paymentStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      completed: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Completed',
      },
      processed: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Processed',
      },
      pending: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Pending',
      },
      failed: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: XCircle,
        label: 'Failed',
      },
      cancelled: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: XCircle,
        label: 'Cancelled',
      },
      voided: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: XCircle,
        label: 'Voided',
      },
    };
    return configs[statusLower] || configs.pending;
  };

  const getPaymentMethodIcon = (method: string) => {
    const methodLower = method?.toLowerCase() || '';
    if (methodLower.includes('bank') || methodLower.includes('transfer')) {
      return Banknote;
    }
    if (methodLower.includes('card')) {
      return CreditCard;
    }
    return Receipt;
  };

  const columns = [
    {
      key: 'payment_number',
      header: 'Payment #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <CreditCard className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-foreground font-medium">
            {item.voucher_no || `#${item.id}`}
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
            {item.supplier || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Payment Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">
            {formatDate(item.posting_date)}
          </span>
        </div>
      ),
    },
    {
      key: 'account',
      header: 'Account',
      render: (item: any) => (
        <span className="text-foreground-secondary text-sm">{item.account || '-'}</span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground font-medium">
          {formatCurrency(item.amount)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load payments</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Payments</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Total Paid</p>
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatCurrency(totalPaid)}
          </p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-blue-400" />
            <p className="text-blue-400 text-sm">This Month</p>
          </div>
          <p className="text-xl font-bold text-blue-400">
            {formatCurrency(0)}
          </p>
          <p className="text-xs text-blue-400/70">
            {formatNumber(0)} payments
          </p>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-yellow-400" />
            <p className="text-yellow-400 text-sm">Pending</p>
          </div>
          <p className="text-xl font-bold text-yellow-400">
            {formatCurrency(0)}
          </p>
          <p className="text-xs text-yellow-400/70">
            {formatNumber(0)} pending
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={(search || status || supplierId || startDate || endDate) && (
          <Button
            onClick={() => {
              setSearch('');
              setStatus('');
              setSupplierId('');
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
            placeholder="Search payments..."
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
          <option value="completed">Completed</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
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
        data={payments}
        keyField="id"
        loading={isLoading}
        emptyMessage="No payments found"
        onRowClick={(item) => router.push(`/purchasing/payments/${(item as any).id}`)}
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
