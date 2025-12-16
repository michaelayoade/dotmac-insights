'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  useAccountingBalanceSheet,
  useAccountingIncomeStatement,
  useAccountingSuppliers,
  useAccountingBankAccounts,
  useAccountingGeneralLedger,
  useAccountingReceivables,
  useAccountingFiscalYears,
  useAccountingDashboard,
  useAccountingReceivablesOutstanding,
  useAccountingPayablesOutstanding,
  useAccountingCashFlow,
} from '@/hooks/useApi';
import Link from 'next/link';
import { cn } from '@/lib/utils';
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
  ArrowDownRight,
  AlertTriangle,
  Loader2,
  Activity,
  BookOpen,
  Users,
  Landmark,
  FileText,
  Plus,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

// Chart color palette matching the teal/finance theme
const CHART_COLORS = ['#2dd4bf', '#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ec4899'];
const TOOLTIP_STYLE = {
  contentStyle: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' },
  labelStyle: { color: '#f8fafc' },
};

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

function ChartCard({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-5 h-5 text-teal-electric" />}
        <div>
          <h3 className="text-white font-semibold">{title}</h3>
          {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function formatCompactCurrency(value: number): string {
  if (value >= 1000000000) return `₦${(value / 1000000000).toFixed(1)}B`;
  if (value >= 1000000) return `₦${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `₦${(value / 1000).toFixed(0)}K`;
  return `₦${value.toFixed(0)}`;
}

export default function AccountingDashboardPage() {
  const currency = 'NGN';
  // Fetch data from multiple endpoints
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError, mutate: refetchDashboard } = useAccountingDashboard(currency);
  const { data: balanceSheet, isLoading: bsLoading, error: bsError, mutate: refetchBalance } = useAccountingBalanceSheet({ currency });
  const { data: incomeStatement, isLoading: incomeLoading, error: incomeError, mutate: refetchIncome } = useAccountingIncomeStatement({ currency });
  const { data: suppliers, isLoading: suppliersLoading, error: suppliersError, mutate: refetchSuppliers } = useAccountingSuppliers({ limit: 1, currency });
  const { data: bankAccounts, isLoading: bankLoading, error: bankError, mutate: refetchBank } = useAccountingBankAccounts();
  const { data: ledger, isLoading: ledgerLoading, error: ledgerError, mutate: refetchLedger } = useAccountingGeneralLedger({ limit: 1, currency });
  const { data: receivables, isLoading: receivablesLoading, error: receivablesError, mutate: refetchReceivables } = useAccountingReceivables({ currency });
  const { data: fiscalYears, isLoading: fiscalLoading, error: fiscalError, mutate: refetchFiscal } = useAccountingFiscalYears();
  const { data: receivablesOutstanding, isLoading: receivablesOutstandingLoading, error: receivablesOutstandingError, mutate: refetchReceivablesOutstanding } = useAccountingReceivablesOutstanding({ currency, top: 5 });
  const { data: payablesOutstanding, isLoading: payablesOutstandingLoading, error: payablesOutstandingError, mutate: refetchPayablesOutstanding } = useAccountingPayablesOutstanding({ currency, top: 5 });
  const { data: cashFlow, isLoading: cashFlowLoading, error: cashFlowError, mutate: refetchCashFlow } = useAccountingCashFlow();

  const swrStates = [
    { error: dashboardError, isLoading: dashboardLoading, mutate: refetchDashboard },
    { error: bsError, isLoading: bsLoading, mutate: refetchBalance },
    { error: incomeError, isLoading: incomeLoading, mutate: refetchIncome },
    { error: suppliersError, isLoading: suppliersLoading, mutate: refetchSuppliers },
    { error: bankError, isLoading: bankLoading, mutate: refetchBank },
    { error: ledgerError, isLoading: ledgerLoading, mutate: refetchLedger },
    { error: receivablesError, isLoading: receivablesLoading, mutate: refetchReceivables },
    { error: fiscalError, isLoading: fiscalLoading, mutate: refetchFiscal },
    { error: receivablesOutstandingError, isLoading: receivablesOutstandingLoading, mutate: refetchReceivablesOutstanding },
    { error: payablesOutstandingError, isLoading: payablesOutstandingLoading, mutate: refetchPayablesOutstanding },
    { error: cashFlowError, isLoading: cashFlowLoading, mutate: refetchCashFlow },
  ];

  const firstError = swrStates.find((state) => state.error)?.error;
  const loading = swrStates.some((state) => state.isLoading);
  const retryAll = () => swrStates.forEach((state) => state.mutate?.());

  if (loading) {
    return <LoadingState />;
  }

  if (firstError) {
    return (
      <ErrorDisplay
        message="Failed to load accounting dashboard data."
        error={firstError as Error}
        onRetry={retryAll}
      />
    );
  }

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
  const arOutstanding = receivablesOutstanding?.total || 0;
  const apOutstanding = payablesOutstanding?.total || 0;
  const topCustomers = receivablesOutstanding?.top || [];
  const topSuppliers = payablesOutstanding?.top || [];

  // Chart data: Balance sheet composition
  const balanceSheetData = useMemo(() => {
    return [
      { name: 'Assets', value: totalAssets, color: '#3b82f6' },
      { name: 'Liabilities', value: totalLiabilities, color: '#ef4444' },
      { name: 'Equity', value: totalEquity, color: '#10b981' },
    ].filter(item => item.value > 0);
  }, [totalAssets, totalLiabilities, totalEquity]);

  // Chart data: Revenue vs Expenses comparison
  const revenueExpenseData = useMemo(() => {
    const cogs = incomeStatement?.cost_of_goods_sold?.total || 0;
    const opex = incomeStatement?.operating_expenses?.total || 0;
    const otherExp = incomeStatement?.other_expenses?.total || 0;
    const otherInc = incomeStatement?.other_income?.total || 0;

    return [
      { name: 'Revenue', amount: totalRevenue, fill: '#10b981' },
      { name: 'COGS', amount: cogs, fill: '#f59e0b' },
      { name: 'Operating', amount: opex, fill: '#8b5cf6' },
      { name: 'Other Exp', amount: otherExp, fill: '#ef4444' },
      { name: 'Other Inc', amount: otherInc, fill: '#2dd4bf' },
      { name: 'Net Income', amount: netIncome, fill: netIncome >= 0 ? '#10b981' : '#ef4444' },
    ];
  }, [incomeStatement, totalRevenue, netIncome]);

  // Chart data: AR vs AP comparison
  const arApData = useMemo(() => {
    return [
      { name: 'Receivables', AR: arOutstanding || accountsReceivable, AP: 0 },
      { name: 'Payables', AR: 0, AP: apOutstanding },
    ];
  }, [arOutstanding, apOutstanding, accountsReceivable]);

  // Chart data: Top customers/suppliers for horizontal bar
  const topPartiesData = useMemo(() => {
    const customers = topCustomers.slice(0, 5).map((c: any) => ({
      name: (c.name || 'Customer').substring(0, 15),
      amount: c.amount || 0,
      type: 'AR',
    }));
    const suppliers = topSuppliers.slice(0, 5).map((s: any) => ({
      name: (s.name || 'Supplier').substring(0, 15),
      amount: s.amount || 0,
      type: 'AP',
    }));
    return [...customers, ...suppliers];
  }, [topCustomers, topSuppliers]);

  // Cash flow data
  const cashFlowData = useMemo(() => {
    if (!cashFlow) return [];
    return [
      { name: 'Operating', value: cashFlow.operating_activities?.net || 0, fill: '#10b981' },
      { name: 'Investing', value: cashFlow.investing_activities?.net || 0, fill: '#3b82f6' },
      { name: 'Financing', value: cashFlow.financing_activities?.net || 0, fill: '#8b5cf6' },
    ];
  }, [cashFlow]);

  return (
    <div className="space-y-6">
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

      {/* Liquidity & Outstanding */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Cash & Bank"
          value={formatCurrency(cashBalance)}
          subtitle={`${bankAccountCount} bank accounts`}
          icon={Wallet}
          colorClass="text-emerald-400"
        />
        <MetricCard
          title="AR Outstanding"
          value={formatCurrency(arOutstanding || accountsReceivable)}
          subtitle="Top customers below"
          icon={ArrowUpRight}
          colorClass="text-blue-400"
        />
        <MetricCard
          title="AP Outstanding"
          value={formatCurrency(apOutstanding)}
          subtitle="Top suppliers below"
          icon={ArrowDownRight}
          colorClass="text-amber-400"
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

      {/* Charts Row 1: Balance Sheet & Income Statement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Balance Sheet Composition */}
        <ChartCard title="Balance Sheet Composition" subtitle="Assets, Liabilities & Equity" icon={Building2}>
          {balanceSheetData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={balanceSheetData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {balanceSheetData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(value: number) => formatCompactCurrency(value)}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No balance sheet data available
            </div>
          )}
        </ChartCard>

        {/* Income Statement Breakdown */}
        <ChartCard title="Income Statement" subtitle="Revenue, expenses & net income" icon={TrendingUp}>
          {revenueExpenseData.some(d => d.amount > 0) ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={revenueExpenseData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis
                  type="number"
                  stroke="#64748b"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => formatCompactCurrency(v)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  width={70}
                />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(value: number) => formatCurrency(value)}
                />
                <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
                  {revenueExpenseData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No income statement data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Charts Row 2: AR/AP & Cash Flow */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* AR vs AP */}
        <ChartCard title="Receivables vs Payables" subtitle="Outstanding amounts" icon={DollarSign}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={arApData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(v) => formatCompactCurrency(v)} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => formatCurrency(value)} />
              <Bar dataKey="AR" name="Receivables" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="AP" name="Payables" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-3 flex items-center justify-between text-xs">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-slate-muted">AR: {formatCurrency(arOutstanding || accountsReceivable)}</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="text-slate-muted">AP: {formatCurrency(apOutstanding)}</span>
              </span>
            </div>
            <span className={cn(
              'font-semibold',
              (arOutstanding || accountsReceivable) > apOutstanding ? 'text-blue-400' : 'text-amber-400'
            )}>
              Net: {formatCurrency((arOutstanding || accountsReceivable) - apOutstanding)}
            </span>
          </div>
        </ChartCard>

        {/* Cash Flow */}
        <ChartCard title="Cash Flow" subtitle="Operating, investing & financing" icon={Wallet}>
          {cashFlowData.length > 0 && cashFlowData.some(d => d.value !== 0) ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={cashFlowData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(v) => formatCompactCurrency(v)} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => formatCurrency(value)} />
                  <Bar dataKey="value" name="Amount" radius={[4, 4, 0, 0]}>
                    {cashFlowData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-2 pt-2 border-t border-slate-border flex items-center justify-between text-sm">
                <span className="text-slate-muted">Net Change in Cash</span>
                <span className={cn(
                  'font-bold',
                  (cashFlow?.net_change_in_cash || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                )}>
                  {formatCurrency(cashFlow?.net_change_in_cash || 0)}
                </span>
              </div>
            </>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">
              No cash flow data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Revenue & Expenses Summary */}
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

      {/* Outstanding detail */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ArrowUpRight className="w-4 h-4 text-blue-400" />
              <h3 className="text-white font-semibold">Top Customers (Outstanding)</h3>
            </div>
            <span className="text-slate-muted text-xs">AR detail</span>
          </div>
          {topCustomers.length ? (
            <div className="space-y-2">
              {topCustomers.map((c: any) => (
                <div key={c.id || c.name} className="flex items-center justify-between text-sm">
                  <div className="text-white truncate max-w-[220px]">{c.name || 'Unknown Customer'}</div>
                  <div className="font-mono text-slate-muted">{formatCurrency(c.amount || 0, c.currency || currency)}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No outstanding customers</p>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ArrowDownRight className="w-4 h-4 text-amber-400" />
              <h3 className="text-white font-semibold">Top Suppliers (Outstanding)</h3>
            </div>
            <span className="text-slate-muted text-xs">AP detail</span>
          </div>
          {topSuppliers.length ? (
            <div className="space-y-2">
              {topSuppliers.map((s: any) => (
                <div key={s.id || s.name} className="flex items-center justify-between text-sm">
                  <div className="text-white truncate max-w-[220px]">{s.name || 'Unknown Supplier'}</div>
                  <div className="font-mono text-slate-muted">{formatCurrency(s.amount || 0, s.currency || currency)}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No outstanding suppliers</p>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2">
        {[
          { href: '/books/accounts-receivable/invoices/new', label: 'New Invoice' },
          { href: '/books/accounts-receivable/payments/new', label: 'New Payment' },
        ].map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
          >
            <Plus className="w-4 h-4" />
            {action.label}
          </Link>
        ))}
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
              <p className="text-2xl font-bold text-blue-400">{formatCurrency((balanceSheet as any)?.total_assets || (balanceSheet as any)?.assets?.total || 0)}</p>
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
              <span
                className={cn(
                  'px-3 py-1 rounded-full text-xs font-medium',
                  balanceSheet.is_balanced
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-yellow-500/20 text-yellow-400'
                )}
              >
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
  );
}
