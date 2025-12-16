'use client';

import { useState } from 'react';
import { useAccountingBalanceSheet } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { buildApiUrl } from '@/lib/api';
import {
  FileSpreadsheet,
  Building2,
  CreditCard,
  PiggyBank,
  Calendar,
  Download,
  BarChart2,
  ChevronDown,
  ChevronRight,
  Briefcase,
  Landmark,
  Coins,
  TrendingUp,
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

interface AccountLineProps {
  name: string;
  amount: number;
  indent?: number;
  bold?: boolean;
  className?: string;
  pct?: number;
}

function AccountLine({ name, amount, indent = 0, bold, className, pct }: AccountLineProps) {
  return (
    <div
      className={cn(
        'flex justify-between items-center py-2 border-b border-slate-border/50',
        bold && 'font-semibold',
        className
      )}
      style={{ paddingLeft: `${indent * 1.5}rem` }}
    >
      <span className="text-white">{name}</span>
      <div className="flex items-center gap-4">
        {pct !== undefined && (
          <span className="text-slate-muted text-sm w-16 text-right">{pct.toFixed(1)}%</span>
        )}
        <span className={cn('font-mono w-32 text-right', amount >= 0 ? 'text-white' : 'text-red-400')}>
          {formatCurrency(amount)}
        </span>
      </div>
    </div>
  );
}

interface CollapsibleSectionProps {
  title: string;
  icon: React.ElementType;
  items: Array<{ account: string; balance: number; account_type?: string; pct_of_total?: number }>;
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
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={cn('w-5 h-5', colorClass)} />
          <h3 className={cn('text-lg font-semibold', colorClass)}>{title}</h3>
          <span className="text-slate-muted text-sm">({items.length} accounts)</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn('font-mono font-bold', colorClass)}>{formatCurrency(total)}</span>
          {isOpen ? (
            <ChevronDown className="w-5 h-5 text-slate-muted" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-muted" />
          )}
        </div>
      </button>
      {isOpen && items.length > 0 && (
        <div className="px-4 pb-4 space-y-1">
          {items.map((item, index) => (
            <AccountLine
              key={index}
              name={item.account}
              amount={item.balance}
              pct={showPct ? item.pct_of_total : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface EquitySectionProps {
  title: string;
  data: {
    share_capital?: { accounts: any[]; total: number };
    share_premium?: { accounts: any[]; total: number };
    reserves?: { accounts: any[]; total: number };
    other_comprehensive_income?: { accounts: any[]; total: number };
    retained_earnings?: { accounts: any[]; total: number; current_period_profit?: number };
    treasury_shares?: { accounts: any[]; total: number };
    total?: number;
  };
  colorClass: string;
  showPct?: boolean;
  totalAssets?: number;
}

function EquitySection({ title, data, colorClass, showPct, totalAssets }: EquitySectionProps) {
  const [isOpen, setIsOpen] = useState(true);

  const components = [
    { label: 'Share Capital', data: data.share_capital, icon: Coins },
    { label: 'Share Premium', data: data.share_premium, icon: TrendingUp },
    { label: 'Reserves', data: data.reserves, icon: Briefcase },
    { label: 'Other Comprehensive Income', data: data.other_comprehensive_income, icon: BarChart2 },
    { label: 'Retained Earnings', data: data.retained_earnings, icon: PiggyBank },
    { label: 'Treasury Shares', data: data.treasury_shares, icon: Landmark },
  ].filter((c) => c.data && (c.data.total !== 0 || c.data.accounts?.length > 0));

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated transition-colors"
      >
        <div className="flex items-center gap-2">
          <PiggyBank className={cn('w-5 h-5', colorClass)} />
          <h3 className={cn('text-lg font-semibold', colorClass)}>{title}</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn('font-mono font-bold', colorClass)}>{formatCurrency(data.total || 0)}</span>
          {isOpen ? (
            <ChevronDown className="w-5 h-5 text-slate-muted" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-muted" />
          )}
        </div>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          {components.map((component, idx) => (
            <div key={idx} className="space-y-1">
              <div className="flex items-center gap-2 text-slate-muted text-sm">
                <component.icon className="w-4 h-4" />
                <span>{component.label}</span>
              </div>
              {component.data?.accounts?.map((acc: any, i: number) => (
                <AccountLine
                  key={i}
                  name={acc.account || acc.name}
                  amount={acc.balance || acc.amount || 0}
                  indent={1}
                  pct={showPct && totalAssets ? ((acc.balance || 0) / totalAssets) * 100 : undefined}
                />
              ))}
              {component.label === 'Retained Earnings' && data.retained_earnings?.current_period_profit !== undefined && (
                <AccountLine
                  name="Current Period Profit"
                  amount={data.retained_earnings.current_period_profit}
                  indent={1}
                  className="text-teal-400"
                />
              )}
              <AccountLine
                name={`Total ${component.label}`}
                amount={component.data?.total || 0}
                bold
                className="border-t border-slate-border"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function BalanceSheetPage() {
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [commonSize, setCommonSize] = useState<boolean>(false);
  const params = { as_of_date: asOfDate || undefined, common_size: commonSize || undefined };
  const { data, isLoading, error, mutate } = useAccountingBalanceSheet(params);

  const exportSheet = (format: 'csv' | 'pdf') => {
    const url = buildApiUrl('/accounting/balance-sheet/export', { ...params, format });
    window.open(url, '_blank');
  };

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load balance sheet."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  // Extract data with IFRS structure support
  const totalAssets = data?.total_assets || data?.assets?.total || 0;
  const totalLiabilities = data?.total_liabilities || data?.liabilities?.total || 0;
  const totalEquity = data?.total_equity || data?.equity?.total || 0;
  const workingCapital = data?.working_capital || 0;
  const currency = data?.currency || 'NGN';

  // Current/Non-Current classification
  const currentAssets = data?.assets_classified?.current_assets || { accounts: [], total: 0 };
  const nonCurrentAssets = data?.assets_classified?.non_current_assets || { accounts: [], total: 0 };
  const currentLiabilities = data?.liabilities_classified?.current_liabilities || { accounts: [], total: 0 };
  const nonCurrentLiabilities = data?.liabilities_classified?.non_current_liabilities || { accounts: [], total: 0 };

  // Equity breakdown
  const equityClassified = data?.equity_classified as { total?: number; accounts?: any[] } | undefined;

  // Fallback to traditional structure if classified data not available
  const assetsAccounts = data?.assets?.accounts || [];
  const liabilitiesAccounts = data?.liabilities?.accounts || [];
  const hasClassifiedData = currentAssets.accounts?.length > 0 || nonCurrentAssets.accounts?.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Statement of Financial Position</h2>
          {data?.as_of_date && (
            <span className="text-slate-muted text-sm">as of {data.as_of_date}</span>
          )}
          {currency && <span className="text-slate-muted text-xs ml-2">({currency})</span>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="input-field"
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
              onClick={() => {
                setAsOfDate('');
                setCommonSize(false);
              }}
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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Building2 className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Assets</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">{formatCurrency(totalAssets, currency)}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <CreditCard className="w-5 h-5 text-red-400" />
            <p className="text-red-400 text-sm">Total Liabilities</p>
          </div>
          <p className="text-2xl font-bold text-red-400">{formatCurrency(totalLiabilities, currency)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <PiggyBank className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Equity</p>
          </div>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(totalEquity, currency)}</p>
        </div>
        <div className={cn(
          'border rounded-xl p-5',
          workingCapital >= 0 ? 'bg-teal-500/10 border-teal-500/30' : 'bg-orange-500/10 border-orange-500/30'
        )}>
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className={cn('w-5 h-5', workingCapital >= 0 ? 'text-teal-400' : 'text-orange-400')} />
            <p className={cn('text-sm', workingCapital >= 0 ? 'text-teal-400' : 'text-orange-400')}>Working Capital</p>
          </div>
          <p className={cn('text-2xl font-bold', workingCapital >= 0 ? 'text-teal-400' : 'text-orange-400')}>
            {formatCurrency(workingCapital, currency)}
          </p>
        </div>
      </div>

      {/* Assets Section */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Building2 className="w-5 h-5 text-blue-400" />
          Assets
        </h3>

        {hasClassifiedData ? (
          <>
            <CollapsibleSection
              title="Current Assets"
              icon={Briefcase}
              items={currentAssets.accounts || []}
              total={currentAssets.total || 0}
              colorClass="text-blue-400"
              showPct={commonSize}
            />
            <CollapsibleSection
              title="Non-Current Assets"
              icon={Landmark}
              items={nonCurrentAssets.accounts || []}
              total={nonCurrentAssets.total || 0}
              colorClass="text-blue-300"
              showPct={commonSize}
            />
          </>
        ) : (
          <CollapsibleSection
            title="All Assets"
            icon={Building2}
            items={assetsAccounts}
            total={totalAssets}
            colorClass="text-blue-400"
            showPct={commonSize}
          />
        )}
      </div>

      {/* Liabilities Section */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-red-400" />
          Liabilities
        </h3>

        {hasClassifiedData ? (
          <>
            <CollapsibleSection
              title="Current Liabilities"
              icon={CreditCard}
              items={currentLiabilities.accounts || []}
              total={currentLiabilities.total || 0}
              colorClass="text-red-400"
              showPct={commonSize}
            />
            <CollapsibleSection
              title="Non-Current Liabilities"
              icon={Landmark}
              items={nonCurrentLiabilities.accounts || []}
              total={nonCurrentLiabilities.total || 0}
              colorClass="text-red-300"
              showPct={commonSize}
            />
          </>
        ) : (
          <CollapsibleSection
            title="All Liabilities"
            icon={CreditCard}
            items={liabilitiesAccounts}
            total={totalLiabilities}
            colorClass="text-red-400"
            showPct={commonSize}
          />
        )}
      </div>

      {/* Equity Section with IFRS breakdown */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <PiggyBank className="w-5 h-5 text-green-400" />
          Equity
        </h3>

        {equityClassified?.total !== undefined ? (
          <EquitySection
            title="Shareholders' Equity"
            data={equityClassified}
            colorClass="text-green-400"
            showPct={commonSize}
            totalAssets={totalAssets}
          />
        ) : (
          <CollapsibleSection
            title="Equity"
            icon={PiggyBank}
            items={data?.equity?.accounts || []}
            total={totalEquity}
            colorClass="text-green-400"
            showPct={commonSize}
          />
        )}
      </div>

      {/* Accounting Equation */}
      <div className="bg-slate-elevated border border-slate-border rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Accounting Equation (IAS 1)</h3>
        <div className="flex items-center justify-center gap-4 text-lg flex-wrap">
          <div className="text-center">
            <p className="text-slate-muted text-sm">Assets</p>
            <p className="font-mono font-bold text-blue-400">{formatCurrency(totalAssets, currency)}</p>
          </div>
          <span className="text-slate-muted text-2xl">=</span>
          <div className="text-center">
            <p className="text-slate-muted text-sm">Liabilities</p>
            <p className="font-mono font-bold text-red-400">{formatCurrency(totalLiabilities, currency)}</p>
          </div>
          <span className="text-slate-muted text-2xl">+</span>
          <div className="text-center">
            <p className="text-slate-muted text-sm">Equity</p>
            <p className="font-mono font-bold text-green-400">{formatCurrency(totalEquity, currency)}</p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-slate-border text-center">
          <p className="text-slate-muted text-sm">
            Difference:{' '}
            <span
              className={cn(
                'font-mono font-semibold',
                data?.is_balanced ? 'text-green-400' : 'text-red-400'
              )}
            >
              {formatCurrency(data?.difference || 0, currency)}
            </span>
            {data?.is_balanced && (
              <span className="ml-2 px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded-full">
                Balanced
              </span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
