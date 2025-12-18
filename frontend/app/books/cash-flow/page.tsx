'use client';

import { useState } from 'react';
import { useAccountingCashFlow } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  Calendar,
  Wallet,
  TrendingUp,
  TrendingDown,
  Building2,
  Landmark,
  Banknote,
  ArrowUpRight,
  ArrowDownRight,
  Info,
  ChevronDown,
  ChevronRight,
  Receipt,
  DollarSign,
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

interface CashFlowLineProps {
  label: string;
  amount: number;
  indent?: number;
  bold?: boolean;
  colorClass?: string;
}

function CashFlowLine({ label, amount, indent = 0, bold, colorClass }: CashFlowLineProps) {
  const color = colorClass || (amount >= 0 ? 'text-green-400' : 'text-red-400');
  return (
    <div
      className={cn('flex justify-between items-center py-2 border-b border-slate-border/30', bold && 'font-semibold')}
      style={{ paddingLeft: `${indent * 1.5}rem` }}
    >
      <span className="text-slate-300">{label}</span>
      <span className={cn('font-mono', color)}>{formatCurrency(amount)}</span>
    </div>
  );
}

interface CollapsibleActivityProps {
  title: string;
  icon: React.ElementType;
  net: number;
  items: { label: string; amount: number }[];
  colorClass: string;
  defaultOpen?: boolean;
}

function CollapsibleActivity({ title, icon: Icon, net, items, colorClass, defaultOpen = true }: CollapsibleActivityProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={cn('w-5 h-5', colorClass)} />
          <h3 className={cn('text-lg font-semibold', colorClass)}>{title}</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn('font-mono font-bold', net >= 0 ? 'text-green-400' : 'text-red-400')}>
            {formatCurrency(net)}
          </span>
          {isOpen ? <ChevronDown className="w-5 h-5 text-slate-muted" /> : <ChevronRight className="w-5 h-5 text-slate-muted" />}
        </div>
      </button>
      {isOpen && items.length > 0 && (
        <div className="px-4 pb-4 space-y-1">
          {items.map((item, index) => (
            <CashFlowLine key={index} label={item.label} amount={item.amount} indent={1} />
          ))}
          <CashFlowLine label={`Net ${title}`} amount={net} bold colorClass={colorClass} />
        </div>
      )}
    </div>
  );
}

export default function CashFlowPage() {
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [fiscalYear, setFiscalYear] = useState<string>('');

  const params = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    fiscal_year: fiscalYear || undefined,
  };

  const { data, isLoading, error, mutate } = useAccountingCashFlow(params);

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load cash flow statement."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  const currency = data?.currency || 'NGN';
  const openingCash = data?.opening_cash || 0;
  const closingCash = data?.closing_cash || 0;
  const netChange = data?.net_change_in_cash || 0;

  // Operating Activities
  const operating = data?.operating_activities || { net: 0 };
  const operatingItems = [
    { label: 'Net Income', amount: operating.net_income || 0 },
    ...(operating.adjustments?.depreciation_amortization
      ? [{ label: 'Add: Depreciation & Amortization', amount: operating.adjustments.depreciation_amortization }]
      : []),
    ...(operating.working_capital_changes
      ? [
          { label: 'Change in Accounts Receivable', amount: operating.working_capital_changes.accounts_receivable || 0 },
          { label: 'Change in Inventory', amount: operating.working_capital_changes.inventory || 0 },
          { label: 'Change in Prepaid Expenses', amount: operating.working_capital_changes.prepaid_expenses || 0 },
          { label: 'Change in Accounts Payable', amount: operating.working_capital_changes.accounts_payable || 0 },
          { label: 'Change in Accrued Liabilities', amount: operating.working_capital_changes.accrued_liabilities || 0 },
        ]
      : []),
    ...(operating.items || []).map((item: any) => ({ label: item.description, amount: item.amount })),
  ].filter((item) => item.amount !== 0);

  // Investing Activities
  const investing = data?.investing_activities || { net: 0 };
  const investingItems = [
    ...(investing.fixed_asset_purchases ? [{ label: 'Purchase of Fixed Assets', amount: -Math.abs(investing.fixed_asset_purchases) }] : []),
    ...(investing.fixed_asset_sales ? [{ label: 'Sale of Fixed Assets', amount: Math.abs(investing.fixed_asset_sales) }] : []),
    ...(investing.investments ? [{ label: 'Investments', amount: investing.investments }] : []),
    ...(investing.items || []).map((item: any) => ({ label: item.description, amount: item.amount })),
  ].filter((item) => item.amount !== 0);

  // Financing Activities
  const financing = data?.financing_activities || { net: 0 };
  const financingItems = [
    ...(financing.debt_proceeds ? [{ label: 'Proceeds from Borrowings', amount: financing.debt_proceeds }] : []),
    ...(financing.debt_repayments ? [{ label: 'Repayment of Borrowings', amount: -Math.abs(financing.debt_repayments) }] : []),
    ...(financing.equity_proceeds ? [{ label: 'Proceeds from Share Issue', amount: financing.equity_proceeds }] : []),
    ...(financing.dividends_paid ? [{ label: 'Dividends Paid', amount: -Math.abs(financing.dividends_paid) }] : []),
    ...(financing.items || []).map((item: any) => ({ label: item.description, amount: item.amount })),
  ].filter((item) => item.amount !== 0);

  // IAS 7 Supplementary Disclosures
  const disclosures = data?.supplementary_disclosures;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Statement of Cash Flows (IAS 7)</h2>
          {data?.period && (
            <span className="text-slate-muted text-sm">
              {data.period.start_date} to {data.period.end_date}
            </span>
          )}
          {data?.method && (
            <span className="text-slate-muted text-xs ml-2 px-2 py-1 bg-slate-elevated rounded">
              {data.method} method
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="input-field"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="input-field"
            />
          </div>
          {(startDate || endDate) && (
            <button
              onClick={() => {
                setStartDate('');
                setEndDate('');
                setFiscalYear('');
              }}
              className="text-slate-muted text-sm hover:text-white"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Opening Cash</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatCurrency(openingCash, currency)}</p>
        </div>
        <div className={cn('border rounded-xl p-5', netChange >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30')}>
          <div className="flex items-center gap-2 mb-2">
            {netChange >= 0 ? (
              <ArrowUpRight className="w-5 h-5 text-green-400" />
            ) : (
              <ArrowDownRight className="w-5 h-5 text-red-400" />
            )}
            <p className={cn('text-sm', netChange >= 0 ? 'text-green-400' : 'text-red-400')}>Net Change</p>
          </div>
          <p className={cn('text-2xl font-bold', netChange >= 0 ? 'text-green-400' : 'text-red-400')}>
            {formatCurrency(netChange, currency)}
          </p>
        </div>
        <div className="bg-teal-500/10 border border-teal-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-teal-400" />
            <p className="text-teal-400 text-sm">Closing Cash</p>
          </div>
          <p className="text-2xl font-bold text-teal-400">{formatCurrency(closingCash, currency)}</p>
        </div>
        <div
          className={cn(
            'border rounded-xl p-5',
            data?.is_reconciled ? 'bg-green-500/10 border-green-500/30' : 'bg-yellow-500/10 border-yellow-500/30'
          )}
        >
          <div className="flex items-center gap-2 mb-2">
            <Info className={cn('w-5 h-5', data?.is_reconciled ? 'text-green-400' : 'text-yellow-400')} />
            <p className={cn('text-sm', data?.is_reconciled ? 'text-green-400' : 'text-yellow-400')}>Reconciliation</p>
          </div>
          <p className={cn('text-lg font-bold', data?.is_reconciled ? 'text-green-400' : 'text-yellow-400')}>
            {data?.is_reconciled ? 'Reconciled' : `Diff: ${formatCurrency(data?.reconciliation_difference || 0)}`}
          </p>
        </div>
      </div>

      {/* Cash Flow Activities */}
      <div className="space-y-4">
        <CollapsibleActivity
          title="Operating Activities"
          icon={TrendingUp}
          net={operating.net}
          items={operatingItems}
          colorClass="text-green-400"
        />

        <CollapsibleActivity
          title="Investing Activities"
          icon={Building2}
          net={investing.net}
          items={investingItems}
          colorClass="text-blue-400"
        />

        <CollapsibleActivity
          title="Financing Activities"
          icon={Landmark}
          net={financing.net}
          items={financingItems}
          colorClass="text-purple-400"
        />
      </div>

      {/* Cash Flow Summary */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Cash Flow Summary</h3>
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-slate-border">
            <span className="text-slate-muted">Opening Cash Balance</span>
            <span className="font-mono text-blue-400">{formatCurrency(openingCash, currency)}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-slate-border">
            <span className="text-slate-muted">Net Cash from Operating Activities</span>
            <span className={cn('font-mono', operating.net >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(operating.net, currency)}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-slate-border">
            <span className="text-slate-muted">Net Cash from Investing Activities</span>
            <span className={cn('font-mono', investing.net >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(investing.net, currency)}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-slate-border">
            <span className="text-slate-muted">Net Cash from Financing Activities</span>
            <span className={cn('font-mono', financing.net >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(financing.net, currency)}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-slate-border font-semibold">
            <span className="text-white">Net Change in Cash</span>
            <span className={cn('font-mono', netChange >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(netChange, currency)}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 font-semibold text-lg">
            <span className="text-teal-400">Closing Cash Balance</span>
            <span className="font-mono text-teal-400">{formatCurrency(closingCash, currency)}</span>
          </div>
        </div>
      </div>

      {/* IAS 7 Supplementary Disclosures */}
      {disclosures && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Receipt className="w-5 h-5 text-teal-electric" />
            IAS 7 Supplementary Disclosures
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-slate-elevated rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Banknote className="w-4 h-4 text-red-400" />
                <span className="text-slate-muted text-sm">Interest Paid</span>
              </div>
              <p className="font-mono text-white">{formatCurrency(disclosures.interest_paid, currency)}</p>
              <p className="text-slate-muted text-xs mt-1">
                Classified as: {disclosures.classification_policy?.interest_paid || 'operating'}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Banknote className="w-4 h-4 text-green-400" />
                <span className="text-slate-muted text-sm">Interest Received</span>
              </div>
              <p className="font-mono text-white">{formatCurrency(disclosures.interest_received, currency)}</p>
              <p className="text-slate-muted text-xs mt-1">
                Classified as: {disclosures.classification_policy?.interest_received || 'operating'}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-purple-400" />
                <span className="text-slate-muted text-sm">Dividends Paid</span>
              </div>
              <p className="font-mono text-white">{formatCurrency(disclosures.dividends_paid, currency)}</p>
              <p className="text-slate-muted text-xs mt-1">
                Classified as: {disclosures.classification_policy?.dividends_paid || 'financing'}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-green-400" />
                <span className="text-slate-muted text-sm">Dividends Received</span>
              </div>
              <p className="font-mono text-white">{formatCurrency(disclosures.dividends_received, currency)}</p>
              <p className="text-slate-muted text-xs mt-1">
                Classified as: {disclosures.classification_policy?.dividends_received || 'operating'}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Receipt className="w-4 h-4 text-amber-400" />
                <span className="text-slate-muted text-sm">Income Taxes Paid</span>
              </div>
              <p className="font-mono text-white">{formatCurrency(disclosures.income_taxes_paid, currency)}</p>
              <p className="text-slate-muted text-xs mt-1">
                Classified as: {disclosures.classification_policy?.taxes_paid || 'operating'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Non-Cash Transactions Note */}
      {data?.non_cash_transactions && (
        <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-2 flex items-center gap-2">
            <Info className="w-5 h-5 text-slate-muted" />
            Non-Cash Transactions (IAS 7.43)
          </h3>
          <p className="text-slate-muted text-sm mb-3">{data.non_cash_transactions.note}</p>
          <ul className="text-slate-muted text-sm list-disc list-inside space-y-1">
            {data.non_cash_transactions.examples.map((example: string, i: number) => (
              <li key={i}>{example}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Bank Summary */}
      {data?.bank_summary && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">Bank Transaction Summary</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <ArrowUpRight className="w-4 h-4 text-green-400" />
                <span className="text-green-400 text-sm">Total Deposits</span>
              </div>
              <p className="font-mono text-xl text-green-400">{formatCurrency(data.bank_summary.deposits, currency)}</p>
            </div>
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <ArrowDownRight className="w-4 h-4 text-red-400" />
                <span className="text-red-400 text-sm">Total Withdrawals</span>
              </div>
              <p className="font-mono text-xl text-red-400">{formatCurrency(data.bank_summary.withdrawals, currency)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
