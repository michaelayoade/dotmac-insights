'use client';

import Link from 'next/link';
import {
  useFinanceDashboard,
  useFinanceAging,
  useFinanceRevenueTrend,
  useFinanceInvoices,
  useFinancePayments,
  useFinanceCreditNotes,
  usePurchasingBills,
  usePurchasingPayments,
  useLeadsSummary,
  usePipelineSummary,
  usePipelineView,
  useUpcomingActivities,
  useOverdueActivities,
} from '@/hooks/useApi';
import type { FinanceAgingAnalytics } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  FileText,
  CreditCard,
  Clock,
  AlertTriangle,
  CheckCircle,
  ShoppingCart,
  Receipt,
  Target,
  UserPlus,
  Calendar,
  ArrowRight,
  BarChart3,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';

function formatCurrency(value: number, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  className?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, trend, trendValue, className }: StatCardProps) {
  return (
    <div className={cn('bg-slate-card rounded-xl border border-slate-border p-6', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-slate-muted text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
          {trend && trendValue && (
            <div className={cn(
              'flex items-center gap-1 mt-2 text-sm',
              trend === 'up' && 'text-green-400',
              trend === 'down' && 'text-red-400',
              trend === 'neutral' && 'text-slate-muted'
            )}>
              {trend === 'up' && <TrendingUp className="w-4 h-4" />}
              {trend === 'down' && <TrendingDown className="w-4 h-4" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        <div className="p-3 bg-slate-elevated rounded-lg">
          <Icon className="w-6 h-6 text-teal-electric" />
        </div>
      </div>
    </div>
  );
}

function AgingChart({ buckets }: { buckets: FinanceAgingAnalytics['buckets'] }) {
  if (!buckets) return null;

  const colorMap: Record<string, string> = {
    current: 'bg-green-500',
    '1_30': 'bg-yellow-500',
    '31_60': 'bg-orange-500',
    '61_90': 'bg-red-400',
    over_90: 'bg-red-600',
  };

  const entries = [
    { key: 'current', label: 'Current', ...buckets.current },
    { key: '1_30', label: '1-30 days', ...buckets['1_30'] },
    { key: '31_60', label: '31-60 days', ...buckets['31_60'] },
    { key: '61_90', label: '61-90 days', ...buckets['61_90'] },
    { key: 'over_90', label: 'Over 90 days', ...buckets.over_90 },
  ];

  const total = entries.reduce((sum, b) => sum + (b.total || 0), 0);

  return (
    <div className="bg-slate-card rounded-xl border border-slate-border p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Invoice Aging</h3>
      <div className="space-y-3">
        {entries.map((bucket) => {
          const amount = bucket.total || 0;
          const count = bucket.count || 0;
          const percent = total > 0 ? (amount / total) * 100 : 0;

          return (
            <div key={bucket.key}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-muted capitalize">{bucket.label}</span>
                <span className="text-white font-mono">
                  {formatCurrency(amount)} ({count})
                </span>
              </div>
              <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all', colorMap[bucket.key] || 'bg-teal-electric')}
                  style={{ width: `${Math.max(percent, percent > 0 ? 2 : 0)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 pt-4 border-t border-slate-border">
        <div className="flex justify-between">
          <span className="text-slate-muted">Total Outstanding</span>
          <span className="text-white font-bold font-mono">{formatCurrency(total)}</span>
        </div>
      </div>
    </div>
  );
}

export default function SalesDashboardPage() {
  const currency = 'NGN';
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError, mutate: refetchDashboard } = useFinanceDashboard(currency);
  const { data: aging, isLoading: agingLoading, error: agingError, mutate: refetchAging } = useFinanceAging({ currency });
  const { data: revenueTrend, isLoading: trendLoading, error: trendError, mutate: refetchTrend } = useFinanceRevenueTrend({ currency, interval: 'month' });
  const { data: recentInvoices, error: invoicesError, mutate: refetchInvoices, isLoading: invoicesLoading } = useFinanceInvoices({
    currency,
    page: 1,
    page_size: 5,
    sort_by: 'invoice_date',
    sort_order: 'desc',
  });
  const { data: recentPayments, error: paymentsError, mutate: refetchPayments, isLoading: paymentsLoading } = useFinancePayments({
    currency,
    page: 1,
    page_size: 5,
    sort_by: 'payment_date',
    sort_order: 'desc',
  });
  const { data: recentCredits, error: creditsError, mutate: refetchCredits, isLoading: creditsLoading } = useFinanceCreditNotes({
    currency,
    page: 1,
    page_size: 5,
    sort_by: 'issue_date',
    sort_order: 'desc',
  });
  const { data: recentBills, error: billsError, mutate: refetchBills, isLoading: billsLoading } = usePurchasingBills({ currency, limit: 5, sort_by: 'posting_date', sort_dir: 'desc' });
  const { data: recentPurchasePayments, error: purchasePaymentsError, mutate: refetchPurchasePayments, isLoading: purchasePaymentsLoading } = usePurchasingPayments({ currency, limit: 5 });

  // CRM Data
  const { data: leadsSummary, isLoading: leadsLoading } = useLeadsSummary();
  const { data: pipelineSummary, isLoading: pipelineLoading } = usePipelineSummary();
  const { data: pipelineView, isLoading: pipelineViewLoading } = usePipelineView();
  const { data: upcomingActivities, isLoading: activitiesLoading } = useUpcomingActivities(5);
  const { data: overdueActivities } = useOverdueActivities();

  const swrStates = [
    { error: dashboardError, isLoading: dashboardLoading, mutate: refetchDashboard },
    { error: agingError, isLoading: agingLoading, mutate: refetchAging },
    { error: trendError, isLoading: trendLoading, mutate: refetchTrend },
    { error: invoicesError, isLoading: invoicesLoading, mutate: refetchInvoices },
    { error: paymentsError, isLoading: paymentsLoading, mutate: refetchPayments },
    { error: creditsError, isLoading: creditsLoading, mutate: refetchCredits },
    { error: billsError, isLoading: billsLoading, mutate: refetchBills },
    { error: purchasePaymentsError, isLoading: purchasePaymentsLoading, mutate: refetchPurchasePayments },
  ];

  const firstError = swrStates.find((state) => state.error)?.error;
  const isDataLoading = swrStates.some((state) => state.isLoading);
  const retryAll = () => swrStates.forEach((state) => state.mutate?.());

  if (isDataLoading) {
    return <LoadingState />;
  }

  const collectionRate = dashboard?.collections?.collection_rate ?? 0;
  const outstandingTotal = dashboard?.outstanding?.total ?? 0;
  const overdueTotal = dashboard?.outstanding?.overdue ?? 0;
  const invoiced30d = dashboard?.collections?.invoiced_30_days ?? 0;
  const collected30d = dashboard?.collections?.last_30_days ?? 0;

  return (
    <div className="space-y-6">
      {firstError && (
        <ErrorDisplay
          message="Failed to load sales dashboard data."
          error={firstError as Error}
          onRetry={retryAll}
        />
      )}
      <PageHeader
        title="Sales Dashboard"
        subtitle="CRM pipeline, revenue metrics, and financial performance"
        icon={BarChart3}
        iconClassName="bg-teal-500/10 border border-teal-500/30"
      />

      {/* CRM Pipeline Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Pipeline Value"
          value={formatCurrency(pipelineSummary?.total_value || 0, currency)}
          subtitle={`Weighted: ${formatCurrency(pipelineSummary?.weighted_value || 0, currency)}`}
          icon={Target}
        />
        <StatCard
          title="Open Opportunities"
          value={formatNumber(pipelineSummary?.open_count || 0)}
          subtitle={`Win Rate: ${((pipelineSummary?.win_rate || 0) * 100).toFixed(0)}%`}
          icon={TrendingUp}
          trend={pipelineSummary?.win_rate >= 0.3 ? 'up' : 'down'}
          trendValue={pipelineSummary?.win_rate >= 0.3 ? 'Above Target' : 'Below Target'}
        />
        <StatCard
          title="Active Leads"
          value={formatNumber((leadsSummary?.new || 0) + (leadsSummary?.contacted || 0) + (leadsSummary?.qualified || 0))}
          subtitle={`New: ${leadsSummary?.new || 0} | Qualified: ${leadsSummary?.qualified || 0}`}
          icon={UserPlus}
        />
        <StatCard
          title="Activities"
          value={formatNumber(upcomingActivities?.items?.length || 0)}
          subtitle={overdueActivities?.items?.length ? `${overdueActivities.items.length} overdue` : 'All on track'}
          icon={Calendar}
          trend={overdueActivities?.items?.length ? 'down' : 'up'}
          trendValue={overdueActivities?.items?.length ? 'Action needed' : 'Healthy'}
        />
      </div>

      {/* Pipeline Stages Overview */}
      {pipelineView && pipelineView.stages?.length > 0 && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Sales Pipeline</h3>
            <Link href="/sales/pipeline" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Pipeline <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {pipelineView.stages.filter((s: any) => !s.is_won && !s.is_lost).map((stage: any) => (
              <div key={stage.id} className="bg-slate-elevated/50 rounded-lg p-3 border border-slate-border/50">
                <div className="text-xs text-slate-muted mb-1">{stage.name}</div>
                <div className="text-lg font-semibold text-white">{stage.opportunity_count}</div>
                <div className="text-xs text-teal-electric">{formatCurrency(stage.opportunity_value || 0, currency)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key AR Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Monthly Recurring Revenue"
          value={formatCurrency(dashboard?.revenue?.mrr || 0, dashboard?.currency || currency)}
          subtitle={`ARR: ${formatCurrency(dashboard?.revenue?.arr || 0, dashboard?.currency || currency)}`}
          icon={TrendingUp}
        />
        <StatCard
          title="Invoiced (30d)"
          value={formatCurrency(invoiced30d, dashboard?.currency || currency)}
          subtitle="Last 30 days"
          icon={FileText}
        />
        <StatCard
          title="Collected (30d)"
          value={formatCurrency(collected30d, dashboard?.currency || currency)}
          subtitle={`Collection Rate: ${(collectionRate * 100).toFixed(1)}%`}
          icon={CreditCard}
          trend={collectionRate >= 0.8 ? 'up' : 'down'}
          trendValue={collectionRate >= 0.8 ? 'Healthy' : 'Below Target'}
        />
        <StatCard
          title="Outstanding"
          value={formatCurrency(outstandingTotal, dashboard?.currency || currency)}
          subtitle={`Overdue: ${formatCurrency(overdueTotal, dashboard?.currency || currency)}`}
          icon={Clock}
        />
      </div>

      {/* DSO and Collection Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Days Sales Outstanding (DSO)</h3>
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <p className="text-5xl font-bold text-teal-electric">{dashboard?.metrics?.dso?.toFixed(0) || '-'}</p>
              <p className="text-slate-muted mt-2">days</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center justify-center gap-4 text-sm">
              {(dashboard?.metrics?.dso || 0) <= 30 ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <span className="text-green-400">Excellent - Below 30 days</span>
                </>
              ) : (dashboard?.metrics?.dso || 0) <= 45 ? (
                <>
                  <CheckCircle className="w-5 h-5 text-yellow-400" />
                  <span className="text-yellow-400">Good - Monitor closely</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <span className="text-red-400">High - Action needed</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Aging Chart */}
        {agingLoading ? (
          <div className="bg-slate-card rounded-xl border border-slate-border p-6 animate-pulse">
            <div className="h-6 bg-slate-elevated rounded w-1/3 mb-4" />
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i}>
                  <div className="h-4 bg-slate-elevated rounded w-full mb-2" />
                  <div className="h-2 bg-slate-elevated rounded" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <AgingChart buckets={aging?.buckets as any} />
        )}
      </div>

      {/* Revenue Trend */}
      {trendLoading ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6 animate-pulse">
          <div className="h-6 bg-slate-elevated rounded w-1/4 mb-4" />
          <div className="h-48 bg-slate-elevated rounded" />
        </div>
      ) : revenueTrend && revenueTrend.length > 0 ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Revenue Trend (12 Months)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border">
                  <th className="text-left py-3 px-2 text-slate-muted font-medium">Period</th>
                  <th className="text-right py-3 px-2 text-slate-muted font-medium">Revenue</th>
                  <th className="text-right py-3 px-2 text-slate-muted font-medium">Payments</th>
                </tr>
              </thead>
              <tbody>
                {revenueTrend.slice(-6).map((item: any, i: number) => (
                  <tr key={i} className="border-b border-slate-border/50 hover:bg-slate-elevated/30">
                    <td className="py-3 px-2 text-white">{item.period}</td>
                    <td className="py-3 px-2 text-right font-mono text-white">{formatCurrency(item.revenue, dashboard?.currency || currency)}</td>
                    <td className="py-3 px-2 text-right font-mono text-teal-electric">{(item.payment_count ?? 0).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Period Info */}
      {dashboard?.period && (
        <p className="text-xs text-slate-muted text-center">
          Data period: {dashboard.period.start} to {dashboard.period.end}
        </p>
      )}

      {/* Sales quick lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Invoices</h3>
            </div>
            <Link href="/sales/invoices" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentInvoices?.invoices?.length ? (
            <div className="space-y-2">
              {recentInvoices.invoices.map((inv: any) => (
                <Link
                  key={inv.id}
                  href={`/sales/invoices/${inv.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-slate-border"
                >
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">
                      {inv.invoice_number || `Invoice #${inv.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {inv.customer_name || 'Unknown'} • {formatDate(inv.invoice_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(inv.total_amount || 0, inv.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{inv.status}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No invoices yet.</p>
          )}
        </div>

        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Payments</h3>
            </div>
            <Link href="/sales/payments" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentPayments?.payments?.length ? (
            <div className="space-y-2">
              {recentPayments.payments.map((pay: any) => (
                <Link
                  key={pay.id}
                  href={`/sales/payments/${pay.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-slate-border"
                >
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">
                      {pay.receipt_number || `Payment #${pay.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {pay.customer_name || 'Unknown'} • {formatDate(pay.payment_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(pay.amount || 0, pay.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{pay.status}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No payments yet.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Receipt className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Credit Notes</h3>
            </div>
            <Link href="/sales/credit-notes" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentCredits?.credit_notes?.length ? (
            <div className="space-y-2">
              {recentCredits.credit_notes.map((note: any) => (
                <Link
                  key={note.id}
                  href={`/sales/credit-notes/${note.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-slate-border"
                >
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">
                      {note.credit_number || `Credit #${note.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {note.customer_name || 'Unknown'} • {formatDate(note.issue_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(note.amount || 0, note.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{note.status}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No credit notes yet.</p>
          )}
        </div>

        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ShoppingCart className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Purchases</h3>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <Link href="/purchasing" className="text-teal-electric hover:text-teal-glow">Purchasing</Link>
              <span className="text-slate-muted">•</span>
              <Link href="/purchasing/payments" className="text-teal-electric hover:text-teal-glow">Payments</Link>
            </div>
          </div>
          {(recentBills?.bills?.length || recentPurchasePayments?.payments?.length) ? (
            <div className="space-y-3">
              {recentBills?.bills?.slice(0, 3).map((bill: any) => (
                <div key={`bill-${bill.id}`} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div>
                    <p className="text-white text-sm font-medium">Bill #{bill.id}</p>
                    <p className="text-xs text-slate-muted">
                      {bill.supplier_name || bill.supplier || 'Unknown'} • {formatDate(bill.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(bill.grand_total || 0, bill.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{bill.status}</p>
                  </div>
                </div>
              ))}
              {recentPurchasePayments?.payments?.slice(0, 2).map((pay: any) => (
                <div key={`pay-${pay.id}`} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div>
                    <p className="text-white text-sm font-medium">Payment #{pay.id}</p>
                    <p className="text-xs text-slate-muted">
                      {(pay as any).supplier || (pay as any).customer || 'Unknown'} • {formatDate((pay as any).posting_date || (pay as any).payment_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(pay.amount || 0, pay.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{pay.status}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No purchasing activity yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
