'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinancePayments } from '@/hooks/useApi';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Plus, Calendar, CreditCard, User, CheckCircle2, Clock, AlertTriangle, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput, FilterSelect, StatusPill, LinkButton } from '@/components/ui';

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { tone: StatusTone; icon: LucideIcon }> = {
    pending: { tone: 'warning', icon: Clock },
    completed: { tone: 'success', icon: CheckCircle2 },
    failed: { tone: 'danger', icon: AlertTriangle },
    refunded: { tone: 'default', icon: XCircle },
  };
  const style = config[normalizedStatus] || config.pending;
  return (
    <StatusPill
      label={formatStatusLabel(status || 'pending')}
      tone={style.tone}
      icon={style.icon}
      className="border border-current/30"
    />
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
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.payment_date)}</span>
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
          <div className="text-foreground font-mono">{formatAccountingCurrency(item.amount, item.currency)}</div>
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
        <LinkButton href="/books/accounts-receivable/payments/new" module="books" icon={Plus}>
          New Payment
        </LinkButton>
      </div>

      <FilterCard contentClassName="grid grid-cols-1 md:grid-cols-4 gap-3">
        <FilterInput
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search receipt/reference"
        />
        <FilterSelect
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
        >
          <option value="">Status</option>
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </FilterSelect>
        <FilterInput
          value={currency}
          onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
          placeholder="Currency"
        />
      </FilterCard>

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
