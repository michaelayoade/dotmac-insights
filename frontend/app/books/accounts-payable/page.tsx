'use client';

import { useState } from 'react';
import { useAccountingPayables } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { buildApiUrl } from '@/lib/api';
import { ArrowDownToLine, Calendar, Download } from 'lucide-react';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function getAgingBadge(daysOverdue: number | undefined | null) {
  if (daysOverdue === undefined || daysOverdue === null || daysOverdue <= 0) {
    return (
      <span className="px-2 py-1 rounded-full text-xs font-medium border bg-green-500/20 text-green-400 border-green-500/30">
        Current
      </span>
    );
  }
  if (daysOverdue <= 30) {
    return (
      <span className="px-2 py-1 rounded-full text-xs font-medium border bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
        1-30 days
      </span>
    );
  }
  if (daysOverdue <= 60) {
    return (
      <span className="px-2 py-1 rounded-full text-xs font-medium border bg-orange-500/20 text-orange-400 border-orange-500/30">
        31-60 days
      </span>
    );
  }
  if (daysOverdue <= 90) {
    return (
      <span className="px-2 py-1 rounded-full text-xs font-medium border bg-red-500/20 text-red-400 border-red-500/30">
        61-90 days
      </span>
    );
  }
  return (
    <span className="px-2 py-1 rounded-full text-xs font-medium border bg-red-700/20 text-red-300 border-red-700/30">
      90+ days
    </span>
  );
}

export default function AccountsPayablePage() {
  const [filters, setFilters] = usePersistentState<{
    offset: number;
    limit: number;
    supplierSearch: string;
    currency: string;
  }>('books.ap.filters', {
    offset: 0,
    limit: 20,
    supplierSearch: '',
    currency: 'NGN',
  });
  const { offset, limit, supplierSearch, currency } = filters;

  const { data, isLoading, error, mutate } = useAccountingPayables({
    currency: currency || undefined,
    limit,
    offset,
  });

  const exportAging = () => {
    const url = buildApiUrl('/accounting/payables-aging/export', { currency: currency || undefined });
    window.open(url, '_blank');
  };

  const columns = [
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <ArrowDownToLine className="w-4 h-4 text-orange-400" />
          <span className="text-foreground text-sm">{item.supplier_name || 'Unknown Supplier'}</span>
        </div>
      ),
    },
    {
      key: 'total_payable',
      header: 'Total Payable',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground">{formatCurrency(item.total_payable)}</span>
      ),
    },
    {
      key: 'current',
      header: 'Current',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-green-400">{formatCurrency(item.current)}</span>,
    },
    {
      key: 'overdue_1_30',
      header: '1-30',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-yellow-400">{formatCurrency(item.overdue_1_30)}</span>,
    },
    {
      key: 'overdue_31_60',
      header: '31-60',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-orange-400">{formatCurrency(item.overdue_31_60)}</span>,
    },
    {
      key: 'overdue_61_90',
      header: '61-90',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-orange-400">{formatCurrency(item.overdue_61_90)}</span>,
    },
    {
      key: 'overdue_over_90',
      header: '90+',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-red-400">{formatCurrency(item.overdue_over_90)}</span>,
    },
    {
      key: 'invoice_count',
      header: '# Invoices',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{item.invoice_count}</span>,
    },
    {
      key: 'oldest_invoice_date',
      header: 'Oldest Bill',
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.oldest_invoice_date)}</span>,
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  const summary = (data?.aging as any) || {};
  const totalSuppliers = data?.suppliers?.length || 0;

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load accounts payable."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Aging Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total AP</p>
          <p className="text-2xl font-bold text-foreground">{formatCurrency(data?.total_payable)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Current</p>
          <p className="text-xl font-bold text-green-400">{formatCurrency(summary.current)}</p>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <p className="text-yellow-400 text-sm">1-30 Days</p>
          <p className="text-xl font-bold text-yellow-400">{formatCurrency(summary['1_30'])}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">31-60 Days</p>
          <p className="text-xl font-bold text-orange-400">{formatCurrency(summary['31_60'])}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">60+ Days</p>
          <p className="text-xl font-bold text-red-400">{formatCurrency(summary.over_90)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search by supplier name..."
            value={supplierSearch}
            onChange={(e) => { setFilters((prev) => ({ ...prev, supplierSearch: e.target.value, offset: 0 })); }}
            className="input-field"
          />
        </div>
        <select
          value={currency}
          onChange={(e) => { setFilters((prev) => ({ ...prev, currency: e.target.value, offset: 0 })); }}
          className="input-field"
        >
          <option value="NGN">NGN</option>
          <option value="USD">USD</option>
        </select>
        {supplierSearch && (
          <button
            onClick={() => { setFilters((prev) => ({ ...prev, supplierSearch: '', offset: 0 })); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </button>
        )}
        <button
          onClick={exportAging}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70 ml-auto"
        >
          <Download className="w-4 h-4" />
          Export aging
        </button>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.suppliers || []}
        keyField="supplier_id"
        loading={isLoading}
        emptyMessage="No accounts payable found"
      />

      {/* Pagination */}
      {totalSuppliers > limit && (
        <Pagination
          total={totalSuppliers}
          limit={limit}
          offset={offset}
          onPageChange={(newOffset) => setFilters((prev) => ({ ...prev, offset: newOffset }))}
          onLimitChange={(newLimit) => {
            setFilters((prev) => ({ ...prev, limit: newLimit, offset: 0 }));
          }}
        />
      )}
    </div>
  );
}
