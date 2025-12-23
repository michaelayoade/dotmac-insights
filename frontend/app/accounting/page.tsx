'use client';

import { useConsolidatedAccountingDashboard } from '@/hooks/useApi';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { ErrorDisplay } from '@/components/insights/shared';
import { DashboardSkeleton } from '@/components/PageSkeleton';
import { StatCard, StatCardGrid, RatioCard } from '@/components/StatCard';
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
import Link from 'next/link';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';
import { formatNumber, formatRatio } from '@/lib/formatters';

export default function AccountingDashboardPage() {
  const currency = 'NGN';
  const { data, isLoading, error, mutate } = useConsolidatedAccountingDashboard(currency);

  const hasCoreData = Boolean(data);
  const loading = isLoading && !hasCoreData;
  const handleRetry = () => mutate();

  const totalAssets = data?.balance_sheet?.total_assets ?? 0;
  const totalLiabilities = data?.balance_sheet?.total_liabilities ?? 0;
  const totalEquity = data?.balance_sheet?.total_equity ?? 0;
  const netWorth = data?.balance_sheet?.net_worth ?? 0;

  const totalRevenue = data?.income_statement?.total_income ?? 0;
  const totalExpenses = data?.income_statement?.total_expenses ?? 0;
  const netIncome = data?.income_statement?.net_income ?? 0;
  const profitMargin = data?.ratios?.profit_margin ?? 0;

  const bankAccountsList = data?.cash?.bank_accounts ?? [];
  const cashBalance = data?.cash?.total ?? 0;
  const accountsReceivable = data?.receivables?.total ?? 0;

  const currentRatio = data?.ratios?.current_ratio ?? 0;
  const debtToEquity = data?.ratios?.debt_to_equity ?? 0;

  const currentRatioStatus = currentRatio >= 1.5 ? 'good' : currentRatio >= 1 ? 'warning' : 'bad';
  const debtEquityStatus = debtToEquity <= 1 ? 'good' : debtToEquity <= 2 ? 'warning' : 'bad';
  const marginStatus = profitMargin >= 20 ? 'good' : profitMargin >= 10 ? 'warning' : 'bad';

  const supplierCount = data?.counts?.suppliers ?? 0;
  const bankAccountCount = bankAccountsList.length;
  const ledgerEntryCount = data?.counts?.gl_entries ?? 0;
  const fiscalYearCount = data?.fiscal_years?.length ?? 0;

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <DashboardShell
      isLoading={false}
      error={error}
      onRetry={handleRetry}
      loadingMessage="Loading accounting data..."
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
          <StatCard
            title="Total Assets"
            value={formatAccountingCurrency(totalAssets)}
            icon={Building2}
            colorClass="text-blue-400"
            loading={loading}
            href="/books/chart-of-accounts?type=asset"
          />
          <StatCard
            title="Total Liabilities"
            value={formatAccountingCurrency(totalLiabilities)}
            icon={CreditCard}
            colorClass="text-red-400"
            loading={loading}
            href="/books/chart-of-accounts?type=liability"
          />
          <StatCard
            title="Total Equity"
            value={formatAccountingCurrency(totalEquity)}
            icon={PiggyBank}
            colorClass="text-green-400"
            loading={loading}
            href="/books/chart-of-accounts?type=equity"
          />
          <StatCard
            title="Net Income (YTD)"
            value={formatAccountingCurrency(netIncome)}
            icon={TrendingUp}
            colorClass="text-teal-electric"
            loading={loading}
            href="/reports?report=income-statement"
          />
        </div>

      {/* Cash & Receivables */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Cash & Bank"
          value={formatAccountingCurrency(cashBalance)}
          subtitle={`${bankAccountCount} bank accounts`}
          icon={Wallet}
          colorClass="text-emerald-400"
          href="/books/bank-accounts"
        />
        <StatCard
          title="Accounts Receivable"
          value={formatAccountingCurrency(accountsReceivable)}
          subtitle="Outstanding AR"
          icon={ArrowUpRight}
          colorClass="text-blue-400"
          href="/books/invoices?status=unpaid"
        />
        <StatCard
          title="Revenue (YTD)"
          value={formatAccountingCurrency(totalRevenue)}
          subtitle={`${profitMargin.toFixed(1)}% profit margin`}
          icon={DollarSign}
          colorClass="text-green-400"
          loading={loading}
          href="/reports?report=income-statement"
        />
      </div>

      {/* Financial Ratios */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Scale className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-foreground">Financial Ratios</h2>
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
            <h2 className="text-lg font-semibold text-foreground">Revenue (YTD)</h2>
          </div>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-3xl font-bold text-green-400">{formatAccountingCurrency(totalRevenue)}</p>
              <p className="text-slate-muted text-sm mt-2">Total revenue for current year</p>
            </>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <h2 className="text-lg font-semibold text-foreground">Expenses (YTD)</h2>
          </div>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-3xl font-bold text-red-400">{formatAccountingCurrency(totalExpenses)}</p>
              <p className="text-slate-muted text-sm mt-2">Total expenses for current year</p>
            </>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/books/ledger" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center group hover:border-slate-border/80 hover:bg-slate-elevated/80 transition-colors cursor-pointer">
          <BookOpen className="w-6 h-6 text-teal-electric mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(ledgerEntryCount)}</p>
          <p className="text-slate-muted text-sm group-hover:text-foreground transition-colors">Ledger Entries</p>
        </Link>
        <Link href="/books/suppliers" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center group hover:border-slate-border/80 hover:bg-slate-elevated/80 transition-colors cursor-pointer">
          <Users className="w-6 h-6 text-orange-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(supplierCount)}</p>
          <p className="text-slate-muted text-sm group-hover:text-foreground transition-colors">Suppliers</p>
        </Link>
        <Link href="/books/bank-accounts" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center group hover:border-slate-border/80 hover:bg-slate-elevated/80 transition-colors cursor-pointer">
          <Landmark className="w-6 h-6 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(bankAccountCount)}</p>
          <p className="text-slate-muted text-sm group-hover:text-foreground transition-colors">Bank Accounts</p>
        </Link>
        <Link href="/books/settings/fiscal-years" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center group hover:border-slate-border/80 hover:bg-slate-elevated/80 transition-colors cursor-pointer">
          <FileText className="w-6 h-6 text-purple-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(fiscalYearCount)}</p>
          <p className="text-slate-muted text-sm group-hover:text-foreground transition-colors">Fiscal Years</p>
        </Link>
      </div>

      {/* Balance Sheet Summary */}
      {data?.balance_sheet && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-foreground">Balance Sheet Summary</h2>
            <span className="text-slate-muted text-sm ml-auto">
              As of {data.fiscal_year?.end || data.generated_at}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-slate-muted text-sm mb-2">Assets</p>
              <p className="text-2xl font-bold text-blue-400">{formatAccountingCurrency(totalAssets)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-2">Liabilities</p>
              <p className="text-2xl font-bold text-red-400">{formatAccountingCurrency(totalLiabilities)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-2">Net Worth</p>
              <p className="text-2xl font-bold text-green-400">{formatAccountingCurrency(netWorth)}</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted">Equity</span>
              <span className="text-foreground font-medium">{formatAccountingCurrency(totalEquity)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
    </DashboardShell>
  );
}
