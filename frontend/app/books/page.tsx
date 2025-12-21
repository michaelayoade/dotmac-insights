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
import { useConsolidatedAccountingDashboard } from '@/hooks/useApi';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import {
  DollarSign,
  TrendingUp,
  Wallet,
  CreditCard,
  Building2,
  PiggyBank,
  Scale,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
  BookOpen,
  Users,
  Landmark,
  ArrowRight,
} from 'lucide-react';
import { ErrorDisplay } from '@/components/insights/shared';
import { DashboardSkeleton } from '@/components/PageSkeleton';
import { PageHeader } from '@/components/ui';
import { CHART_COLORS } from '@/lib/design-tokens';

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
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

function formatCompactCurrency(value: number): string {
  if (value >= 1000000000) return `₦${(value / 1000000000).toFixed(1)}B`;
  if (value >= 1000000) return `₦${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `₦${(value / 1000).toFixed(0)}K`;
  return `₦${value.toFixed(0)}`;
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  loading?: boolean;
  href?: string;
}

function MetricCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', loading, href }: MetricCardProps) {
  const content = (
    <div className={cn(
      'bg-slate-card border border-slate-border rounded-xl p-5 transition-colors',
      href && 'hover:border-teal-electric/50 cursor-pointer'
    )}>
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
      {href && (
        <div className="mt-3 pt-3 border-t border-slate-border/50 flex items-center text-xs text-teal-electric">
          <span>View details</span>
          <ArrowRight className="w-3 h-3 ml-1" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
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

function ChartCard({ title, subtitle, icon: Icon, href, children }: { title: string; subtitle?: string; icon?: React.ElementType; href?: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-5 h-5 text-teal-electric" />}
          <div>
            <h3 className="text-foreground font-semibold">{title}</h3>
            {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
          </div>
        </div>
        {href && (
          <Link href={href} className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
            View Details <ArrowRight className="w-4 h-4" />
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}

export default function AccountingDashboardPage() {
  const currency = 'NGN';
  const { data, isLoading, error, mutate } = useConsolidatedAccountingDashboard(currency);

  // Chart data - must be called unconditionally
  const balanceSheetData = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'Assets', value: data.balance_sheet?.total_assets || 0, color: CHART_COLORS.info },
      { name: 'Liabilities', value: data.balance_sheet?.total_liabilities || 0, color: CHART_COLORS.danger },
      { name: 'Equity', value: data.balance_sheet?.total_equity || 0, color: CHART_COLORS.success },
    ].filter(item => item.value > 0);
  }, [data]);

  const revenueExpenseData = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'Revenue', amount: data.income_statement?.total_income || 0, fill: CHART_COLORS.success },
      { name: 'Expenses', amount: data.income_statement?.total_expenses || 0, fill: CHART_COLORS.warning },
      { name: 'Net Income', amount: data.income_statement?.net_income || 0, fill: (data.income_statement?.net_income || 0) >= 0 ? CHART_COLORS.success : CHART_COLORS.danger },
    ];
  }, [data]);

  const arApData = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'Receivables', AR: data.receivables?.total || 0, AP: 0 },
      { name: 'Payables', AR: 0, AP: data.payables?.total || 0 },
    ];
  }, [data]);

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load accounting dashboard data."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) {
    return <DashboardSkeleton />;
  }

  const { balance_sheet, income_statement, cash, receivables, payables, ratios, counts, fiscal_years } = data;

  // Calculate ratio status
  const currentRatioStatus = (ratios?.current_ratio || 0) >= 1.5 ? 'good' : (ratios?.current_ratio || 0) >= 1 ? 'warning' : 'bad';
  const debtEquityStatus = (ratios?.debt_to_equity || 0) <= 1 ? 'good' : (ratios?.debt_to_equity || 0) <= 2 ? 'warning' : 'bad';
  const marginStatus = (ratios?.profit_margin || 0) >= 20 ? 'good' : (ratios?.profit_margin || 0) >= 10 ? 'warning' : 'bad';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounting Dashboard"
        subtitle="Financial position, performance metrics, and key ratios"
        icon={BookOpen}
        iconClassName="bg-blue-500/10 border border-blue-500/30"
      />

      {/* Key Financial Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Assets"
          value={formatCurrency(balance_sheet?.total_assets)}
          icon={Building2}
          colorClass="text-blue-400"
          href="/books/balance-sheet"
        />
        <MetricCard
          title="Total Liabilities"
          value={formatCurrency(balance_sheet?.total_liabilities)}
          icon={CreditCard}
          colorClass="text-red-400"
          href="/books/balance-sheet"
        />
        <MetricCard
          title="Total Equity"
          value={formatCurrency(balance_sheet?.total_equity)}
          icon={PiggyBank}
          colorClass="text-green-400"
          href="/books/balance-sheet"
        />
        <MetricCard
          title="Net Income (YTD)"
          value={formatCurrency(income_statement?.net_income)}
          icon={TrendingUp}
          colorClass="text-teal-electric"
          href="/books/income-statement"
        />
      </div>

      {/* Liquidity & Outstanding */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Cash & Bank"
          value={formatCurrency(cash?.total)}
          subtitle={`${cash?.bank_accounts?.length || 0} bank accounts`}
          icon={Wallet}
          colorClass="text-emerald-400"
          href="/books/bank-accounts"
        />
        <MetricCard
          title="AR Outstanding"
          value={formatCurrency(receivables?.total)}
          subtitle="Top customers below"
          icon={ArrowUpRight}
          colorClass="text-blue-400"
          href="/books/receivables"
        />
        <MetricCard
          title="AP Outstanding"
          value={formatCurrency(payables?.total)}
          subtitle="Top suppliers below"
          icon={ArrowDownRight}
          colorClass="text-amber-400"
          href="/books/payables"
        />
        <MetricCard
          title="Revenue (YTD)"
          value={formatCurrency(income_statement?.total_income)}
          subtitle={`${(ratios?.profit_margin || 0).toFixed(1)}% profit margin`}
          icon={DollarSign}
          colorClass="text-green-400"
          href="/books/income-statement"
        />
      </div>

      {/* Financial Ratios */}
      <Link href="/books/ratios" className="block">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 hover:border-teal-electric/50 transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Scale className="w-5 h-5 text-teal-electric" />
              <h2 className="text-lg font-semibold text-foreground">Financial Ratios</h2>
            </div>
            <div className="text-teal-electric text-sm flex items-center gap-1">
              View Analysis <ArrowRight className="w-4 h-4" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <RatioCard
              title="Current Ratio"
              value={formatRatio(ratios?.current_ratio)}
              description="Total Assets / Total Liabilities"
              status={currentRatioStatus}
            />
            <RatioCard
              title="Debt to Equity"
              value={formatRatio(ratios?.debt_to_equity)}
              description="Total Liabilities / Total Equity"
              status={debtEquityStatus}
            />
            <RatioCard
              title="Profit Margin"
              value={`${(ratios?.profit_margin || 0).toFixed(1)}%`}
              description="Net Income / Revenue"
              status={marginStatus}
            />
          </div>
        </div>
      </Link>

      {/* Charts Row 1: Balance Sheet & Income Statement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Balance Sheet Composition" subtitle="Assets, Liabilities & Equity" icon={Building2} href="/books/balance-sheet">
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

        <ChartCard title="Income Statement" subtitle="Revenue vs Expenses" icon={TrendingUp} href="/books/income-statement">
          {revenueExpenseData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={revenueExpenseData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis type="number" tickFormatter={(val) => formatCompactCurrency(val)} tick={{ fill: 'var(--chart-muted)', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: 'var(--chart-text)', fontSize: 11 }} width={80} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => formatCompactCurrency(value)} />
                <Bar dataKey="amount" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No income data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Charts Row 2: AR/AP & Bank Accounts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Receivables vs Payables" subtitle="AR/AP Outstanding" icon={Scale} href="/books/receivables">
          {arApData.length > 0 && (arApData[0].AR > 0 || arApData[1].AP > 0) ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={arApData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="name" tick={{ fill: 'var(--chart-text)', fontSize: 11 }} />
                <YAxis tickFormatter={(val) => formatCompactCurrency(val)} tick={{ fill: 'var(--chart-muted)', fontSize: 10 }} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => formatCompactCurrency(value)} />
                <Bar dataKey="AR" fill={CHART_COLORS.success} name="Receivables" radius={[4, 4, 0, 0]} />
                <Bar dataKey="AP" fill={CHART_COLORS.warning} name="Payables" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted text-sm">
              No AR/AP data available
            </div>
          )}
        </ChartCard>

        {/* Bank Accounts */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Landmark className="w-5 h-5 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Bank Accounts</h3>
            </div>
            <Link href="/books/bank-accounts" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {cash?.bank_accounts && cash.bank_accounts.length > 0 ? (
            <div className="space-y-3">
              {cash.bank_accounts.map((account, index) => (
                <Link
                  key={account.id || index}
                  href={`/books/bank-accounts/${account.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div>
                    <p className="text-foreground text-sm font-medium">{account.account_name}</p>
                    <p className="text-slate-muted text-xs">{account.bank_name} •••• {account.account_number}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-foreground font-mono text-sm">{formatCurrency(account.balance, account.currency)}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="h-[120px] flex items-center justify-center text-slate-muted text-sm">
              No bank accounts configured
            </div>
          )}
        </div>
      </div>

      {/* Top Customers & Suppliers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ArrowUpRight className="w-5 h-5 text-blue-400" />
              <h3 className="text-foreground font-semibold">Top Customers (Outstanding)</h3>
            </div>
            <Link href="/books/receivables" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {receivables?.top_customers && receivables.top_customers.length > 0 ? (
            <div className="space-y-2">
              {receivables.top_customers.map((customer, index) => (
                <Link
                  key={index}
                  href={`/customers?search=${encodeURIComponent(customer.customer_name)}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 text-xs font-bold">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-foreground text-sm font-medium truncate max-w-[180px]">{customer.customer_name}</p>
                      <p className="text-slate-muted text-xs">{customer.invoice_count} invoices</p>
                    </div>
                  </div>
                  <p className="text-foreground font-mono text-sm">{formatCurrency(customer.outstanding)}</p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="h-[120px] flex items-center justify-center text-slate-muted text-sm">
              No outstanding receivables
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ArrowDownRight className="w-5 h-5 text-amber-400" />
              <h3 className="text-foreground font-semibold">Top Suppliers (Outstanding)</h3>
            </div>
            <Link href="/books/payables" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {payables?.top_suppliers && payables.top_suppliers.length > 0 ? (
            <div className="space-y-2">
              {payables.top_suppliers.map((supplier, index) => (
                <Link
                  key={index}
                  href={`/purchasing/suppliers?search=${encodeURIComponent(supplier.supplier_name)}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xs font-bold">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-foreground text-sm font-medium truncate max-w-[180px]">{supplier.supplier_name}</p>
                      <p className="text-slate-muted text-xs">{supplier.bill_count} bills</p>
                    </div>
                  </div>
                  <p className="text-foreground font-mono text-sm">{formatCurrency(supplier.outstanding)}</p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="h-[120px] flex items-center justify-center text-slate-muted text-sm">
              No outstanding payables
            </div>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/purchasing/suppliers" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <Users className="w-6 h-6 text-teal-electric mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(counts?.suppliers)}</p>
          <p className="text-slate-muted text-sm">Suppliers</p>
        </Link>
        <Link href="/books/general-ledger" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <BookOpen className="w-6 h-6 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(counts?.gl_entries)}</p>
          <p className="text-slate-muted text-sm">GL Entries (YTD)</p>
        </Link>
        <Link href="/books/bank-accounts" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <Landmark className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(cash?.bank_accounts?.length)}</p>
          <p className="text-slate-muted text-sm">Bank Accounts</p>
        </Link>
        <Link href="/books/fiscal-years" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <Scale className="w-6 h-6 text-purple-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(fiscal_years?.length)}</p>
          <p className="text-slate-muted text-sm">Fiscal Years</p>
        </Link>
      </div>
    </div>
  );
}
