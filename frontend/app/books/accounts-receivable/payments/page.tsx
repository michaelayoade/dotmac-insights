'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinancePayments } from '@/hooks/useApi';
import { formatCurrency, cn } from '@/lib/utils';
import { Plus, Filter, Calendar, CreditCard, User, CheckCircle2, Clock, AlertTriangle, XCircle } from 'lucide-react';

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    pending: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', icon: <Clock className="w-3 h-3" /> },
    completed: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: <CheckCircle2 className="w-3 h-3" /> },
    failed: { bg: 'bg-rose-500/10', border: 'border-rose-500/40', text: 'text-rose-300', icon: <AlertTriangle className="w-3 h-3" /> },
    refunded: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-foreground-secondary', icon: <XCircle className="w-3 h-3" /> },
  };
  const style = config[normalizedStatus] || config.pending;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', style.bg, style.border, style.text)}>
      {style.icon}
      <span className="capitalize">{status || 'Pending'}</span>
    </span>
  );
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

  const payments = (data as any)?.payments || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'receipt',
      header: 'Receipt',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-foreground">{item.receipt_number || `#${item.id}`}</span>
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
          <div className="text-foreground font-mono">{formatCurrency(item.amount, item.currency)}</div>
          <div className="text-xs text-slate-muted">{item.payment_method || '—'}</div>
        </div>
      ),
    },
    {
      key: 'invoice',
      header: 'Invoice',
      render: (item: any) => (
        <span className="text-slate-200 text-sm">{item.invoice?.invoice_number || '—'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <StatusBadge status={item.status} />,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">AR Payments</h1>
          <p className="text-slate-muted text-sm">Record and review customer payments</p>
        </div>
        <Link
          href="/books/accounts-receivable/payments/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Payment
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-foreground text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search receipt/reference"
            className="input-field"
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="input-field"
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
            className="input-field"
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
