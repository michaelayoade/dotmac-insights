'use client';

import Link from 'next/link';
import { TrendingUp, FileText, Calculator, CreditCard } from 'lucide-react';
import { useReportsRevenueSummary, useReportsExpensesSummary, useReportsProfitabilityMargins, useReportsCashPositionSummary } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { ErrorDisplay } from '@/components/insights/shared';

export default function ReportsOverviewPage() {
  const revenue = useReportsRevenueSummary();
  const expenses = useReportsExpensesSummary();
  const profitability = useReportsProfitabilityMargins();
  const cash = useReportsCashPositionSummary();

  const isLoading = revenue.isLoading && expenses.isLoading && profitability.isLoading && cash.isLoading;
  const error = revenue.error || expenses.error || profitability.error || cash.error;
  const handleRetry = () => {
    revenue.mutate();
    expenses.mutate();
    profitability.mutate();
    cash.mutate();
  };

  const cards = [
    {
      title: 'Revenue',
      href: '/reports/revenue',
      icon: TrendingUp,
      value: revenue.data?.total_revenue,
      sub: `MRR ${formatCurrency(revenue.data?.mrr || 0, revenue.data?.currency || 'NGN')}`,
      loading: revenue.isLoading,
    },
    {
      title: 'Expenses',
      href: '/reports/expenses',
      icon: FileText,
      value: expenses.data?.total_expenses,
      sub: expenses.data?.categories?.[0]?.category ? `Top: ${expenses.data.categories[0].category}` : '—',
      loading: expenses.isLoading,
    },
    {
      title: 'Profitability',
      href: '/reports/profitability',
      icon: Calculator,
      value: profitability.data?.gross_margin,
      sub: `Net ${profitability.data?.net_margin ?? 0}%`,
      loading: profitability.isLoading,
    },
    {
      title: 'Cash Position',
      href: '/reports/cash-position',
      icon: CreditCard,
      value: cash.data?.total_cash,
      sub: cash.data?.accounts?.[0]?.account ? `Top acct: ${cash.data.accounts[0].account}` : '—',
      loading: cash.isLoading,
    },
  ];

  return (
    <DashboardShell
      isLoading={isLoading}
      error={error}
      onRetry={handleRetry}
      loadingMessage="Loading reports data..."
      softError
    >
      <div className="space-y-6">
        {error && (
          <ErrorDisplay
            message="Failed to load reports data."
            error={error as Error}
            onRetry={handleRetry}
          />
        )}
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Reports</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {cards.map((card) => (
            <Link
              key={card.title}
              href={card.href}
              className="bg-slate-card border border-slate-border rounded-xl p-4 flex flex-col gap-1 hover:border-teal-electric/50 transition"
            >
              <div className="flex items-center gap-2 text-slate-muted text-sm">
                <card.icon className="w-4 h-4 text-teal-electric" />
                {card.title}
              </div>
              <p className="text-2xl font-bold text-foreground">
                {card.loading ? '—' : formatCurrency(card.value || 0, 'NGN')}
              </p>
              <p className="text-slate-muted text-sm">{card.sub}</p>
            </Link>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            href="/reports/revenue"
            className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-teal-electric/50 transition"
          >
            <div>
              <p className="text-sm text-slate-muted">Revenue</p>
              <p className="text-foreground font-semibold">Trends, customers, products</p>
            </div>
            <TrendingUp className="w-5 h-5 text-teal-electric" />
          </Link>
          <Link
            href="/reports/expenses"
            className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-teal-electric/50 transition"
          >
            <div>
              <p className="text-sm text-slate-muted">Expenses</p>
              <p className="text-foreground font-semibold">Trend and vendor breakdown</p>
            </div>
            <FileText className="w-5 h-5 text-teal-electric" />
          </Link>
          <Link
            href="/reports/profitability"
            className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-teal-electric/50 transition"
          >
            <div>
              <p className="text-sm text-slate-muted">Profitability</p>
              <p className="text-foreground font-semibold">Margins and segments</p>
            </div>
            <Calculator className="w-5 h-5 text-teal-electric" />
          </Link>
          <Link
            href="/reports/cash-position"
            className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-teal-electric/50 transition"
          >
            <div>
              <p className="text-sm text-slate-muted">Cash Position</p>
              <p className="text-foreground font-semibold">Balances, forecast, runway</p>
            </div>
            <CreditCard className="w-5 h-5 text-teal-electric" />
          </Link>
        </div>
    </div>
    </DashboardShell>
  );
}
