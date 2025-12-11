'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useFinanceCreditNotes } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, Receipt } from 'lucide-react';

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
    applied: 'bg-green-500/20 text-green-400 border-green-500/30',
    pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    partial: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    cancelled: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    expired: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const color = statusColors[status?.toLowerCase()] || statusColors.pending;
  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border', color)}>
      {status || 'Pending'}
    </span>
  );
}

export default function CreditNotesPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const currency = 'NGN';
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'issue_date' | 'amount' | 'customer_id' | 'invoice_id' | 'status'>('issue_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const router = useRouter();
  const searchParams = useSearchParams();
  const invoiceIdFilter = searchParams?.get('invoice_id');

  const { data, isLoading, error } = useFinanceCreditNotes({
    currency,
    search: search || undefined,
    invoice_id: invoiceIdFilter ? Number(invoiceIdFilter) : undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    limit,
    offset,
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
      key: 'credit_note_number',
      header: 'Credit Note #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-teal-electric">{item.credit_note_number || `CN-${item.id}`}</span>
        </div>
      ),
    },
    {
      key: 'invoice_id',
      header: 'Invoice',
      render: (item: any) => (
        item.invoice_id ? (
          <Link href={`/finance/invoices/${item.invoice_id}`} className="font-mono text-teal-electric hover:text-teal-glow">
            #{item.invoice_id}
          </Link>
        ) : (
          <span className="text-slate-muted">-</span>
        )
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      sortable: true,
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-red-400">-{formatCurrency(item.amount || 0, item.currency)}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => getStatusBadge(item.status),
    },
    {
      key: 'date',
      header: 'Date',
      sortable: true,
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.date)}</span>,
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (item: any) => (
        <span className="text-slate-muted text-sm truncate max-w-[200px] block">
          {item.reason || item.note || '-'}
        </span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load credit notes</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search credit notes..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setOffset(0); }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="issue_date">Issue date</option>
          <option value="amount">Amount</option>
          <option value="customer_id">Customer</option>
          <option value="invoice_id">Invoice</option>
          <option value="status">Status</option>
        </select>
        <select
          value={sortDir}
          onChange={(e) => { setSortDir(e.target.value as typeof sortDir); setOffset(0); }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.data || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No credit notes found"
        onRowClick={(item) => router.push(`/finance/credit-notes/${(item as any).id}`)}
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
