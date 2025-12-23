'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useFinancePayments } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, CreditCard, Banknote, Wallet } from 'lucide-react';
import { FilterCard, FilterInput, FilterSelect } from '@/components/ui';
import { formatCurrency, formatDate } from '@/lib/formatters';

function getPaymentMethodIcon(method: string) {
  const methodLower = method?.toLowerCase() || '';
  if (methodLower.includes('bank') || methodLower.includes('transfer')) {
    return <Banknote className="w-4 h-4 text-blue-400" />;
  }
  if (methodLower.includes('card') || methodLower.includes('credit') || methodLower.includes('debit')) {
    return <CreditCard className="w-4 h-4 text-purple-400" />;
  }
  return <Wallet className="w-4 h-4 text-teal-electric" />;
}

export default function PaymentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'payment_date' | 'amount' | 'status'>('payment_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const currency = 'NGN';
  const invoiceIdFilter = searchParams?.get('invoice_id');

  const { data, isLoading, error } = useFinancePayments({
    status: status || undefined,
    payment_method: paymentMethod || undefined,
    search: search || undefined,
    invoice_id: invoiceIdFilter ? Number(invoiceIdFilter) : undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    currency,
    page: Math.floor(offset / limit) + 1,
    page_size: limit,
  });

  const columns = [
    {
      key: 'customer',
      header: 'Customer',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="text-foreground text-sm">
            {item.customer_name || item.customer?.name || (item.customer_id ? `Customer ${item.customer_id}` : '—')}
          </span>
          <span className="text-xs text-slate-muted font-mono">
            {item.customer_id ? `#${item.customer_id}` : '—'}
          </span>
        </div>
      ),
    },
    {
      key: 'receipt_number',
      header: 'Receipt #',
      sortable: true,
      render: (item: any) => (
        <span className="font-mono text-teal-electric">{item.receipt_number || `#${item.id}`}</span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      sortable: true,
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn(
          'font-mono',
          item.status === 'failed' ? 'text-red-400' : 'text-green-400'
        )}>
          {formatCurrency(item.amount || 0, item.currency)}
        </span>
      ),
    },
    {
      key: 'payment_method',
      header: 'Method',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          {getPaymentMethodIcon(item.payment_method)}
          <span className="text-slate-muted">{item.payment_method || '-'}</span>
        </div>
      ),
    },
    {
      key: 'invoice_id',
      header: 'Invoice',
      render: (item: any) => (
        item.invoice_id ? (
          <Link href={`/sales/invoices/${item.invoice_id}`} className="font-mono text-teal-electric hover:text-teal-glow">
            #{item.invoice_id}
          </Link>
        ) : (
          <span className="font-mono text-slate-muted">-</span>
        )
      ),
    },
    {
      key: 'payment_date',
      header: 'Date',
      sortable: true,
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.payment_date)}</span>,
    },
    {
      key: 'transaction_reference',
      header: 'Reference',
      render: (item: any) => (
        <span className="text-slate-muted text-sm truncate max-w-[200px] block">
          {item.transaction_reference || item.gateway_reference || item.notes || '-'}
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
        </div>
      )}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Payments</h1>
        <Link
          href="/sales/payments/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <CreditCard className="w-4 h-4" />
          New Payment
        </Link>
      </div>
      {/* Filters */}
      <FilterCard contentClassName="flex flex-wrap gap-4 items-center">
        <FilterSelect
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All Status</option>
          <option value="completed">Completed</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </FilterSelect>
        <FilterInput
          type="text"
          placeholder="Search receipts or references..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
          className="flex-1 min-w-[200px] max-w-md"
        />
        <FilterSelect
          value={paymentMethod}
          onChange={(e) => {
            setPaymentMethod(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All Methods</option>
          <option value="bank_transfer">Bank Transfer</option>
          <option value="card">Card</option>
          <option value="cash">Cash</option>
        </FilterSelect>
        <FilterSelect
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setOffset(0); }}
        >
          <option value="payment_date">Payment date</option>
          <option value="amount">Amount</option>
          <option value="status">Status</option>
        </FilterSelect>
        <FilterSelect
          value={sortOrder}
          onChange={(e) => { setSortOrder(e.target.value as typeof sortOrder); setOffset(0); }}
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </FilterSelect>
      </FilterCard>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.payments || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No payments found"
        onRowClick={(item: { id: number }) => router.push(`/sales/payments/${item.id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {data && data.total > limit && (
        <Pagination
          total={data.total}
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
