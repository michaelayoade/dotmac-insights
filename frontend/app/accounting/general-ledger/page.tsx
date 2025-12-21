'use client';

import { useMemo, useState } from 'react';
import { useAccountingGeneralLedger } from '@/hooks/useApi';
import { AccountingGeneralLedgerEntry } from '@/lib/api';
import { DataTable, Pagination } from '@/components/DataTable';
import PageSkeleton from '@/components/PageSkeleton';
import { cn } from '@/lib/utils';
import { AlertTriangle, BookMarked, Calendar, ArrowUpRight, ArrowDownRight } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function GeneralLedgerPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [accountCode, setAccountCode] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const { data, isLoading, error } = useAccountingGeneralLedger({
    account: accountCode || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit,
    offset,
  });

  const entries = useMemo(() => data?.entries ?? [], [data?.entries]);
  const totals = useMemo(
    () =>
      entries.reduce(
        (acc, entry) => ({
          total_debit: acc.total_debit + (entry.debit || 0),
          total_credit: acc.total_credit + (entry.credit || 0),
        }),
        { total_debit: 0, total_credit: 0 }
      ),
    [entries]
  );

  if (isLoading && !data) {
    return <PageSkeleton showHeader={false} showStats statsCount={4} />;
  }

  const columns = [
    {
      key: 'date',
      header: 'Date',
      sortable: true,
      render: (item: AccountingGeneralLedgerEntry) => (
        <span className="text-slate-muted">{formatDate(item.posting_date)}</span>
      ),
    },
    {
      key: 'account',
      header: 'Account',
      render: (item: AccountingGeneralLedgerEntry) => (
        <div>
          <span className="font-mono text-teal-electric text-sm">{item.account}</span>
          <span className="text-foreground ml-2">{item.account_name || ''}</span>
        </div>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item: AccountingGeneralLedgerEntry) => (
        <span className="text-foreground-secondary text-sm truncate max-w-[250px] block">
          {item.remarks || item.voucher_no || item.party || '-'}
        </span>
      ),
    },
    {
      key: 'debit',
      header: 'Debit',
      align: 'right' as const,
      render: (item: AccountingGeneralLedgerEntry) => (
        <div className="flex items-center justify-end gap-1">
          {(item.debit || 0) > 0 && <ArrowUpRight className="w-3 h-3 text-blue-400" />}
          <span className={cn('font-mono', (item.debit || 0) > 0 ? 'text-blue-400' : 'text-slate-muted')}>
            {(item.debit || 0) > 0 ? formatCurrency(item.debit) : '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'credit',
      header: 'Credit',
      align: 'right' as const,
      render: (item: AccountingGeneralLedgerEntry) => (
        <div className="flex items-center justify-end gap-1">
          {(item.credit || 0) > 0 && <ArrowDownRight className="w-3 h-3 text-green-400" />}
          <span className={cn('font-mono', (item.credit || 0) > 0 ? 'text-green-400' : 'text-slate-muted')}>
            {(item.credit || 0) > 0 ? formatCurrency(item.credit) : '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'balance',
      header: 'Running Balance',
      align: 'right' as const,
      render: (item: AccountingGeneralLedgerEntry) => (
        <span
          className={cn(
            'font-mono font-semibold',
            (item.balance || 0) >= 0 ? 'text-foreground' : 'text-red-400'
          )}
        >
          {item.balance !== undefined && item.balance !== null ? formatCurrency(item.balance) : '-'}
        </span>
      ),
    },
    {
      key: 'reference',
      header: 'Reference',
      render: (item: AccountingGeneralLedgerEntry) => (
        <div className="text-slate-muted text-xs font-mono space-y-0.5">
          <div>{item.voucher_no || '-'}</div>
          {item.voucher_type && <div className="uppercase tracking-wide">{item.voucher_type}</div>}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load general ledger</p>
        </div>
      )}
      {/* Summary */}
      {!!(entries ?? []).length && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Total Entries</p>
            <p className="text-2xl font-bold text-foreground">{data?.total || 0}</p>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
            <p className="text-blue-400 text-sm">Total Debits</p>
            <p className="text-2xl font-bold text-blue-400">{formatCurrency(totals.total_debit)}</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
            <p className="text-green-400 text-sm">Total Credits</p>
            <p className="text-2xl font-bold text-green-400">{formatCurrency(totals.total_credit)}</p>
          </div>
          <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Net Change</p>
            <p
              className={cn(
                'text-2xl font-bold',
                (totals.total_debit - totals.total_credit) >= 0 ? 'text-green-400' : 'text-red-400'
              )}
            >
              {formatCurrency(totals.total_debit - totals.total_credit)}
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
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
        <div className="flex-1 min-w-[160px] max-w-xs">
          <input
            type="text"
            placeholder="Filter by account code..."
            value={accountCode}
            onChange={(e) => { setAccountCode(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        {(startDate || endDate || accountCode) && (
          <button
            onClick={() => { setStartDate(''); setEndDate(''); setAccountCode(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={entries ?? []}
        keyField="id"
        loading={isLoading && !data}
        emptyMessage="No ledger entries found"
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
