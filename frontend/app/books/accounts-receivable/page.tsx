'use client';

import { useState } from 'react';
import { useAccountingReceivables, useAccountingReceivablesEnhanced } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { buildApiUrl } from '@/lib/api';
import { Users, Calendar, Download } from 'lucide-react';
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

export default function AccountsReceivablePage() {
  const [filters, setFilters] = usePersistentState<{
    offset: number;
    limit: number;
    customerSearch: string;
    minAmount: string;
    enhanced: boolean;
  }>('books.ar.filters', {
    offset: 0,
    limit: 20,
    customerSearch: '',
    minAmount: '',
    enhanced: false,
  });
  const { offset, limit, customerSearch, minAmount, enhanced } = filters;

  const params = {
    search: customerSearch || undefined,
    min_amount: minAmount ? Number(minAmount) : undefined,
    limit,
    offset,
  };

  const base = useAccountingReceivables(params, {
    isPaused: () => enhanced,
  });
  const enhancedResult = useAccountingReceivablesEnhanced(params, {
    isPaused: () => !enhanced,
  });

  const data = enhanced ? enhancedResult.data : base.data;
  const isLoading = enhanced ? enhancedResult.isLoading : base.isLoading;
  const error = enhanced ? enhancedResult.error : base.error;

  const exportAging = () => {
    const url = buildApiUrl('/accounting/receivables-aging/export', {});
    window.open(url, '_blank');
  };

  const columns = [
    {
      key: 'customer',
      header: 'Customer',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-blue-400" />
          <span className="text-foreground text-sm">{item.customer_name || 'Unknown Customer'}</span>
        </div>
      ),
    },
    {
      key: 'total_receivable',
      header: 'Total Receivable',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground">{formatCurrency(item.total_receivable)}</span>
      ),
    },
    {
      key: 'current',
      header: 'Current',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-green-400">{formatCurrency(item.current)}</span>
      ),
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
      header: 'Oldest Invoice',
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.oldest_invoice_date)}</span>,
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  const summary = data?.aging || {};

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load accounts receivable."
          error={error as Error}
          onRetry={() => {
            base.mutate?.();
            enhancedResult.mutate?.();
          }}
        />
      )}
      {/* Aging Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total AR</p>
          <p className="text-2xl font-bold text-foreground">{formatCurrency(data?.total_receivable)}</p>
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
            placeholder="Search by customer name..."
            value={customerSearch}
            onChange={(e) => { setFilters((prev) => ({ ...prev, customerSearch: e.target.value, offset: 0 })); }}
            className="input-field"
          />
        </div>
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="number"
            placeholder="Min amount"
            value={minAmount}
            onChange={(e) => { setFilters((prev) => ({ ...prev, minAmount: e.target.value, offset: 0 })); }}
            className="input-field"
          />
        </div>
        <label className="flex items-center gap-2 text-slate-muted text-sm">
          <input type="checkbox" checked={enhanced} onChange={(e) => setFilters((prev) => ({ ...prev, enhanced: e.target.checked, offset: 0 }))} />
          Enhanced aging
        </label>
        {(customerSearch || minAmount) && (
          <button
            onClick={() => { setFilters((prev) => ({ ...prev, customerSearch: '', minAmount: '', offset: 0 })); }}
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
        data={data?.customers || []}
        keyField="customer_id"
        loading={isLoading}
        emptyMessage="No accounts receivable found"
      />

      {/* Pagination */}
      {data && (data.total || 0) > limit && (
        <Pagination
          total={data.total || 0}
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
