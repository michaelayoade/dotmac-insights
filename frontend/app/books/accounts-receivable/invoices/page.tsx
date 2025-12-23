'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinanceInvoices } from '@/hooks/useApi';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Plus, FileText, Calendar, User, CheckCircle2, Clock, AlertTriangle, FileEdit, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput, FilterSelect, StatusPill, LinkButton } from '@/components/ui';

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs text-slate-muted mb-1">{children}</label>;
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }> = {
    draft: { tone: 'default', icon: FileEdit },
    pending: { tone: 'warning', icon: Clock },
    paid: { tone: 'success', icon: CheckCircle2 },
    partially_paid: { tone: 'info', icon: Clock, label: 'Partially paid' },
    overdue: { tone: 'danger', icon: AlertTriangle },
    cancelled: { tone: 'default', icon: XCircle },
  };
  const style = config[normalizedStatus] || config.pending;
  return (
    <StatusPill
      label={style.label || formatStatusLabel(status || 'pending')}
      tone={style.tone}
      icon={style.icon}
      className="border border-current/30"
    />
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
          <span className="text-slate-muted text-xs">{formatAccountingDate(item.invoice_date)}</span>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer Name',
      render: (item: any) => (
        <div className="flex items-center gap-2 text-foreground">
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
          <div className="text-foreground font-mono">{formatAccountingCurrency(item.total_amount ?? item.amount, item.currency)}</div>
          <div className="text-xs text-emerald-400">Paid: {formatAccountingCurrency(item.amount_paid ?? 0, item.currency)}</div>
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
          <span>{formatAccountingDate(item.due_date)}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">AR Invoices</h1>
          <p className="text-slate-muted text-sm">Create and manage sales invoices</p>
        </div>
        <LinkButton href="/books/accounts-receivable/invoices/new" module="books" icon={Plus}>
          New Invoice
        </LinkButton>
      </div>

      <FilterCard title="Filter Invoices" contentClassName="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <FormLabel>Search</FormLabel>
          <FilterInput
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Invoice number or description..."
          />
        </div>
        <div>
          <FormLabel>Status</FormLabel>
          <FilterSelect
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="partially_paid">Partially Paid</option>
            <option value="overdue">Overdue</option>
          </FilterSelect>
        </div>
        <div>
          <FormLabel>Currency</FormLabel>
          <FilterSelect
            value={currency}
            onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
          >
            <option value="NGN">NGN</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
          </FilterSelect>
        </div>
      </FilterCard>

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
