'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { usePurchasingBills } from '@/hooks/useApi';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Plus, Calendar, Landmark, CheckCircle2, Clock, AlertTriangle, FileEdit, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput, FilterSelect, StatusPill, LinkButton } from '@/components/ui';

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || '').toLowerCase();
  const config: Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }> = {
    draft: { tone: 'default', icon: FileEdit },
    submitted: { tone: 'info', icon: Clock },
    unpaid: { tone: 'warning', icon: Clock },
    paid: { tone: 'success', icon: CheckCircle2 },
    partially_paid: { tone: 'info', icon: Clock, label: 'Partially paid' },
    overdue: { tone: 'danger', icon: AlertTriangle },
    cancelled: { tone: 'default', icon: XCircle },
  };
  const style = config[normalizedStatus] || config.submitted;
  return (
    <StatusPill
      label={style.label || formatStatusLabel(status || 'submitted')}
      tone={style.tone}
      icon={style.icon}
      className="border border-current/30"
    />
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
          <span className="font-mono text-foreground">{item.erpnext_id || item.name || `#${item.id}`}</span>
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.posting_date)}</span>
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
          <div className="text-foreground font-mono">{formatAccountingCurrency(item.grand_total ?? item.amount, item.currency)}</div>
          <div className="text-xs text-slate-muted">Outstanding: {formatAccountingCurrency(item.outstanding_amount ?? 0, item.currency)}</div>
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
          <span>{formatAccountingDate(item.due_date)}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">AP Bills</h1>
          <p className="text-slate-muted text-sm">Capture vendor bills</p>
        </div>
        <LinkButton href="/books/accounts-payable/bills/new" module="books" icon={Plus}>
          New Bill
        </LinkButton>
      </div>

      <FilterCard contentClassName="grid grid-cols-1 md:grid-cols-4 gap-3">
        <FilterInput
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search supplier/number"
        />
        <FilterSelect
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
        >
          <option value="">Status</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="paid">Paid</option>
          <option value="unpaid">Unpaid</option>
          <option value="overdue">Overdue</option>
        </FilterSelect>
        <FilterSelect
          value={currency}
          onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
        >
          <option value="NGN">NGN</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="GBP">GBP</option>
        </FilterSelect>
      </FilterCard>

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
