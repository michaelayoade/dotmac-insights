'use client';

import { useMemo, useState } from 'react';
import { useAccountingGeneralLedger } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import { Calendar, Download, BarChart2 } from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { Button } from '@/components/ui';
import { getGeneralLedgerColumns } from '@/lib/config/accounting-tables';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

export default function GeneralLedgerPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [accountCode, setAccountCode] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const setPresetRange = (days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    const toInput = (d: Date) => d.toISOString().slice(0, 10);
    setStartDate(toInput(start));
    setEndDate(toInput(end));
    setOffset(0);
  };

  const { data, isLoading, error, mutate } = useAccountingGeneralLedger({
    account: accountCode || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit,
    offset,
  });

  const entries = data?.entries;
  const totals = useMemo(
    () =>
      (entries ?? []).reduce(
        (acc, entry) => ({
          total_debit: acc.total_debit + (entry.debit || 0),
          total_credit: acc.total_credit + (entry.credit || 0),
        }),
        { total_debit: 0, total_credit: 0 }
      ),
    [entries]
  );

  const exportLedger = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/general-ledger/export', {
      account: accountCode || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      format,
    });
    window.open(url, '_blank');
  };

  const columns = getGeneralLedgerColumns();

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load general ledger."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Summary */}
      {!!(entries ?? []).length && (
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border">
            <span className="text-xs uppercase tracking-[0.08em] text-slate-muted">Entries</span>
            <span className="text-foreground font-semibold">{data?.total || 0}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/30">
            <span className="text-xs uppercase tracking-[0.08em] text-blue-300">Debits</span>
            <span className="text-blue-100 font-semibold">{formatAccountingCurrency(totals.total_debit)}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/30">
            <span className="text-xs uppercase tracking-[0.08em] text-green-300">Credits</span>
            <span className="text-green-100 font-semibold">{formatAccountingCurrency(totals.total_credit)}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border">
            <span className="text-xs uppercase tracking-[0.08em] text-slate-muted">Net</span>
            <span
              className={cn(
                'font-semibold',
                (totals.total_debit - totals.total_credit) >= 0 ? 'text-green-300' : 'text-red-300'
              )}
            >
              {formatAccountingCurrency(totals.total_debit - totals.total_credit)}
            </span>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-muted" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setOffset(0); }}
            className="input-field"
          />
          <span className="text-slate-muted">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setOffset(0); }}
            className="input-field"
          />
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setPresetRange(30)}
            className="text-xs px-3 py-1.5 rounded-md border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            Last 30d
          </Button>
          <Button
            onClick={() => {
              const now = new Date();
              const ytdStart = new Date(Date.UTC(now.getUTCFullYear(), 0, 1));
              const toInput = (d: Date) => d.toISOString().slice(0, 10);
              setStartDate(toInput(ytdStart));
              setEndDate(toInput(now));
              setOffset(0);
            }}
            className="text-xs px-3 py-1.5 rounded-md border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            YTD
          </Button>
        </div>
        <div className="flex-1 min-w-[160px] max-w-xs">
          <input
            type="text"
            placeholder="Filter by account code..."
            value={accountCode}
            onChange={(e) => { setAccountCode(e.target.value); setOffset(0); }}
            className="input-field"
          />
        </div>
        {(startDate || endDate || accountCode) && (
          <Button
            onClick={() => { setStartDate(''); setEndDate(''); setAccountCode(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        <div className="flex gap-2 ml-auto">
          <Button
            onClick={() => exportLedger('csv')}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <Download className="w-4 h-4" />
            CSV
          </Button>
          <Button
            onClick={() => exportLedger('pdf')}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <BarChart2 className="w-4 h-4" />
            PDF
          </Button>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={entries ?? []}
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
