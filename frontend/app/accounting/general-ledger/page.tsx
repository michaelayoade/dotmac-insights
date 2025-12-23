'use client';

import { useMemo, useState } from 'react';
import { useAccountingGeneralLedger } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import PageSkeleton from '@/components/PageSkeleton';
import { cn } from '@/lib/utils';
import { AlertTriangle } from 'lucide-react';
import { Button, FilterCard, FilterInput } from '@/components/ui';
import { getGeneralLedgerColumns } from '@/lib/config/accounting-tables';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

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

  const columns = getGeneralLedgerColumns();

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
            <p className="text-2xl font-bold text-blue-400">{formatAccountingCurrency(totals.total_debit)}</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
            <p className="text-green-400 text-sm">Total Credits</p>
            <p className="text-2xl font-bold text-green-400">{formatAccountingCurrency(totals.total_credit)}</p>
          </div>
          <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Net Change</p>
            <p
              className={cn(
                'text-2xl font-bold',
                (totals.total_debit - totals.total_credit) >= 0 ? 'text-green-400' : 'text-red-400'
              )}
            >
              {formatAccountingCurrency(totals.total_debit - totals.total_credit)}
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <FilterCard
        actions={(startDate || endDate || accountCode) && (
          <Button
            onClick={() => { setStartDate(''); setEndDate(''); setAccountCode(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        contentClassName="flex flex-wrap gap-4 items-center"
      >
        <div className="flex items-center gap-2">
          <FilterInput
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setOffset(0); }}
          />
          <span className="text-slate-muted">to</span>
          <FilterInput
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setOffset(0); }}
          />
        </div>
        <FilterInput
          type="text"
          placeholder="Filter by account code..."
          value={accountCode}
          onChange={(e) => { setAccountCode(e.target.value); setOffset(0); }}
          className="flex-1 min-w-[160px] max-w-xs"
        />
      </FilterCard>

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
