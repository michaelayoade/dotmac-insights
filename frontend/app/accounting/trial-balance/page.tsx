'use client';

import { useState } from 'react';
import { useAccountingTrialBalance } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, Scale, CheckCircle2, XCircle, Calendar } from 'lucide-react';
import { Button } from '@/components/ui';
import { getTrialBalanceColumns } from '@/lib/config/accounting-tables';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

export default function TrialBalancePage() {
  const [asOfDate, setAsOfDate] = useState<string>('');
  const { data, isLoading, error } = useAccountingTrialBalance({ end_date: asOfDate || undefined });

  const columns = getTrialBalanceColumns();

  const isBalanced = data?.is_balanced ?? true;
  const difference = data?.difference ?? 0;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load trial balance</p>
        </div>
      )}
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Debit</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatAccountingCurrency(data?.total_debit)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Credit</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatAccountingCurrency(data?.total_credit)}</p>
        </div>
        <div className={cn(
          'border rounded-xl p-5',
          isBalanced
            ? 'bg-green-500/10 border-green-500/30'
            : 'bg-red-500/10 border-red-500/30'
        )}>
          <div className="flex items-center gap-2 mb-2">
            {isBalanced ? (
              <CheckCircle2 className="w-5 h-5 text-green-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
            <p className={cn('text-sm', isBalanced ? 'text-green-400' : 'text-red-400')}>Status</p>
          </div>
          <p className={cn('text-2xl font-bold', isBalanced ? 'text-green-400' : 'text-red-400')}>
            {isBalanced ? 'Balanced' : 'Unbalanced'}
          </p>
        </div>
        <div className={cn(
          'border rounded-xl p-5',
          difference === 0
            ? 'bg-slate-card border-slate-border'
            : 'bg-yellow-500/10 border-yellow-500/30'
        )}>
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-5 h-5 text-slate-muted" />
            <p className="text-slate-muted text-sm">Difference</p>
          </div>
          <p className={cn(
            'text-2xl font-bold',
            difference === 0 ? 'text-foreground' : 'text-yellow-400'
          )}>
            {formatAccountingCurrency(difference)}
          </p>
        </div>
      </div>

      {/* Date Filter */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-muted" />
          <label className="text-slate-muted text-sm">As of Date:</label>
        </div>
        <input
          type="date"
          value={asOfDate}
          onChange={(e) => setAsOfDate(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        {asOfDate && (
          <Button
            onClick={() => setAsOfDate('')}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear
          </Button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.accounts || []}
        keyField="account_number"
        loading={isLoading}
        emptyMessage="No trial balance data available"
      />

      {/* Totals Row */}
      {data && (
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
          <div className="flex justify-between items-center">
            <span className="text-foreground font-semibold">Total</span>
            <div className="flex gap-8">
              <div className="text-right">
                <p className="text-slate-muted text-xs">Debit</p>
                <p className="font-mono font-bold text-blue-400">{formatAccountingCurrency(data.total_debit)}</p>
              </div>
              <div className="text-right">
                <p className="text-slate-muted text-xs">Credit</p>
                <p className="font-mono font-bold text-green-400">{formatAccountingCurrency(data.total_credit)}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
