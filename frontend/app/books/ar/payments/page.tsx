'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinancePayments } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';
import { Plus, Filter, Calendar, CreditCard, User } from 'lucide-react';

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function BooksPaymentsPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useFinancePayments({
    status: status || undefined,
    currency: currency || undefined,
    search: search || undefined,
    page,
    page_size: pageSize,
  });

  const payments = data?.payments || data?.data || [];
  const total = data?.total || 0;

  const columns = [
    {
      key: 'receipt',
      header: 'Receipt',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-white">{item.receipt_number || `#${item.id}`}</span>
          <span className="text-slate-muted text-sm">{formatDate(item.payment_date)}</span>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-slate-200">
          <User className="w-3 h-3 text-slate-muted" />
          <span>{item.customer_name || item.customer?.name || 'Unknown'}</span>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <div className="text-white font-mono">{formatCurrency(item.amount, item.currency)}</div>
          <div className="text-xs text-slate-muted">{item.payment_method || '—'}</div>
        </div>
      ),
    },
    {
      key: 'invoice',
      header: 'Invoice',
      render: (item: any) => (
        <span className="text-slate-200 text-sm">{item.invoice?.invoice_number || item.invoice_id || '—'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AR Payments</h1>
          <p className="text-slate-muted text-sm">Record and review customer payments</p>
        </div>
        <Link
          href="/books/ar/payments/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Payment
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search receipt/reference"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">Status</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="refunded">Refunded</option>
          </select>
          <input
            value={currency}
            onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
            placeholder="Currency"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
      </div>

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
