'use client';

import { useState } from 'react';
import { useAccountingTrialBalance } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { cn, formatCurrency } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import { AlertTriangle, Scale, CheckCircle2, XCircle, Calendar, Download, BarChart2 } from 'lucide-react';

function getAccountTypeColor(type: string) {
  const colors: Record<string, string> = {
    asset: 'text-blue-400',
    liability: 'text-red-400',
    equity: 'text-green-400',
    income: 'text-teal-400',
    revenue: 'text-teal-400',
    expense: 'text-orange-400',
  };
  return colors[type?.toLowerCase()] || 'text-slate-muted';
}

export default function TrialBalancePage() {
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [drill, setDrill] = useState<boolean>(false);

  const params = { end_date: asOfDate || undefined, drill: drill || undefined };
  const { data, isLoading, error } = useAccountingTrialBalance(params);

  const exportBalance = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/trial-balance/export', { ...params, format });
    window.open(url, '_blank');
  };

  const rows = (data?.accounts || []).map((acc, idx) => ({
    ...acc,
    rowId: `${acc.account_number}-${acc.account_name}-${idx}`,
  }));

  const columns = [
    {
      key: 'account_number',
      header: 'Account #',
      sortable: true,
      render: (item: any) => (
        <span className="font-mono text-teal-electric">{item.account_number}</span>
      ),
    },
    {
      key: 'account_name',
      header: 'Account Name',
      sortable: true,
      render: (item: any) => (
        <span className="text-white">{item.account_name}</span>
      ),
    },
    {
      key: 'account_type',
      header: 'Type',
      render: (item: any) => (
        <span className={cn('capitalize', getAccountTypeColor(item.account_type))}>
          {item.account_type || '-'}
        </span>
      ),
    },
    {
      key: 'debit',
      header: 'Debit',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn('font-mono', item.debit > 0 ? 'text-blue-400' : 'text-slate-muted')}>
          {item.debit > 0 ? formatCurrency(item.debit) : '-'}
        </span>
      ),
    },
    {
      key: 'credit',
      header: 'Credit',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn('font-mono', item.credit > 0 ? 'text-green-400' : 'text-slate-muted')}>
          {item.credit > 0 ? formatCurrency(item.credit) : '-'}
        </span>
      ),
    },
    {
      key: 'balance',
      header: 'Balance',
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
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load trial balance</p>
      </div>
    );
  }

  const isBalanced = data?.is_balanced ?? true;
  const difference = data?.difference ?? 0;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Debit</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatCurrency(data?.total_debit || 0)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Credit</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(data?.total_credit || 0)}</p>
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
            difference === 0 ? 'text-white' : 'text-yellow-400'
          )}>
            {formatCurrency(difference)}
          </p>
        </div>
      </div>

      {/* Date Filter */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-muted" />
          <label className="text-slate-muted text-sm">As of Date:</label>
        </div>
        <input
          type="date"
          value={asOfDate}
          onChange={(e) => setAsOfDate(e.target.value)}
          className="input-field"
        />
        <label className="flex items-center gap-2 text-slate-muted text-sm">
          <input type="checkbox" checked={drill} onChange={(e) => setDrill(e.target.checked)} />
          Drill-down balances
        </label>
        {asOfDate && (
          <button
            onClick={() => { setAsOfDate(''); setDrill(false); }}
            className="text-slate-muted text-sm hover:text-white transition-colors"
          >
            Clear
          </button>
        )}
        <div className="flex gap-2">
          <button
            onClick={() => exportBalance('csv')}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <Download className="w-4 h-4" />
            CSV
          </button>
          <button
            onClick={() => exportBalance('pdf')}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <BarChart2 className="w-4 h-4" />
            PDF
          </button>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={rows}
        keyField="rowId"
        loading={isLoading}
        emptyMessage="No trial balance data available"
      />

      {/* Totals Row */}
      {data && (
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
          <div className="flex justify-between items-center">
            <span className="text-white font-semibold">Total</span>
            <div className="flex gap-8">
              <div className="text-right">
                <p className="text-slate-muted text-xs">Debit</p>
                <p className="font-mono font-bold text-blue-400">{formatCurrency(data.total_debit)}</p>
              </div>
              <div className="text-right">
                <p className="text-slate-muted text-xs">Credit</p>
                <p className="font-mono font-bold text-green-400">{formatCurrency(data.total_credit)}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
