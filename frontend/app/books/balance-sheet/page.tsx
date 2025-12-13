'use client';

import { useState } from 'react';
import { useAccountingBalanceSheet } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import { AlertTriangle, FileSpreadsheet, Building2, CreditCard, PiggyBank, Calendar, Loader2, Download, BarChart2 } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

interface AccountLineProps {
  name: string;
  amount: number;
  indent?: number;
  bold?: boolean;
  className?: string;
}

function AccountLine({ name, amount, indent = 0, bold, className }: AccountLineProps) {
  return (
    <div className={cn(
      'flex justify-between items-center py-2 border-b border-slate-border/50',
      bold && 'font-semibold',
      className
    )} style={{ paddingLeft: `${indent * 1.5}rem` }}>
      <span className="text-white">{name}</span>
      <span className={cn(
        'font-mono',
        amount >= 0 ? 'text-white' : 'text-red-400'
      )}>
        {formatCurrency(amount)}
      </span>
    </div>
  );
}

interface SectionProps {
  title: string;
  icon: React.ElementType;
  items: Array<{ name: string; amount: number; children?: Array<{ name: string; amount: number }> }>;
  total: number;
  colorClass: string;
}

function Section({ title, icon: Icon, items, total, colorClass }: SectionProps) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <Icon className={cn('w-5 h-5', colorClass)} />
        <h2 className={cn('text-lg font-semibold', colorClass)}>{title}</h2>
      </div>
      <div className="space-y-1">
        {items.map((item, index) => (
          <div key={index}>
            <AccountLine
              name={item.name}
              amount={item.amount}
              bold={item.children && item.children.length > 0}
            />
            {item.children?.map((child, childIndex) => (
              <AccountLine
                key={childIndex}
                name={child.name}
                amount={child.amount}
                indent={1}
              />
            ))}
          </div>
        ))}
      </div>
      <div className={cn('flex justify-between items-center pt-4 mt-4 border-t-2 border-slate-border')}>
        <span className={cn('font-bold', colorClass)}>Total {title}</span>
        <span className={cn('font-mono font-bold text-lg', colorClass)}>
          {formatCurrency(total)}
        </span>
      </div>
    </div>
  );
}

export default function BalanceSheetPage() {
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [commonSize, setCommonSize] = useState<boolean>(false);
  const params = { as_of_date: asOfDate || undefined, common_size: commonSize || undefined };
  const { data, isLoading, error } = useAccountingBalanceSheet(params);

  const exportSheet = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/balance-sheet/export', { ...params, format });
    window.open(url, '_blank');
  };

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load balance sheet</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-teal-electric" />
      </div>
    );
  }

  const assets = data?.assets || { current_assets: [], fixed_assets: [], other_assets: [], total: 0 };
  const liabilities = data?.liabilities || { current_liabilities: [], long_term_liabilities: [], total: 0 };
  const equity = data?.equity || { items: [], retained_earnings: 0, total: 0 };

  const mapSection = (label: string, rows: Array<{ account: string; balance: number }>) => ({
    name: label,
    amount: rows.reduce((sum, row) => sum + (row.balance || 0), 0),
    children: rows.map((row) => ({ name: row.account, amount: row.balance })),
  });

  const assetItems = [
    mapSection('Current Assets', assets.current_assets || []),
    mapSection('Fixed Assets', assets.fixed_assets || []),
    mapSection('Other Assets', assets.other_assets || []),
  ].filter((item) => item.children?.length);

  const liabilityItems = [
    mapSection('Current Liabilities', liabilities.current_liabilities || []),
    mapSection('Long-term Liabilities', liabilities.long_term_liabilities || []),
  ].filter((item) => item.children?.length);

  const equityItems = [
    ...(equity.items || []).map((row) => ({ name: row.account, amount: row.balance, children: [] as any[] })),
    { name: 'Retained Earnings', amount: equity.retained_earnings || 0, children: [] as any[] },
  ];

  return (
    <div className="space-y-6">
      {/* Header with date */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Balance Sheet</h2>
          {data?.as_of_date && (
            <span className="text-slate-muted text-sm">
              as of {typeof data.as_of_date === 'string'
                ? data.as_of_date
                : (() => {
                  const asOf: any = data.as_of_date;
                  return asOf?.end_date || asOf?.start_date || '-';
                })()}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <label className="flex items-center gap-2 text-slate-muted text-sm">
            <input
              type="checkbox"
              checked={commonSize}
              onChange={(e) => setCommonSize(e.target.checked)}
            />
            Common size
          </label>
          {asOfDate && (
            <button
              onClick={() => { setAsOfDate(''); setCommonSize(false); }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear
            </button>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => exportSheet('csv')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
            >
              <Download className="w-4 h-4" />
              CSV
            </button>
            <button
              onClick={() => exportSheet('pdf')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
            >
              <BarChart2 className="w-4 h-4" />
              PDF
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Building2 className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Assets</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatCurrency(assets.total)}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <CreditCard className="w-5 h-5 text-red-400" />
            <p className="text-red-400 text-sm">Total Liabilities</p>
          </div>
          <p className="text-2xl font-bold text-red-400">{formatCurrency(liabilities.total)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <PiggyBank className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Equity</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(equity.total)}</p>
        </div>
      </div>

      {/* Assets Section */}
      <Section
        title="Assets"
        icon={Building2}
        items={assetItems}
        total={assets.total}
        colorClass="text-blue-400"
      />

      {/* Liabilities Section */}
      <Section
        title="Liabilities"
        icon={CreditCard}
        items={liabilityItems}
        total={liabilities.total}
        colorClass="text-red-400"
      />

      {/* Equity Section */}
      <Section
        title="Equity"
        icon={PiggyBank}
        items={equityItems}
        total={equity.total}
        colorClass="text-green-400"
      />

      {/* Accounting Equation */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Accounting Equation</h3>
        <div className="flex items-center justify-center gap-4 text-lg">
          <div className="text-center">
            <p className="text-slate-muted text-sm">Assets</p>
            <p className="font-mono font-bold text-blue-400">{formatCurrency(assets.total)}</p>
          </div>
          <span className="text-slate-muted">=</span>
          <div className="text-center">
            <p className="text-slate-muted text-sm">Liabilities</p>
            <p className="font-mono font-bold text-red-400">{formatCurrency(liabilities.total)}</p>
          </div>
          <span className="text-slate-muted">+</span>
          <div className="text-center">
            <p className="text-slate-muted text-sm">Equity</p>
            <p className="font-mono font-bold text-green-400">{formatCurrency(equity.total)}</p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-slate-border text-center">
          <p className="text-slate-muted text-sm">
            Difference: {' '}
            <span className={cn(
              'font-mono font-semibold',
              Math.abs(assets.total - (liabilities.total + equity.total)) < 1
                ? 'text-green-400'
                : 'text-red-400'
            )}>
              {formatCurrency(assets.total - (liabilities.total + equity.total))}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
