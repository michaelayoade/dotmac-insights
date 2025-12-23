'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { usePurchasingPayments } from '@/hooks/useApi';

import { Calendar, CreditCard, Landmark } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput } from '@/components/ui';

export default function BooksApPaymentsPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = usePurchasingPayments({
    currency: currency || undefined,
    search: search || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const payments = (data as any)?.payments || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'receipt',
      header: 'Payment',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-foreground">{item.receipt_number || `#${item.id}`}</span>
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.payment_date)}</span>
        </div>
      ),
    },
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-slate-200">
          <Landmark className="w-3 h-3 text-slate-muted" />
          <span>{item.supplier_name || item.supplier || 'Unknown'}</span>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <div className="text-foreground font-mono">{formatAccountingCurrency(item.amount, item.currency)}</div>
          <div className="text-xs text-slate-muted">{item.payment_method || '—'}</div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
    },
    {
      key: 'bill',
      header: 'Bill',
      render: (item: any) => <span className="text-slate-200 text-sm">{item.purchase_invoice_id || '—'}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">AP Payments</h1>
          <p className="text-slate-muted text-sm">Vendor payments</p>
        </div>
        <Link
          href="/books/accounts-payable/bills"
          className="text-sm text-teal-electric hover:text-teal-electric/80"
        >
          Go to Bills
        </Link>
      </div>

      <FilterCard contentClassName="grid grid-cols-1 md:grid-cols-3 gap-3">
        <FilterInput
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search receipt/reference"
        />
        <FilterInput
          value={currency}
          onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
          placeholder="Currency"
        />
      </FilterCard>

      <DataTable
        columns={columns}
        data={payments}
        keyField="id"
        loading={isLoading}
        emptyMessage="No payments found"
      />

      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(offset) => setPage(Math.floor(offset / pageSize) + 1)}
          onLimitChange={(limit) => { setPageSize(limit); setPage(1); }}
        />
      )}
    </div>
  );
}
