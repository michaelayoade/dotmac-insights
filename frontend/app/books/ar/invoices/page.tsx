'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinanceInvoices } from '@/hooks/useApi';
import { cn, formatCurrency } from '@/lib/utils';
import { Plus, Filter, FileText, Calendar, User, CheckCircle2, Clock, AlertTriangle, FileEdit, XCircle } from 'lucide-react';

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs text-slate-muted mb-1">{children}</label>;
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    draft: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-slate-300', icon: <FileEdit className="w-3 h-3" /> },
    pending: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', icon: <Clock className="w-3 h-3" /> },
    paid: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: <CheckCircle2 className="w-3 h-3" /> },
    partially_paid: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/40', text: 'text-cyan-300', icon: <Clock className="w-3 h-3" /> },
    overdue: { bg: 'bg-rose-500/10', border: 'border-rose-500/40', text: 'text-rose-300', icon: <AlertTriangle className="w-3 h-3" /> },
    cancelled: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-slate-400', icon: <XCircle className="w-3 h-3" /> },
  };
  const style = config[normalizedStatus] || config.pending;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', style.bg, style.border, style.text)}>
      {style.icon}
      <span className="capitalize">{(status || 'Pending').replace('_', ' ')}</span>
    </span>
  );
}

export default function BooksInvoicesPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useFinanceInvoices({
    status: status || undefined,
    currency: currency || undefined,
    search: search || undefined,
    page,
    page_size: pageSize,
  });

  const invoices = (data as any)?.invoices || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'number',
      header: 'Invoice Number',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-teal-electric font-medium">{item.invoice_number || `#${item.id}`}</span>
          <span className="text-slate-muted text-xs">{formatDate(item.invoice_date)}</span>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer Name',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-white">
          <User className="w-3 h-3 text-slate-muted" />
          <span className="font-medium">{item.customer_name || item.customer?.name || 'Unknown'}</span>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Invoice Amount',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <div className="text-white font-mono">{formatCurrency(item.total_amount ?? item.amount, item.currency)}</div>
          <div className="text-xs text-emerald-400">Paid: {formatCurrency(item.amount_paid ?? 0, item.currency)}</div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <StatusBadge status={item.status} />,
    },
    {
      key: 'due',
      header: 'Due Date',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-slate-muted text-sm">
          <Calendar className="w-3 h-3" />
          <span>{formatDate(item.due_date)}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AR Invoices</h1>
          <p className="text-slate-muted text-sm">Create and manage sales invoices</p>
        </div>
        <Link
          href="/books/ar/invoices/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Invoice
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <p className="text-xs text-slate-muted mb-3">Filter Invoices</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <FormLabel>Search</FormLabel>
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Invoice number or description..."
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div>
            <FormLabel>Status</FormLabel>
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending">Pending</option>
              <option value="paid">Paid</option>
              <option value="partially_paid">Partially Paid</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>
          <div>
            <FormLabel>Currency</FormLabel>
            <select
              value={currency}
              onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="NGN">NGN</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={invoices}
        keyField="id"
        loading={isLoading}
        emptyMessage="No invoices found"
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
