'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { usePurchasingDebitNotes } from '@/hooks/useApi';

import { Plus, Calendar, Landmark } from 'lucide-react';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';
import { FilterCard, FilterInput, FilterSelect, LinkButton } from '@/components/ui';

export default function BooksDebitNotesPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [search, setSearch] = useState('');

  const { data, isLoading } = usePurchasingDebitNotes({
    status: status || undefined,
    currency: currency || undefined,
    search: search || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const notes = (data as any)?.debit_notes || (data as any)?.data || [];
  const total = (data as any)?.total || 0;

  const columns = [
    {
      key: 'number',
      header: 'Debit Note',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-foreground">{item.debit_note_no || item.name || `#${item.id}`}</span>
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
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
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
          <h1 className="text-2xl font-bold text-foreground">AP Debit Notes</h1>
          <p className="text-slate-muted text-sm">Track vendor credits</p>
        </div>
        <LinkButton href="/books/accounts-payable/debit-notes/new" module="books" icon={Plus}>
          New Debit Note
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
        emptyMessage="No debit notes found"
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
