'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { usePurchasingBills } from '@/hooks/useApi';
import { formatCurrency, cn } from '@/lib/utils';
import { Plus, Filter, Calendar, Landmark, CheckCircle2, Clock, AlertTriangle, FileEdit, XCircle } from 'lucide-react';

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    draft: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-slate-300', icon: <FileEdit className="w-3 h-3" /> },
    submitted: { bg: 'bg-blue-500/10', border: 'border-blue-500/40', text: 'text-blue-300', icon: <Clock className="w-3 h-3" /> },
    unpaid: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', icon: <Clock className="w-3 h-3" /> },
    paid: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: <CheckCircle2 className="w-3 h-3" /> },
    partially_paid: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/40', text: 'text-cyan-300', icon: <Clock className="w-3 h-3" /> },
    overdue: { bg: 'bg-rose-500/10', border: 'border-rose-500/40', text: 'text-rose-300', icon: <AlertTriangle className="w-3 h-3" /> },
    cancelled: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-slate-400', icon: <XCircle className="w-3 h-3" /> },
  };
  const style = config[normalizedStatus] || config.submitted;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', style.bg, style.border, style.text)}>
      {style.icon}
      <span className="capitalize">{(status || 'Submitted').replace('_', ' ')}</span>
    </span>
  );
}

export default function BooksBillsPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = usePurchasingBills({
    status: status || undefined,
    currency: currency || undefined,
    search: search || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const bills = (data as any)?.bills || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'number',
      header: 'Bill',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-white">{item.erpnext_id || item.name || `#${item.id}`}</span>
          <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span>
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
          <div className="text-white font-mono">{formatCurrency(item.grand_total ?? item.amount, item.currency)}</div>
          <div className="text-xs text-slate-muted">Outstanding: {formatCurrency(item.outstanding_amount ?? 0, item.currency)}</div>
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
      header: 'Due',
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
          <h1 className="text-2xl font-bold text-white">AP Bills</h1>
          <p className="text-slate-muted text-sm">Capture vendor bills</p>
        </div>
        <Link
          href="/books/accounts-payable/bills/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Bill
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
            placeholder="Search supplier/number"
            className="input-field"
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="input-field"
          >
            <option value="">Status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="paid">Paid</option>
            <option value="unpaid">Unpaid</option>
            <option value="overdue">Overdue</option>
          </select>
          <select
            value={currency}
            onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
            className="input-field"
          >
            <option value="NGN">NGN</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
          </select>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={bills}
        keyField="id"
        loading={isLoading}
        emptyMessage="No bills found"
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
