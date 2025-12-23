'use client';

import { useState } from 'react';
import { useAccountingJournalEntries } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, ClipboardList, Calendar } from 'lucide-react';
import { Button } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

export default function JournalEntriesPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [voucherType, setVoucherType] = useState<string>('');

  const { data, isLoading, error } = useAccountingJournalEntries({
    voucher_type: voucherType || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'entry_number',
      header: 'Entry #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-teal-electric">{item.voucher_no || `JE-${item.id}`}</span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      sortable: true,
      render: (item: any) => (
        <span className="text-slate-muted">{formatAccountingDate(item.posting_date)}</span>
      ),
    },
    {
      key: 'voucher_type',
      header: 'Type',
      render: (item: any) => (
        <span className="text-foreground text-sm">
          {item.voucher_type || '-'}
        </span>
      ),
    },
    {
      key: 'debit_total',
      header: 'Debit',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-blue-400">
          {formatAccountingCurrency(item.debit_total || item.total_debit)}
        </span>
      ),
    },
    {
      key: 'credit_total',
      header: 'Credit',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-green-400">
          {formatAccountingCurrency(item.credit_total || item.total_credit)}
        </span>
      ),
    },
    {
      key: 'remarks',
      header: 'Remarks',
      render: (item: any) => (
        <span className="text-slate-muted text-sm truncate max-w-[240px] block">
          {item.user_remark || '-'}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load journal entries</p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Entries</p>
          <p className="text-2xl font-bold text-foreground">{data?.total || 0}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Total Debit</p>
          <p className="text-2xl font-bold text-blue-400">{formatAccountingCurrency((data as any)?.summary?.total_debit)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Total Credit</p>
          <p className="text-2xl font-bold text-green-400">{formatAccountingCurrency((data as any)?.summary?.total_credit)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <select
            value={voucherType}
            onChange={(e) => { setVoucherType(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Types</option>
            <option value="Journal Entry">Journal Entry</option>
            <option value="Payment Entry">Payment Entry</option>
            <option value="Sales Invoice">Sales Invoice</option>
            <option value="Purchase Invoice">Purchase Invoice</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-muted" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setOffset(0); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <span className="text-slate-muted">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setOffset(0); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        {(startDate || endDate || voucherType) && (
          <Button
            onClick={() => { setStartDate(''); setEndDate(''); setVoucherType(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={(data as any)?.entries || (data as any)?.data || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No journal entries found"
      />

      {/* Pagination */}
      {data && (data.total || 0) > limit && (
        <Pagination
          total={data.total || 0}
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
