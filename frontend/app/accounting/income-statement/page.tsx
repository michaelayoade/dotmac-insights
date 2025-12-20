'use client';

import { useState } from 'react';
import { useAccountingIncomeStatement } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { AlertTriangle, TrendingUp, TrendingDown, Calendar, DollarSign, Minus, Equal } from 'lucide-react';
import PageSkeleton from '@/components/PageSkeleton';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

interface LineItemProps {
  name: string;
  amount: number;
  indent?: number;
  bold?: boolean;
  colorClass?: string;
}

function LineItem({ name, amount, indent = 0, bold, colorClass = 'text-white' }: LineItemProps) {
  return (
    <div className={cn(
      'flex justify-between items-center py-2',
      bold && 'font-semibold border-t border-slate-border pt-3 mt-2'
    )} style={{ paddingLeft: `${indent * 1.5}rem` }}>
      <span className={bold ? colorClass : 'text-slate-300'}>{name}</span>
      <span className={cn('font-mono', colorClass)}>
        {formatCurrency(amount)}
      </span>
    </div>
  );
}

export default function IncomeStatementPage() {
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const { data, isLoading, error } = useAccountingIncomeStatement({
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  });

  if (isLoading && !data) {
    return <PageSkeleton showHeader showStats statsCount={3} />;
  }

  const revenue = data?.revenue || { items: [], total: 0 };
  const cogs = data?.cost_of_goods_sold || { items: [], total: 0 };
  const operatingExpenses = data?.operating_expenses || { items: [], total: 0 };
  const otherIncome = data?.other_income || { items: [], total: 0 };
  const otherExpenses = data?.other_expenses || { items: [], total: 0 };

  const grossProfit = data?.gross_profit ?? (revenue.total - cogs.total);
  const operatingIncome = data?.operating_income ?? (grossProfit - operatingExpenses.total);
  const expensesTotal = cogs.total + operatingExpenses.total + otherExpenses.total;
  const netIncome = data?.net_income ?? (operatingIncome + otherIncome.total - otherExpenses.total);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load income statement</p>
        </div>
      )}
      {/* Header with date range */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Income Statement</h2>
          {data?.period && (
            <span className="text-slate-muted text-sm">
              {typeof data.period === 'string'
                ? data.period
                : (() => {
                  const period: any = data.period;
                  return `${period?.start_date || period?.start || ''} - ${period?.end_date || period?.end || ''}`;
                })()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              placeholder="Start Date"
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              placeholder="End Date"
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          {(startDate || endDate) && (
            <button
              onClick={() => { setStartDate(''); setEndDate(''); }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Revenue</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(revenue.total)}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <p className="text-red-400 text-sm">Total Expenses</p>
          </div>
          <p className="text-2xl font-bold text-red-400">{formatCurrency(expensesTotal)}</p>
        </div>
        <div className={cn(
          'border rounded-xl p-5',
          netIncome >= 0
            ? 'bg-teal-500/10 border-teal-500/30'
            : 'bg-orange-500/10 border-orange-500/30'
        )}>
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className={cn('w-5 h-5', netIncome >= 0 ? 'text-teal-400' : 'text-orange-400')} />
            <p className={cn('text-sm', netIncome >= 0 ? 'text-teal-400' : 'text-orange-400')}>Net Income</p>
          </div>
          <p className={cn('text-2xl font-bold', netIncome >= 0 ? 'text-teal-400' : 'text-orange-400')}>
            {formatCurrency(netIncome)}
          </p>
        </div>
      </div>

      {/* Income Statement Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Section */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <h3 className="text-lg font-semibold text-green-400">Revenue</h3>
          </div>
          <div className="space-y-1">
            {(revenue.items || []).map((item: any, index: number) => (
              <LineItem
                key={index}
                name={item.name}
                amount={item.amount}
                colorClass="text-green-400"
              />
            ))}
            <LineItem
              name="Total Revenue"
              amount={revenue.total}
              bold
              colorClass="text-green-400"
            />
          </div>
        </div>

        {/* Expenses Section */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <h3 className="text-lg font-semibold text-red-400">Expenses</h3>
          </div>
          <div className="space-y-1">
            {(cogs.items || []).map((item: any, index: number) => (
              <LineItem key={`cogs-${index}`} name={item.name} amount={item.amount} colorClass="text-orange-300" />
            ))}
            {cogs.total !== 0 && <LineItem name="Cost of Goods Sold" amount={cogs.total} bold colorClass="text-orange-300" />}
            {(operatingExpenses.items || []).map((item: any, index: number) => (
              <LineItem key={`op-${index}`} name={item.name} amount={item.amount} colorClass="text-red-400" />
            ))}
            {operatingExpenses.total !== 0 && (
              <LineItem name="Operating Expenses" amount={operatingExpenses.total} bold colorClass="text-red-400" />
            )}
            {(otherExpenses.items || []).map((item: any, index: number) => (
              <LineItem key={`otherexp-${index}`} name={item.name} amount={item.amount} colorClass="text-red-400" />
            ))}
            {otherExpenses.total !== 0 && (
              <LineItem name="Other Expenses" amount={otherExpenses.total} bold colorClass="text-red-400" />
            )}
            <LineItem
              name="Total Expenses"
              amount={expensesTotal}
              bold
              colorClass="text-red-400"
            />
          </div>
        </div>
      </div>

      {/* Net Income Calculation */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Net Income Calculation</h3>
        <div className="flex items-center justify-center gap-6 text-lg flex-wrap">
          <div className="text-center">
            <p className="text-slate-muted text-sm">Revenue</p>
            <p className="font-mono font-bold text-green-400">{formatCurrency(revenue.total)}</p>
          </div>
          <Minus className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Expenses</p>
            <p className="font-mono font-bold text-red-400">{formatCurrency(expensesTotal)}</p>
          </div>
          <Equal className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Net Income</p>
            <p className={cn(
              'font-mono font-bold text-xl',
              netIncome >= 0 ? 'text-teal-400' : 'text-orange-400'
            )}>
              {formatCurrency(netIncome)}
            </p>
          </div>
        </div>

        {/* Profit Margins */}
        {grossProfit !== 0 && (
          <div className="mt-6 pt-4 border-t border-slate-border">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-center">
              {grossProfit !== 0 && (
                <div>
                  <p className="text-slate-muted text-sm">Gross Profit</p>
                  <p className="font-mono font-semibold text-white">{formatCurrency(grossProfit)}</p>
                </div>
              )}
              {operatingIncome !== 0 && (
                <div>
                  <p className="text-slate-muted text-sm">Operating Income</p>
                  <p className="font-mono font-semibold text-white">{formatCurrency(operatingIncome)}</p>
                </div>
              )}
              {revenue.total > 0 && (
                <div>
                  <p className="text-slate-muted text-sm">Net Margin</p>
                  <p className={cn(
                    'font-mono font-semibold',
                    netIncome >= 0 ? 'text-green-400' : 'text-red-400'
                  )}>
                    {((netIncome / revenue.total) * 100).toFixed(1)}%
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
