'use client';

import { useState } from 'react';
import { useAccountingReceivables } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Users } from 'lucide-react';
import { Button, FilterCard, FilterInput } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

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
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [customerId, setCustomerId] = useState<string>('');

  const { data, isLoading, error } = useAccountingReceivables({
    customer_id: customerId ? Number(customerId) : undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'customer',
      header: 'Customer',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-blue-400" />
          <div className="flex flex-col">
            <span className="text-foreground text-sm">{item.customer_name || 'Customer'}</span>
            <span className="text-xs text-slate-muted font-mono">#{item.customer_id}</span>
          </div>
        </div>
      ),
    },
    {
      key: 'total_receivable',
      header: 'Total Receivable',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground">{formatAccountingCurrency(item.total_receivable)}</span>
      ),
    },
    {
      key: 'current',
      header: 'Current',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-green-400">{formatAccountingCurrency(item.current)}</span>
      ),
    },
    {
      key: 'overdue_1_30',
      header: '1-30',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-yellow-400">{formatAccountingCurrency(item.overdue_1_30)}</span>,
    },
    {
      key: 'overdue_31_60',
      header: '31-60',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-orange-400">{formatAccountingCurrency(item.overdue_31_60)}</span>,
    },
    {
      key: 'overdue_61_90',
      header: '61-90',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-orange-400">{formatAccountingCurrency(item.overdue_61_90)}</span>,
    },
    {
      key: 'overdue_over_90',
      header: '90+',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-red-400">{formatAccountingCurrency(item.overdue_over_90)}</span>,
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
      render: (item: any) => <span className="text-slate-muted">{formatAccountingDate(item.oldest_invoice_date)}</span>,
    },
  ];

  const summary = (data?.aging as any) || {};
  const totalCustomers = data?.customers?.length || 0;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load accounts receivable</p>
        </div>
      )}
      {/* Aging Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total AR</p>
          <p className="text-2xl font-bold text-foreground">{formatAccountingCurrency(data?.total_receivable)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Current</p>
          <p className="text-xl font-bold text-green-400">{formatAccountingCurrency(summary.current)}</p>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <p className="text-yellow-400 text-sm">1-30 Days</p>
          <p className="text-xl font-bold text-yellow-400">{formatAccountingCurrency(summary['1_30'])}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">31-60 Days</p>
          <p className="text-xl font-bold text-orange-400">{formatAccountingCurrency(summary['31_60'])}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">60+ Days</p>
          <p className="text-xl font-bold text-red-400">{formatAccountingCurrency(summary.over_90)}</p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={customerId && (
          <Button
            onClick={() => { setCustomerId(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        contentClassName="flex flex-wrap gap-4 items-center"
      >
        <FilterInput
          type="number"
          placeholder="Filter by customer id"
          value={customerId}
          onChange={(e) => { setCustomerId(e.target.value); setOffset(0); }}
          className="flex-1 min-w-[200px] max-w-md"
        />
      </FilterCard>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.customers || []}
        keyField="customer_id"
        loading={isLoading}
        emptyMessage="No accounts receivable found"
      />

      {/* Pagination */}
      {totalCustomers > limit && (
        <Pagination
          total={totalCustomers}
          limit={limit}
          offset={offset}
          onPageChange={setOffset}
          onLimitChange={(newLimit) => {
            setLimit(newLimit);
            setOffset(0);
          }}
        />
      )}
    </div>
  );
}
