'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useFinanceCreditNotes } from '@/hooks/useApi';

import { Plus, Calendar, User } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput, FilterSelect, LinkButton } from '@/components/ui';

export default function BooksCreditNotesPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useFinanceCreditNotes({
    status: status || undefined,
    currency: currency || undefined,
    search: search || undefined,
    page,
    page_size: pageSize,
  });

  const notes = (data as any)?.credit_notes || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'number',
      header: 'Credit Note',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-foreground">{item.credit_number || `#${item.id}`}</span>
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.issue_date)}</span>
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
          <div className="text-xs text-slate-muted">{item.status}</div>
        </div>
      ),
    },
    {
      key: 'invoice',
      header: 'Invoice',
      render: (item: any) => <span className="text-slate-200 text-sm">{item.invoice_id || '—'}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">AR Credit Notes</h1>
          <p className="text-slate-muted text-sm">Issue and track customer credits</p>
        </div>
        <LinkButton href="/books/accounts-receivable/credit-notes/new" module="books" icon={Plus}>
          New Credit Note
        </LinkButton>
      </div>

      <FilterCard contentClassName="grid grid-cols-1 md:grid-cols-4 gap-3">
        <FilterInput
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search credit number/description"
        />
        <FilterSelect
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
        >
          <option value="">Status</option>
          <option value="draft">Draft</option>
          <option value="issued">Issued</option>
          <option value="applied">Applied</option>
          <option value="cancelled">Cancelled</option>
        </FilterSelect>
        <FilterInput
          value={currency}
          onChange={(e) => { setCurrency(e.target.value); setPage(1); }}
          placeholder="Currency"
        />
      </FilterCard>

      <DataTable
        columns={columns}
        data={notes}
        keyField="id"
        loading={isLoading}
        emptyMessage="No credit notes found"
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
