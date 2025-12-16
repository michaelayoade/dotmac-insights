'use client';

import { useState } from 'react';
import { useAccountingEquityStatement } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import {
  FileSpreadsheet,
  Calendar,
  Download,
  BarChart2,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  PiggyBank,
  Coins,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Layers,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

interface MovementRowProps {
  label: string;
  value: number;
  currency: string;
  isSubItem?: boolean;
  isTotal?: boolean;
  colorClass?: string;
}

function MovementRow({ label, value, currency, isSubItem, isTotal, colorClass }: MovementRowProps) {
  return (
    <div
      className={cn(
        'flex justify-between items-center py-2',
        isTotal ? 'border-t-2 border-slate-border font-bold' : 'border-b border-slate-border/50',
        isSubItem && 'pl-4'
      )}
    >
      <span className={cn('text-white', isSubItem && 'text-slate-muted')}>{label}</span>
      <span
        className={cn(
          'font-mono w-36 text-right',
          colorClass || (value >= 0 ? 'text-green-400' : 'text-red-400'),
          isTotal && 'text-lg'
        )}
      >
        {value >= 0 ? '' : '('}
        {formatCurrency(Math.abs(value), currency)}
        {value < 0 ? ')' : ''}
      </span>
    </div>
  );
}

interface ComponentCardProps {
  component: {
    component: string;
    opening_balance: number;
    profit_loss: number;
    other_comprehensive_income: number;
    dividends: number;
    share_transactions: number;
    transfers: number;
    other_movements: number;
    closing_balance: number;
    accounts?: Record<string, number>;
  };
  currency: string;
}

function ComponentCard({ component, currency }: ComponentCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const netChange = component.closing_balance - component.opening_balance;
  const hasMovements =
    component.profit_loss !== 0 ||
    component.other_comprehensive_income !== 0 ||
    component.dividends !== 0 ||
    component.share_transactions !== 0 ||
    component.transfers !== 0 ||
    component.other_movements !== 0;

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated transition-colors"
      >
        <div className="flex items-center gap-3">
          <Coins className="w-5 h-5 text-teal-electric" />
          <div className="text-left">
            <h4 className="font-semibold text-white">{component.component}</h4>
            <p className="text-sm text-slate-muted">
              {formatCurrency(component.opening_balance, currency)} → {formatCurrency(component.closing_balance, currency)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className={cn('font-mono font-bold', netChange >= 0 ? 'text-green-400' : 'text-red-400')}>
              {netChange >= 0 ? '+' : ''}{formatCurrency(netChange, currency)}
            </span>
          </div>
          {isOpen ? (
            <ChevronDown className="w-5 h-5 text-slate-muted" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-muted" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-2">
          <MovementRow
            label="Opening Balance"
            value={component.opening_balance}
            currency={currency}
            colorClass="text-slate-muted"
          />

          {hasMovements && (
            <div className="py-2">
              <p className="text-xs text-slate-muted uppercase tracking-wide mb-2">Movements</p>
              {component.profit_loss !== 0 && (
                <MovementRow label="Profit/(Loss) for the period" value={component.profit_loss} currency={currency} isSubItem />
              )}
              {component.other_comprehensive_income !== 0 && (
                <MovementRow label="Other Comprehensive Income" value={component.other_comprehensive_income} currency={currency} isSubItem />
              )}
              {component.dividends !== 0 && (
                <MovementRow label="Dividends" value={component.dividends} currency={currency} isSubItem />
              )}
              {component.share_transactions !== 0 && (
                <MovementRow label="Share Transactions" value={component.share_transactions} currency={currency} isSubItem />
              )}
              {component.transfers !== 0 && (
                <MovementRow label="Transfers" value={component.transfers} currency={currency} isSubItem />
              )}
              {component.other_movements !== 0 && (
                <MovementRow label="Other Movements" value={component.other_movements} currency={currency} isSubItem />
              )}
            </div>
          )}

          <MovementRow
            label="Closing Balance"
            value={component.closing_balance}
            currency={currency}
            isTotal
            colorClass="text-teal-electric"
          />

          {/* Account breakdown if available */}
          {component.accounts && Object.keys(component.accounts).length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-border">
              <p className="text-xs text-slate-muted uppercase tracking-wide mb-2">Account Breakdown</p>
              {Object.entries(component.accounts).map(([account, balance]) => (
                <div key={account} className="flex justify-between py-1 text-sm">
                  <span className="text-slate-muted">{account}</span>
                  <span className="font-mono text-white">{formatCurrency(balance, currency)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function EquityStatementPage() {
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const params = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  };

  const { data, isLoading, error, mutate } = useAccountingEquityStatement(params);

  const exportStatement = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/equity-statement/export', { ...params, format });
    window.open(url, '_blank');
  };

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load statement of changes in equity."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  const currency = data?.currency || 'NGN';
  const summary = data?.summary;
  const reconciliation = data?.reconciliation;
  const components = data?.components || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Statement of Changes in Equity</h2>
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
              className="input-field"
              placeholder="Start"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="input-field"
              placeholder="End"
            />
          </div>
          {(startDate || endDate) && (
            <button
              onClick={() => {
                setStartDate('');
                setEndDate('');
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear
            </button>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => exportStatement('csv')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
            >
              <Download className="w-4 h-4" />
              CSV
            </button>
            <button
              onClick={() => exportStatement('pdf')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
            >
              <BarChart2 className="w-4 h-4" />
              PDF
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <PiggyBank className="w-5 h-5 text-slate-muted" />
              <p className="text-slate-muted text-sm">Opening Equity</p>
            </div>
            <p className="text-2xl font-bold text-white">{formatCurrency(summary.total_opening_equity, currency)}</p>
          </div>

          <div className={cn(
            'border rounded-xl p-5',
            summary.total_comprehensive_income >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
          )}>
            <div className="flex items-center gap-2 mb-2">
              {summary.total_comprehensive_income >= 0 ? (
                <TrendingUp className="w-5 h-5 text-green-400" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-400" />
              )}
              <p className={cn('text-sm', summary.total_comprehensive_income >= 0 ? 'text-green-400' : 'text-red-400')}>
                Total Comprehensive Income
              </p>
            </div>
            <p className={cn('text-2xl font-bold', summary.total_comprehensive_income >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(summary.total_comprehensive_income, currency)}
            </p>
            <div className="mt-2 text-xs text-slate-muted">
              <span>Profit: {formatCurrency(summary.profit_for_period, currency)}</span>
              {summary.other_comprehensive_income !== 0 && (
                <span className="ml-2">| OCI: {formatCurrency(summary.other_comprehensive_income, currency)}</span>
              )}
            </div>
          </div>

          <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="w-5 h-5 text-purple-400" />
              <p className="text-purple-400 text-sm">Owner Transactions</p>
            </div>
            <p className="text-2xl font-bold text-purple-400">
              {formatCurrency(
                (summary.transactions_with_owners?.dividends_paid || 0) +
                (summary.transactions_with_owners?.share_issues || 0) +
                (summary.transactions_with_owners?.treasury_share_transactions || 0),
                currency
              )}
            </p>
            <div className="mt-2 text-xs text-slate-muted space-y-1">
              {summary.transactions_with_owners?.dividends_paid !== 0 && (
                <div>Dividends: {formatCurrency(summary.transactions_with_owners.dividends_paid, currency)}</div>
              )}
              {summary.transactions_with_owners?.share_issues !== 0 && (
                <div>Share Issues: {formatCurrency(summary.transactions_with_owners.share_issues, currency)}</div>
              )}
            </div>
          </div>

          <div className="bg-teal-500/10 border border-teal-500/30 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <PiggyBank className="w-5 h-5 text-teal-electric" />
              <p className="text-teal-electric text-sm">Closing Equity</p>
            </div>
            <p className="text-2xl font-bold text-teal-electric">{formatCurrency(summary.total_closing_equity, currency)}</p>
            <div className="mt-2 text-xs">
              <span className={cn(summary.change_in_equity >= 0 ? 'text-green-400' : 'text-red-400')}>
                {summary.change_in_equity >= 0 ? '+' : ''}{formatCurrency(summary.change_in_equity, currency)} change
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Equity Flow Visualization */}
      {summary && (
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">Equity Flow (IAS 1)</h3>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <div className="text-center">
              <p className="text-slate-muted text-xs mb-1">Opening Equity</p>
              <p className="font-mono font-bold text-white">{formatCurrency(summary.total_opening_equity, currency)}</p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-muted" />
            <div className="text-center">
              <p className="text-slate-muted text-xs mb-1">+ Comprehensive Income</p>
              <p className={cn('font-mono font-bold', summary.total_comprehensive_income >= 0 ? 'text-green-400' : 'text-red-400')}>
                {summary.total_comprehensive_income >= 0 ? '+' : ''}{formatCurrency(summary.total_comprehensive_income, currency)}
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-muted" />
            <div className="text-center">
              <p className="text-slate-muted text-xs mb-1">+/- Owner Transactions</p>
              <p className="font-mono font-bold text-purple-400">
                {formatCurrency(
                  (summary.transactions_with_owners?.dividends_paid || 0) +
                  (summary.transactions_with_owners?.share_issues || 0) +
                  (summary.transactions_with_owners?.treasury_share_transactions || 0),
                  currency
                )}
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-muted" />
            <div className="text-center">
              <p className="text-slate-muted text-xs mb-1">= Closing Equity</p>
              <p className="font-mono font-bold text-teal-electric">{formatCurrency(summary.total_closing_equity, currency)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Equity Components */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Coins className="w-5 h-5 text-teal-electric" />
          Equity Components
        </h3>

        {components.length === 0 ? (
          <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
            <p className="text-slate-muted">No equity components found for this period</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {components.map((component, idx) => (
              <ComponentCard key={idx} component={component} currency={currency} />
            ))}
          </div>
        )}
      </div>

      {/* Reconciliation Section */}
      {reconciliation && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-teal-electric" />
              <h3 className="font-semibold text-white">Equity Reconciliation</h3>
            </div>
            {reconciliation.is_reconciled ? (
              <span className="flex items-center gap-1 text-green-400 text-sm">
                <CheckCircle2 className="w-4 h-4" />
                Reconciled
              </span>
            ) : (
              <span className="flex items-center gap-1 text-red-400 text-sm">
                <XCircle className="w-4 h-4" />
                Unreconciled
              </span>
            )}
          </div>
          <div className="p-4 space-y-1">
            <div className="flex justify-between py-2 border-b border-slate-border/50">
              <span className="text-white">Opening Equity</span>
              <span className="font-mono text-white">{formatCurrency(reconciliation.opening_equity, currency)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-border/50">
              <span className="text-slate-muted pl-4">Add: Profit for the period</span>
              <span className="font-mono text-green-400">+{formatCurrency(reconciliation.add_profit_for_period, currency)}</span>
            </div>
            {reconciliation.add_other_comprehensive_income !== 0 && (
              <div className="flex justify-between py-2 border-b border-slate-border/50">
                <span className="text-slate-muted pl-4">Add: Other Comprehensive Income</span>
                <span className={cn('font-mono', reconciliation.add_other_comprehensive_income >= 0 ? 'text-green-400' : 'text-red-400')}>
                  {reconciliation.add_other_comprehensive_income >= 0 ? '+' : ''}{formatCurrency(reconciliation.add_other_comprehensive_income, currency)}
                </span>
              </div>
            )}
            {reconciliation.less_dividends !== 0 && (
              <div className="flex justify-between py-2 border-b border-slate-border/50">
                <span className="text-slate-muted pl-4">Less: Dividends Paid</span>
                <span className="font-mono text-red-400">{formatCurrency(reconciliation.less_dividends, currency)}</span>
              </div>
            )}
            {reconciliation.add_share_issues !== 0 && (
              <div className="flex justify-between py-2 border-b border-slate-border/50">
                <span className="text-slate-muted pl-4">Add: Share Issues</span>
                <span className="font-mono text-green-400">+{formatCurrency(reconciliation.add_share_issues, currency)}</span>
              </div>
            )}
            {reconciliation.less_treasury_shares !== 0 && (
              <div className="flex justify-between py-2 border-b border-slate-border/50">
                <span className="text-slate-muted pl-4">Less: Treasury Share Transactions</span>
                <span className="font-mono text-red-400">{formatCurrency(reconciliation.less_treasury_shares, currency)}</span>
              </div>
            )}
            {reconciliation.other_movements !== 0 && (
              <div className="flex justify-between py-2 border-b border-slate-border/50">
                <span className="text-slate-muted pl-4">Other Movements</span>
                <span className={cn('font-mono', reconciliation.other_movements >= 0 ? 'text-green-400' : 'text-red-400')}>
                  {reconciliation.other_movements >= 0 ? '+' : ''}{formatCurrency(reconciliation.other_movements, currency)}
                </span>
              </div>
            )}
            <div className="flex justify-between py-3 border-t-2 border-slate-border font-bold">
              <span className="text-white">Closing Equity</span>
              <span className="font-mono text-lg text-teal-electric">{formatCurrency(reconciliation.closing_equity, currency)}</span>
            </div>
          </div>
        </div>
      )}

      {/* IAS 1 Note */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-4">
        <p className="text-slate-muted text-sm">
          <strong className="text-white">IAS 1 Disclosure:</strong> This statement presents changes in equity components
          including share capital, share premium, retained earnings, and reserves. It reconciles opening and closing
          balances for each equity component, showing comprehensive income and transactions with owners in their capacity
          as owners (dividends, share issues, treasury shares).
        </p>
      </div>
    </div>
  );
}
