'use client';

import { useState } from 'react';
import { useAccountingIncomeStatement } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  DollarSign,
  Minus,
  Equal,
  Download,
  BarChart2,
  ChevronDown,
  ChevronRight,
  Percent,
  Calculator,
  Banknote,
  Receipt,
} from 'lucide-react';
import { ErrorDisplay } from '@/components/insights/shared';
import PageSkeleton from '@/components/PageSkeleton';
import { PercentStatCard } from '@/components/StatCard';
import { Button } from '@/components/ui';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

function formatPercent(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0.0%';
  return `${value.toFixed(1)}%`;
}

interface LineItemProps {
  name: string;
  amount: number;
  indent?: number;
  bold?: boolean;
  colorClass?: string;
  pct?: number;
}

function LineItem({ name, amount, indent = 0, bold, colorClass = 'text-foreground', pct }: LineItemProps) {
  return (
    <div
      className={cn(
        'flex justify-between items-center py-2',
        bold && 'font-semibold border-t border-slate-border pt-3 mt-2'
      )}
      style={{ paddingLeft: `${indent * 1.5}rem` }}
    >
      <span className={bold ? colorClass : 'text-foreground-secondary'}>{name}</span>
      <div className="flex items-center gap-4">
        {pct !== undefined && (
          <span className="text-slate-muted text-sm w-16 text-right">{pct.toFixed(1)}%</span>
        )}
        <span className={cn('font-mono w-32 text-right', colorClass)}>{formatAccountingCurrency(amount)}</span>
      </div>
    </div>
  );
}

interface CollapsibleSectionProps {
  title: string;
  icon: React.ElementType;
  items: Array<{ account?: string; name?: string; amount: number; pct_of_revenue?: number }>;
  total: number;
  colorClass: string;
  defaultOpen?: boolean;
  showPct?: boolean;
}

function CollapsibleSection({
  title,
  icon: Icon,
  items,
  total,
  colorClass,
  defaultOpen = true,
  showPct,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <Button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={cn('w-5 h-5', colorClass)} />
          <h3 className={cn('text-lg font-semibold', colorClass)}>{title}</h3>
          <span className="text-slate-muted text-sm">({items.length} items)</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn('font-mono font-bold', colorClass)}>{formatAccountingCurrency(total)}</span>
          {isOpen ? (
            <ChevronDown className="w-5 h-5 text-slate-muted" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-muted" />
          )}
        </div>
      </Button>
      {isOpen && items.length > 0 && (
        <div className="px-4 pb-4 space-y-1">
          {items.map((item, index) => (
            <LineItem
              key={index}
              name={item.account || item.name || 'Unknown'}
              amount={item.amount}
              colorClass={colorClass}
              pct={showPct ? item.pct_of_revenue : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}


export default function IncomeStatementPage() {
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [compareStart, setCompareStart] = useState<string>('');
  const [compareEnd, setCompareEnd] = useState<string>('');
  const [showYtd, setShowYtd] = useState<boolean>(false);
  const [commonSize, setCommonSize] = useState<boolean>(false);
  const [basis, setBasis] = useState<string>('');

  const params = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    compare_start: compareStart || undefined,
    compare_end: compareEnd || undefined,
    show_ytd: showYtd || undefined,
    common_size: commonSize || undefined,
    basis: basis || undefined,
  };

  const { data, isLoading, error, mutate } = useAccountingIncomeStatement(params);

  const exportStatement = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/income-statement/export', { ...params, format });
    window.open(url, '_blank');
  };

  if (isLoading && !data) {
    return <PageSkeleton showHeader showStats statsCount={4} />;
  }

  // Extract IFRS structure data
  const currency = data?.currency || 'NGN';
  const revenue = data?.revenue || { accounts: [], total: 0 };
  const cogs = data?.cost_of_goods_sold || { accounts: [], total: 0 };
  const operatingExpenses = data?.operating_expenses || { accounts: [], total: 0 };
  const financeIncome = data?.finance_income || { accounts: [], total: 0 };
  const financeCosts = data?.finance_costs || { accounts: [], total: 0 };
  const taxExpense = data?.tax_expense || { accounts: [], total: 0 };

  // Key IFRS metrics
  const grossProfit = data?.gross_profit ?? revenue.total - cogs.total;
  const operatingIncome = data?.operating_income ?? data?.ebit ?? grossProfit - operatingExpenses.total;
  const ebitda = data?.ebitda ?? operatingIncome;
  const netFinance = data?.net_finance_income ?? financeIncome.total - financeCosts.total;
  const profitBeforeTax = data?.profit_before_tax ?? data?.ebt ?? operatingIncome + netFinance;
  const netIncome = data?.net_income ?? data?.profit_after_tax ?? profitBeforeTax - taxExpense.total;

  // Margins
  const grossMargin = data?.gross_margin ?? (revenue.total > 0 ? (grossProfit / revenue.total) * 100 : 0);
  const operatingMargin = data?.operating_margin ?? (revenue.total > 0 ? (operatingIncome / revenue.total) * 100 : 0);
  const ebitdaMargin = data?.ebitda_margin ?? (revenue.total > 0 ? (ebitda / revenue.total) * 100 : 0);
  const netMargin = data?.net_margin ?? (revenue.total > 0 ? (netIncome / revenue.total) * 100 : 0);
  const effectiveTaxRate = data?.effective_tax_rate ?? (profitBeforeTax > 0 ? (taxExpense.total / profitBeforeTax) * 100 : 0);

  const totalExpenses = cogs.total + operatingExpenses.total + financeCosts.total + taxExpense.total;

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load income statement."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-foreground">Statement of Profit or Loss</h2>
          {data?.period && (
            <span className="text-slate-muted text-sm">
              {data.period.start_date} to {data.period.end_date}
            </span>
          )}
          {currency && <span className="text-slate-muted text-xs ml-2">({currency})</span>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              placeholder="Start Date"
              className="input-field"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              placeholder="End Date"
              className="input-field"
            />
          </div>
          <label className="flex items-center gap-2 text-slate-muted text-sm">
            <input type="checkbox" checked={commonSize} onChange={(e) => setCommonSize(e.target.checked)} />
            Common size
          </label>
          <select
            value={basis}
            onChange={(e) => setBasis(e.target.value)}
            className="input-field"
          >
            <option value="">Basis</option>
            <option value="accrual">Accrual</option>
            <option value="cash">Cash</option>
          </select>
          {(startDate || endDate || commonSize || basis) && (
            <Button
              onClick={() => {
                setStartDate('');
                setEndDate('');
                setCompareStart('');
                setCompareEnd('');
                setShowYtd(false);
                setCommonSize(false);
                setBasis('');
              }}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear
            </Button>
          )}
          <div className="flex gap-2">
            <Button
              onClick={() => exportStatement('csv')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
            >
              <Download className="w-4 h-4" />
              CSV
            </Button>
            <Button
              onClick={() => exportStatement('pdf')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
            >
              <BarChart2 className="w-4 h-4" />
              PDF
            </Button>
          </div>
        </div>
      </div>

      {/* Key Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Revenue</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatAccountingCurrency(revenue.total, currency)}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Calculator className="w-5 h-5 text-orange-400" />
            <p className="text-orange-400 text-sm">Gross Profit</p>
          </div>
          <p className="text-2xl font-bold text-orange-400">{formatAccountingCurrency(grossProfit, currency)}</p>
          <p className="text-orange-300 text-sm mt-1">{formatPercent(grossMargin)} margin</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <BarChart2 className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">EBITDA</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatAccountingCurrency(ebitda, currency)}</p>
          <p className="text-blue-300 text-sm mt-1">{formatPercent(ebitdaMargin)} margin</p>
        </div>
        <div
          className={cn(
            'border rounded-xl p-5',
            netIncome >= 0 ? 'bg-teal-500/10 border-teal-500/30' : 'bg-red-500/10 border-red-500/30'
          )}
        >
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className={cn('w-5 h-5', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')} />
            <p className={cn('text-sm', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')}>Net Income</p>
          </div>
          <p className={cn('text-2xl font-bold', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')}>
            {formatAccountingCurrency(netIncome, currency)}
          </p>
          <p className={cn('text-sm mt-1', netIncome >= 0 ? 'text-teal-300' : 'text-red-300')}>
            {formatPercent(netMargin)} margin
          </p>
        </div>
      </div>

      {/* IFRS P&L Structure */}
      <div className="space-y-4">
        {/* Revenue */}
        <CollapsibleSection
          title="Revenue"
          icon={TrendingUp}
          items={revenue.accounts || []}
          total={revenue.total}
          colorClass="text-green-400"
          showPct={commonSize}
        />

        {/* Cost of Goods Sold */}
        {cogs.total !== 0 && (
          <CollapsibleSection
            title="Cost of Goods Sold"
            icon={Receipt}
            items={cogs.accounts || []}
            total={cogs.total}
            colorClass="text-orange-400"
            showPct={commonSize}
          />
        )}

        {/* Gross Profit Line */}
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Calculator className="w-5 h-5 text-orange-400" />
              <span className="text-foreground font-semibold">Gross Profit</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-slate-muted text-sm">{formatPercent(grossMargin)}</span>
              <span className="font-mono font-bold text-orange-400">{formatAccountingCurrency(grossProfit, currency)}</span>
            </div>
          </div>
        </div>

        {/* Operating Expenses */}
        <CollapsibleSection
          title="Operating Expenses"
          icon={TrendingDown}
          items={operatingExpenses.accounts || []}
          total={operatingExpenses.total}
          colorClass="text-red-400"
          showPct={commonSize}
        />

        {/* Operating Income / EBIT Line */}
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-blue-400" />
              <span className="text-foreground font-semibold">Operating Income (EBIT)</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-slate-muted text-sm">{formatPercent(operatingMargin)}</span>
              <span className="font-mono font-bold text-blue-400">{formatAccountingCurrency(operatingIncome, currency)}</span>
            </div>
          </div>
          {data?.depreciation_amortization !== undefined && data.depreciation_amortization > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-border flex justify-between items-center text-sm">
              <span className="text-slate-muted">EBITDA (add back D&A: {formatAccountingCurrency(data.depreciation_amortization)})</span>
              <span className="font-mono text-blue-300">{formatAccountingCurrency(ebitda, currency)}</span>
            </div>
          )}
        </div>

        {/* Finance Income */}
        {financeIncome.total !== 0 && (
          <CollapsibleSection
            title="Finance Income"
            icon={Banknote}
            items={financeIncome.accounts || []}
            total={financeIncome.total}
            colorClass="text-green-300"
            defaultOpen={false}
            showPct={commonSize}
          />
        )}

        {/* Finance Costs */}
        {financeCosts.total !== 0 && (
          <CollapsibleSection
            title="Finance Costs"
            icon={Percent}
            items={financeCosts.accounts || []}
            total={financeCosts.total}
            colorClass="text-red-300"
            defaultOpen={false}
            showPct={commonSize}
          />
        )}

        {/* Profit Before Tax Line */}
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Calculator className="w-5 h-5 text-purple-400" />
              <span className="text-foreground font-semibold">Profit Before Tax (EBT)</span>
            </div>
            <span className="font-mono font-bold text-purple-400">{formatAccountingCurrency(profitBeforeTax, currency)}</span>
          </div>
        </div>

        {/* Tax Expense */}
        {taxExpense.total !== 0 && (
          <CollapsibleSection
            title="Income Tax Expense"
            icon={Receipt}
            items={taxExpense.accounts || []}
            total={taxExpense.total}
            colorClass="text-amber-400"
            defaultOpen={false}
            showPct={commonSize}
          />
        )}

        {/* Net Income Line */}
        <div
          className={cn(
            'border rounded-xl p-4',
            netIncome >= 0 ? 'bg-teal-500/10 border-teal-500/30' : 'bg-red-500/10 border-red-500/30'
          )}
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <DollarSign className={cn('w-5 h-5', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')} />
              <span className={cn('font-semibold', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')}>
                Profit for the Period
              </span>
            </div>
            <div className="flex items-center gap-4">
              <span className={cn('text-sm', netIncome >= 0 ? 'text-teal-300' : 'text-red-300')}>
                {formatPercent(netMargin)}
              </span>
              <span className={cn('font-mono font-bold text-xl', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')}>
                {formatAccountingCurrency(netIncome, currency)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Profitability Summary */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
          <Percent className="w-5 h-5 text-teal-electric" />
          Profitability Metrics (IAS 1)
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <PercentStatCard title="Gross Margin" value={formatAccountingCurrency(grossProfit)} pct={grossMargin} colorClass="text-orange-400" />
          <PercentStatCard title="Operating Margin" value={formatAccountingCurrency(operatingIncome)} pct={operatingMargin} colorClass="text-blue-400" />
          <PercentStatCard title="EBITDA Margin" value={formatAccountingCurrency(ebitda)} pct={ebitdaMargin} colorClass="text-blue-300" />
          <PercentStatCard title="Net Margin" value={formatAccountingCurrency(netIncome)} pct={netMargin} colorClass="text-teal-400" />
          <PercentStatCard title="Effective Tax Rate" value={formatPercent(effectiveTaxRate)} icon={Receipt} colorClass="text-amber-400" />
        </div>
      </div>

      {/* P&L Summary */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
        <h3 className="text-foreground font-semibold mb-4">P&L Waterfall</h3>
        <div className="flex items-center justify-center gap-4 text-lg flex-wrap">
          <div className="text-center">
            <p className="text-slate-muted text-sm">Revenue</p>
            <p className="font-mono font-bold text-green-400">{formatAccountingCurrency(revenue.total, currency)}</p>
          </div>
          <Minus className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">COGS</p>
            <p className="font-mono font-bold text-orange-400">{formatAccountingCurrency(cogs.total, currency)}</p>
          </div>
          <Equal className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Gross Profit</p>
            <p className="font-mono font-bold text-orange-300">{formatAccountingCurrency(grossProfit, currency)}</p>
          </div>
          <Minus className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">OpEx</p>
            <p className="font-mono font-bold text-red-400">{formatAccountingCurrency(operatingExpenses.total, currency)}</p>
          </div>
          <Equal className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Operating</p>
            <p className="font-mono font-bold text-blue-400">{formatAccountingCurrency(operatingIncome, currency)}</p>
          </div>
        </div>
        <div className="flex items-center justify-center gap-4 text-lg flex-wrap mt-4 pt-4 border-t border-slate-border">
          <div className="text-center">
            <p className="text-slate-muted text-sm">Operating</p>
            <p className="font-mono font-bold text-blue-400">{formatAccountingCurrency(operatingIncome, currency)}</p>
          </div>
          <span className="text-slate-muted">±</span>
          <div className="text-center">
            <p className="text-slate-muted text-sm">Net Finance</p>
            <p className={cn('font-mono font-bold', netFinance >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatAccountingCurrency(netFinance, currency)}
            </p>
          </div>
          <Minus className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Tax</p>
            <p className="font-mono font-bold text-amber-400">{formatAccountingCurrency(taxExpense.total, currency)}</p>
          </div>
          <Equal className="w-5 h-5 text-slate-muted" />
          <div className="text-center">
            <p className="text-slate-muted text-sm">Net Income</p>
            <p className={cn('font-mono font-bold text-xl', netIncome >= 0 ? 'text-teal-400' : 'text-red-400')}>
              {formatAccountingCurrency(netIncome, currency)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
