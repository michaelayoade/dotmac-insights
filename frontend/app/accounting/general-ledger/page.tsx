'use client';

import { useState } from 'react';
import { useAccountingGeneralLedger } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
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

  const columns = [
    {
      key: 'date',
      header: 'Date',
      sortable: true,
      render: (item: any) => (
        <span className="text-slate-muted">{formatDate(item.posting_date)}</span>
      ),
    },
    {
      key: 'account',
      header: 'Account',
      render: (item: any) => (
        <div>
          <span className="font-mono text-teal-electric text-sm">{item.account}</span>
          <span className="text-white ml-2">{item.account_name || ''}</span>
        </div>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item: any) => (
        <span className="text-slate-300 text-sm truncate max-w-[250px] block">
          {item.remarks || item.voucher_no || item.party || '-'}
        </span>
      ),
    },
    {
      key: 'debit',
      header: 'Debit',
      align: 'right' as const,
      render: (item: any) => (
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
      render: (item: any) => (
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
      render: (item: any) => (
        <span className={cn(
          'font-mono font-semibold',
          (item.balance || 0) >= 0 ? 'text-white' : 'text-red-400'
        )}>
          {formatCurrency(item.balance)}
        </span>
      ),
    },
    {
      key: 'reference',
      header: 'Reference',
      render: (item: any) => (
        <div className="text-slate-muted text-xs font-mono space-y-0.5">
          <div>{item.voucher_no || '-'}</div>
          {item.voucher_type && <div className="uppercase tracking-wide">{item.voucher_type}</div>}
        </div>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load general ledger</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      {data?.summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Total Entries</p>
            <p className="text-2xl font-bold text-white">{data.total || 0}</p>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
            <p className="text-blue-400 text-sm">Total Debits</p>
            <p className="text-2xl font-bold text-blue-400">{formatCurrency(data.summary.total_debit)}</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
            <p className="text-green-400 text-sm">Total Credits</p>
            <p className="text-2xl font-bold text-green-400">{formatCurrency(data.summary.total_credit)}</p>
          </div>
          <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Net Change</p>
            <p className={cn(
              'text-2xl font-bold',
              ((data.summary.total_debit || 0) - (data.summary.total_credit || 0)) >= 0 ? 'text-green-400' : 'text-red-400'
            )}>
              {formatCurrency((data.summary.total_debit || 0) - (data.summary.total_credit || 0))}
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
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <span className="text-slate-muted">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setOffset(0); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <div className="flex-1 min-w-[160px] max-w-xs">
          <input
            type="text"
            placeholder="Filter by account code..."
            value={accountCode}
            onChange={(e) => { setAccountCode(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        {(startDate || endDate || accountCode) && (
          <button
            onClick={() => { setStartDate(''); setEndDate(''); setAccountCode(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-white transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.entries || data?.data || []}
        keyField="id"
        loading={isLoading}
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
