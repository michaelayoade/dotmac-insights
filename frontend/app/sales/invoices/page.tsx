'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useFinanceInvoices } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { formatCurrency, formatDate } from '@/lib/formatters';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { FilterCard, FilterInput, FilterSelect, StatusPill, LoadingState } from '@/components/ui';
import { AlertTriangle, FileText, CreditCard, Receipt } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const STATUS_TONES: Record<string, StatusTone> = {
  paid: 'success',
  unpaid: 'warning',
  partially_paid: 'info',
  overdue: 'danger',
  cancelled: 'default',
};

export default function InvoicesPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('sales:read');
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'invoice_date' | 'total_amount' | 'status'>('invoice_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const currency = 'NGN';

  const canFetch = !authLoading && !missingScope;
  const { data, isLoading, error } = useFinanceInvoices(
    {
      status: status || undefined,
      overdue_only: overdueOnly || undefined,
      search: search || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      currency,
      page: Math.floor(offset / limit) + 1,
      page_size: limit,
    },
    { isPaused: () => !canFetch }
  );

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the sales:read permission to view invoices."
        backHref="/sales"
        backLabel="Back to Sales"
      />
    );
  }

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
        <span className="font-mono text-foreground">{formatCurrency(item.total_amount || 0, item.currency)}</span>
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
      render: (item: any) => (
        <StatusPill
          label={formatStatusLabel(item.status)}
          tone={STATUS_TONES[item.status?.toLowerCase()] || 'default'}
        />
      ),
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

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load invoices</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Invoices</h1>
        <Link
          href="/sales/invoices/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <FileText className="w-4 h-4" />
          New Invoice
        </Link>
      </div>
      {/* Filters */}
      <FilterCard contentClassName="flex flex-wrap gap-4 items-center">
        <FilterInput
          type="text"
          placeholder="Search invoices..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
          className="flex-1 min-w-[200px] max-w-md"
        />
        <FilterSelect
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All Status</option>
          <option value="paid">Paid</option>
          <option value="unpaid">Unpaid</option>
          <option value="partially_paid">Partially Paid</option>
          <option value="overdue">Overdue</option>
        </FilterSelect>
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
        <FilterSelect
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setOffset(0); }}
        >
          <option value="invoice_date">Invoice date</option>
          <option value="total_amount">Amount</option>
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
        data={data?.invoices || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No invoices found"
        onRowClick={(item: { id: number }) => router.push(`/sales/invoices/${item.id}`)}
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
