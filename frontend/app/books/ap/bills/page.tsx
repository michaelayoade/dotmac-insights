'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataTable, Pagination } from '@/components/DataTable';
import { usePurchasingBills } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';
import { Plus, Filter, Calendar, Landmark } from 'lucide-react';

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
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

  const bills = data?.bills || data?.data || [];
  const total = data?.total || 0;

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
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
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
          href="/books/ap/bills/new"
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
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">Status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="paid">Paid</option>
            <option value="unpaid">Unpaid</option>
            <option value="overdue">Overdue</option>
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
