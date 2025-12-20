'use client';

import {
  useAccountingBalanceSheet,
  useAccountingIncomeStatement,
  useAccountingSuppliers,
  useAccountingBankAccounts,
  useAccountingGeneralLedger,
  useAccountingReceivables,
  useAccountingFiscalYears,
  useAccountingDashboard,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { ErrorDisplay } from '@/components/insights/shared';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  CreditCard,
  Building2,
  PiggyBank,
  Scale,
  ArrowUpRight,
  Loader2,
  Activity,
  BookOpen,
  Users,
  Landmark,
  FileText,
} from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatRatio(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0.00';
  return value.toFixed(2);
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  loading?: boolean;
}

function MetricCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', loading }: MetricCardProps) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-slate-muted text-sm">{title}</p>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <p className={cn('text-2xl font-bold', colorClass)}>{value}</p>
          )}
          {subtitle && <p className="text-slate-muted text-xs">{subtitle}</p>}
        </div>
        <div className={cn('p-2 rounded-lg bg-slate-elevated')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

interface RatioCardProps {
  title: string;
  value: string;
  description: string;
  status: 'good' | 'warning' | 'bad';
}

function RatioCard({ title, value, description, status }: RatioCardProps) {
  const statusColors = {
    good: 'border-green-500/30 bg-green-500/10',
    warning: 'border-yellow-500/30 bg-yellow-500/10',
    bad: 'border-red-500/30 bg-red-500/10',
  };
  const valueColors = {
    good: 'text-green-400',
    warning: 'text-yellow-400',
    bad: 'text-red-400',
  };

  return (
    <div className={cn('rounded-xl p-4 border', statusColors[status])}>
      <p className="text-slate-muted text-sm mb-1">{title}</p>
      <p className={cn('text-xl font-bold', valueColors[status])}>{value}</p>
      <p className="text-slate-muted text-xs mt-1">{description}</p>
    </div>
  );
}

export default function AccountingDashboardPage() {
  // Fetch data from multiple endpoints
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError, mutate: retryDashboard } = useAccountingDashboard();
  const { data: balanceSheet, isLoading: bsLoading, error: bsError, mutate: retryBs } = useAccountingBalanceSheet();
  const { data: incomeStatement, isLoading: isLoading, error: isError, mutate: retryIs } = useAccountingIncomeStatement();
  const { data: suppliers } = useAccountingSuppliers({ limit: 1 });
  const { data: bankAccounts } = useAccountingBankAccounts();
  const { data: ledger } = useAccountingGeneralLedger({ limit: 1 });
  const { data: receivables } = useAccountingReceivables();
  const { data: fiscalYears } = useAccountingFiscalYears();

  const loading = bsLoading || isLoading || dashboardLoading;
  const error = dashboardError || bsError || isError;
  const handleRetry = () => {
    retryDashboard();
    retryBs();
    retryIs();
  };

  // Extract key metrics with dashboard as primary source and statements as fallback
  const totalAssets = dashboard?.summary?.total_assets ?? balanceSheet?.assets?.total ?? 0;
  const totalLiabilities = dashboard?.summary?.total_liabilities ?? balanceSheet?.liabilities?.total ?? 0;
  const totalEquity = dashboard?.summary?.total_equity ?? balanceSheet?.equity?.total ?? 0;

  // Extract from income statement
  const totalRevenue = incomeStatement?.revenue?.total || 0;
  const totalExpenses = (incomeStatement?.cost_of_goods_sold?.total || 0)
    + (incomeStatement?.operating_expenses?.total || 0)
    + (incomeStatement?.other_expenses?.total || 0);
  const netIncome = dashboard?.summary?.net_income_ytd ?? incomeStatement?.net_income ?? 0;
  const profitMargin = totalRevenue > 0 ? (netIncome / totalRevenue) * 100 : 0;

  // Calculate cash balance from bank accounts
  const bankAccountsList = bankAccounts?.accounts || [];
  const cashBalanceFromAccounts = bankAccountsList.reduce((sum: number, acc: any) => {
    // Only count actual bank accounts (not payables)
    const balance = acc.balance || acc.current_balance || 0;
    return sum + balance;
  }, 0);
  const cashBalance = dashboard?.summary?.cash_balance ?? cashBalanceFromAccounts;

  // Get AR total
  const accountsReceivable = dashboard?.summary?.accounts_receivable ?? receivables?.total_receivable ?? 0;

  // Calculate financial ratios
  const currentRatio = totalLiabilities > 0 ? totalAssets / totalLiabilities : 0;
  const debtToEquity = totalEquity > 0 ? totalLiabilities / totalEquity : 0;

  // Determine ratio health status
  const currentRatioStatus = currentRatio >= 1.5 ? 'good' : currentRatio >= 1 ? 'warning' : 'bad';
  const debtEquityStatus = debtToEquity <= 1 ? 'good' : debtToEquity <= 2 ? 'warning' : 'bad';
  const marginStatus = profitMargin >= 20 ? 'good' : profitMargin >= 10 ? 'warning' : 'bad';

  // Counts
  const supplierCount = suppliers?.total || 0;
  const bankAccountCount = bankAccounts?.total || bankAccountsList.length || 0;
  const ledgerEntryCount = ledger?.total || 0;
  const fiscalYearCount = fiscalYears?.total || 0;

  return (
    <DashboardShell
      isLoading={loading && !dashboard && !balanceSheet}
      error={error}
      onRetry={handleRetry}
      loadingMessage="Loading accounting data..."
      errorMessage="Failed to load accounting data"
      softError
    >
      <div className="space-y-6">
        {error && (
          <ErrorDisplay
            message="Failed to load accounting data."
            error={error as Error}
            onRetry={handleRetry}
          />
        )}
        {/* Key Financial Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Total Assets"
            value={formatCurrency(totalAssets)}
            icon={Building2}
            colorClass="text-blue-400"
            loading={loading}
          />
          <MetricCard
            title="Total Liabilities"
            value={formatCurrency(totalLiabilities)}
            icon={CreditCard}
            colorClass="text-red-400"
            loading={loading}
          />
          <MetricCard
            title="Total Equity"
            value={formatCurrency(totalEquity)}
            icon={PiggyBank}
            colorClass="text-green-400"
            loading={loading}
          />
          <MetricCard
            title="Net Income (YTD)"
            value={formatCurrency(netIncome)}
            icon={TrendingUp}
            colorClass="text-teal-electric"
            loading={loading}
          />
        </div>

      {/* Cash & Receivables */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Cash & Bank"
          value={formatCurrency(cashBalance)}
          subtitle={`${bankAccountCount} bank accounts`}
          icon={Wallet}
          colorClass="text-emerald-400"
        />
        <MetricCard
          title="Accounts Receivable"
          value={formatCurrency(accountsReceivable)}
          subtitle="Outstanding AR"
          icon={ArrowUpRight}
          colorClass="text-blue-400"
        />
        <MetricCard
          title="Revenue (YTD)"
          value={formatCurrency(totalRevenue)}
          subtitle={`${profitMargin.toFixed(1)}% profit margin`}
          icon={DollarSign}
          colorClass="text-green-400"
          loading={loading}
        />
      </div>

      {/* Financial Ratios */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Scale className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Financial Ratios</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <RatioCard
            title="Current Ratio"
            value={formatRatio(currentRatio)}
            description="Total Assets / Total Liabilities"
            status={currentRatioStatus}
          />
          <RatioCard
            title="Debt to Equity"
            value={formatRatio(debtToEquity)}
            description="Total Liabilities / Total Equity"
            status={debtEquityStatus}
          />
          <RatioCard
            title="Profit Margin"
            value={`${profitMargin.toFixed(1)}%`}
            description="Net Income / Revenue"
            status={marginStatus}
          />
        </div>
      </div>

      {/* Revenue & Expenses */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <h2 className="text-lg font-semibold text-white">Revenue (YTD)</h2>
          </div>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-3xl font-bold text-green-400">{formatCurrency(totalRevenue)}</p>
              <p className="text-slate-muted text-sm mt-2">Total revenue for current year</p>
            </>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <h2 className="text-lg font-semibold text-white">Expenses (YTD)</h2>
          </div>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-3xl font-bold text-red-400">{formatCurrency(totalExpenses)}</p>
              <p className="text-slate-muted text-sm mt-2">Total expenses for current year</p>
            </>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <BookOpen className="w-6 h-6 text-teal-electric mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(ledgerEntryCount)}</p>
          <p className="text-slate-muted text-sm">Ledger Entries</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <Users className="w-6 h-6 text-orange-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(supplierCount)}</p>
          <p className="text-slate-muted text-sm">Suppliers</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <Landmark className="w-6 h-6 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(bankAccountCount)}</p>
          <p className="text-slate-muted text-sm">Bank Accounts</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <FileText className="w-6 h-6 text-purple-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(fiscalYearCount)}</p>
          <p className="text-slate-muted text-sm">Fiscal Years</p>
        </div>
      </div>

      {/* Balance Sheet Summary */}
      {balanceSheet && !bsLoading && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-white">Balance Sheet Summary</h2>
            <span className="text-slate-muted text-sm ml-auto">
              As of {typeof balanceSheet.as_of_date === 'string'
                ? balanceSheet.as_of_date
                : (() => {
                  const asOf: any = balanceSheet.as_of_date;
                  return asOf?.end_date || asOf?.start_date || '-';
                })()}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-slate-muted text-sm mb-2">Assets {((balanceSheet as any)?.assets?.accounts?.length || 0) ? `(${(balanceSheet as any).assets.accounts.length} accounts)` : ''}</p>
              <p className="text-2xl font-bold text-blue-400">{formatCurrency((balanceSheet as any)?.total_assets || balanceSheet.assets?.total || 0)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-2">Liabilities {((balanceSheet as any)?.liabilities?.accounts?.length || 0) ? `(${(balanceSheet as any).liabilities.accounts.length} accounts)` : ''}</p>
              <p className="text-2xl font-bold text-red-400">{formatCurrency((balanceSheet as any)?.liabilities?.total || 0)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-2">Equity + Retained Earnings</p>
              <p className="text-2xl font-bold text-green-400">{formatCurrency(totalEquity)}</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Accounting Equation Balance</span>
              <span className={cn(
                'px-3 py-1 rounded-full text-xs font-medium',
                balanceSheet.is_balanced
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-yellow-500/20 text-yellow-400'
              )}>
                {balanceSheet.is_balanced
                  ? 'Balanced'
                  : (() => {
                    const totals: any = balanceSheet;
                    return `Difference: ${formatCurrency(Math.abs((totals.total_assets || totals.assets?.total || 0) - (totals.total_liabilities_equity || totals.liabilities?.total || 0)))}`;
                  })()}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
    </DashboardShell>
  );
}
