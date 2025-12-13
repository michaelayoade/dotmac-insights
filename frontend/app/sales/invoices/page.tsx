'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useFinanceInvoices } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, FileText, CreditCard, Receipt } from 'lucide-react';

function formatCurrency(value: number, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function getStatusBadge(status: string) {
  const statusColors: Record<string, string> = {
    paid: 'bg-green-500/20 text-green-400 border-green-500/30',
    unpaid: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    partially_paid: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
    cancelled: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  };
  const color = statusColors[status.toLowerCase()] || statusColors.unpaid;
  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border', color)}>
      {status}
    </span>
  );
}

export default function InvoicesPage() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'invoice_date' | 'total_amount' | 'status'>('invoice_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const currency = 'NGN';

  const { data, isLoading, error } = useFinanceInvoices({
    status: status || undefined,
    overdue_only: overdueOnly || undefined,
    search: search || undefined,
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
          <span className="text-white text-sm">
            {item.customer_name || item.customer?.name || (item.customer_id ? `Customer ${item.customer_id}` : '—')}
          </span>
          <span className="text-xs text-slate-muted font-mono">
            {item.customer_id ? `#${item.customer_id}` : '—'}
          </span>
        </div>
      ),
    },
    {
      key: 'invoice_number',
      header: 'Invoice #',
      sortable: true,
      render: (item: any) => (
        <span className="font-mono text-teal-electric">{item.invoice_number || '-'}</span>
      ),
    },
    {
      key: 'total_amount',
      header: 'Amount',
      sortable: true,
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white">{formatCurrency(item.total_amount || 0, item.currency)}</span>
      ),
    },
    {
      key: 'amount_paid',
      header: 'Paid',
      sortable: true,
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-green-400">{formatCurrency(item.amount_paid || 0, item.currency)}</span>
      ),
    },
    {
      key: 'balance',
      header: 'Balance',
      sortable: true,
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn('font-mono', item.balance > 0 ? 'text-yellow-400' : 'text-slate-muted')}>
          {formatCurrency(item.balance || 0, item.currency)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => getStatusBadge(item.status),
    },
    {
      key: 'invoice_date',
      header: 'Date',
      sortable: true,
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.invoice_date)}</span>,
    },
    {
      key: 'due_date',
      header: 'Due Date',
      sortable: true,
      render: (item: any) => (
        <span className="text-slate-muted">{formatDate(item.due_date)}</span>
      ),
    },
    {
      key: 'links',
      header: 'Links',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-xs">
          <Link
            href={`/sales/payments?invoice_id=${item.id}`}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-elevated text-teal-electric border border-slate-border hover:border-teal-electric/50"
            onClick={(e) => e.stopPropagation()}
          >
            <CreditCard className="w-3 h-3" />
            Payments
          </Link>
          <Link
            href={`/sales/credit-notes?invoice_id=${item.id}`}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-elevated text-amber-warn border border-slate-border hover:border-amber-warn/50"
            onClick={(e) => e.stopPropagation()}
          >
            <Receipt className="w-3 h-3" />
            Credits
          </Link>
        </div>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load invoices</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Invoices</h1>
        <Link
          href="/sales/invoices/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <FileText className="w-4 h-4" />
          New Invoice
        </Link>
      </div>
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search invoices..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Status</option>
          <option value="paid">Paid</option>
          <option value="unpaid">Unpaid</option>
          <option value="partially_paid">Partially Paid</option>
          <option value="overdue">Overdue</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => {
              setOverdueOnly(e.target.checked);
              setOffset(0);
            }}
            className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
          />
          Overdue only
        </label>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setOffset(0); }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="invoice_date">Invoice date</option>
          <option value="total_amount">Amount</option>
          <option value="status">Status</option>
        </select>
        <select
          value={sortOrder}
          onChange={(e) => { setSortOrder(e.target.value as typeof sortOrder); setOffset(0); }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.invoices || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No invoices found"
        onRowClick={(item) => router.push(`/sales/invoices/${(item as any).id}`)}
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
