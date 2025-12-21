'use client';

import Link from 'next/link';
import { useConsolidatedSalesDashboard } from '@/hooks/useApi';
import type { SalesDashboardResponse } from '@/lib/api/domains/dashboards';
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
  Users,
  Activity,
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
  href?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, trend, trendValue, className, href }: StatCardProps) {
  const content = (
    <div className={cn(
      'bg-slate-card rounded-xl border border-slate-border p-6',
      href && 'hover:border-teal-electric/50 hover:bg-slate-elevated/50 transition-all cursor-pointer',
      className
    )}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-slate-muted text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
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

interface AgingBuckets {
  current: { count: number; total: number };
  '1_30': { count: number; total: number };
  '31_60': { count: number; total: number };
  '61_90': { count: number; total: number };
  over_90: { count: number; total: number };
}

function AgingChart({ buckets }: { buckets: AgingBuckets }) {
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
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-foreground">Invoice Aging</h3>
        <Link href="/sales/invoices?overdue_only=true" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
          View Overdue <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
      <div className="space-y-3">
        {entries.map((bucket) => {
          const amount = bucket.total || 0;
          const count = bucket.count || 0;
          const percent = total > 0 ? (amount / total) * 100 : 0;

          return (
            <div key={bucket.key}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-muted capitalize">{bucket.label}</span>
                <span className="text-foreground font-mono">
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
          <span className="text-foreground font-bold font-mono">{formatCurrency(total)}</span>
        </div>
      </div>
    </div>
  );
}

export default function SalesDashboardPage() {
  const currency = 'NGN';
  const { data, isLoading, error, mutate } = useConsolidatedSalesDashboard(currency);

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load sales dashboard data."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) {
    return <LoadingState />;
  }

  const { finance, aging, revenue_trend, recent, crm } = data;
  const collectionRate = finance?.collections?.collection_rate ?? 0;
  const outstandingTotal = finance?.outstanding?.total ?? 0;
  const overdueTotal = finance?.outstanding?.overdue ?? 0;
  const invoiced30d = finance?.collections?.invoiced_30_days ?? 0;
  const collected30d = finance?.collections?.last_30_days ?? 0;

  return (
    <div className="space-y-6">
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
          value={formatCurrency(crm?.pipeline?.total_value || 0, currency)}
          subtitle={`Weighted: ${formatCurrency(crm?.pipeline?.weighted_value || 0, currency)}`}
          icon={Target}
          href="/sales/pipeline"
        />
        <StatCard
          title="Open Opportunities"
          value={formatNumber(crm?.pipeline?.open_count || 0)}
          subtitle={`Win Rate: ${((crm?.pipeline?.win_rate || 0) * 100).toFixed(0)}%`}
          icon={TrendingUp}
          trend={(crm?.pipeline?.win_rate || 0) >= 0.3 ? 'up' : 'down'}
          trendValue={(crm?.pipeline?.win_rate || 0) >= 0.3 ? 'Above Target' : 'Below Target'}
          href="/sales/opportunities"
        />
        <StatCard
          title="Active Leads"
          value={formatNumber((crm?.leads?.new || 0) + (crm?.leads?.contacted || 0) + (crm?.leads?.qualified || 0))}
          subtitle={`New: ${crm?.leads?.new || 0} | Qualified: ${crm?.leads?.qualified || 0}`}
          icon={UserPlus}
          href="/sales/leads"
        />
        <StatCard
          title="Activities"
          value={formatNumber(crm?.upcoming_activities?.length || 0)}
          subtitle={crm?.overdue_activities?.length ? `${crm.overdue_activities.length} overdue` : 'All on track'}
          icon={Calendar}
          trend={crm?.overdue_activities?.length ? 'down' : 'up'}
          trendValue={crm?.overdue_activities?.length ? 'Action needed' : 'Healthy'}
          href="/sales/activities"
        />
      </div>

      {/* Pipeline Stages Overview */}
      {crm?.stages && crm.stages.length > 0 && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-foreground">Sales Pipeline</h3>
            <Link href="/sales/pipeline" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Pipeline <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {crm.stages.filter((s) => !s.is_won && !s.is_lost).map((stage) => (
              <Link
                key={stage.id}
                href={`/sales/opportunities?stage=${stage.id}`}
                className="bg-slate-elevated/50 rounded-lg p-3 border border-slate-border/50 hover:border-teal-electric/50 transition-all"
              >
                <div className="text-xs text-slate-muted mb-1">{stage.name}</div>
                <div className="text-lg font-semibold text-foreground">{stage.opportunity_count}</div>
                <div className="text-xs text-teal-electric">{formatCurrency(stage.opportunity_value || 0, currency)}</div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Key AR Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Monthly Recurring Revenue"
          value={formatCurrency(finance?.revenue?.mrr || 0, currency)}
          subtitle={`ARR: ${formatCurrency(finance?.revenue?.arr || 0, currency)}`}
          icon={TrendingUp}
          href="/sales/subscriptions"
        />
        <StatCard
          title="Invoiced (30d)"
          value={formatCurrency(invoiced30d, currency)}
          subtitle="Last 30 days"
          icon={FileText}
          href="/sales/invoices"
        />
        <StatCard
          title="Collected (30d)"
          value={formatCurrency(collected30d, currency)}
          subtitle={`Collection Rate: ${(collectionRate * 100).toFixed(1)}%`}
          icon={CreditCard}
          trend={collectionRate >= 0.8 ? 'up' : 'down'}
          trendValue={collectionRate >= 0.8 ? 'Healthy' : 'Below Target'}
          href="/sales/payments"
        />
        <StatCard
          title="Outstanding"
          value={formatCurrency(outstandingTotal, currency)}
          subtitle={`Overdue: ${formatCurrency(overdueTotal, currency)}`}
          icon={Clock}
          href="/sales/invoices?status=overdue"
        />
      </div>

      {/* DSO and Collection Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link href="/sales/analytics" className="block">
          <div className="bg-slate-card rounded-xl border border-slate-border p-6 hover:border-teal-electric/50 transition-all">
            <h3 className="text-lg font-semibold text-foreground mb-4">Days Sales Outstanding (DSO)</h3>
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <p className="text-5xl font-bold text-teal-electric">{finance?.metrics?.dso?.toFixed(0) || '-'}</p>
                <p className="text-slate-muted mt-2">days</p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-slate-border">
              <div className="flex items-center justify-center gap-4 text-sm">
                {(finance?.metrics?.dso || 0) <= 30 ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="text-green-400">Excellent - Below 30 days</span>
                  </>
                ) : (finance?.metrics?.dso || 0) <= 45 ? (
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
        </Link>

        <AgingChart buckets={aging?.buckets as AgingBuckets} />
      </div>

      {/* Revenue Trend */}
      {revenue_trend && revenue_trend.length > 0 && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-foreground">Revenue Trend (6 Months)</h3>
            <Link href="/sales/analytics" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Analytics <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
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
                {revenue_trend.slice(-6).map((item, i: number) => (
                  <tr key={i} className="border-b border-slate-border/50 hover:bg-slate-elevated/30">
                    <td className="py-3 px-2 text-foreground">{item.period}</td>
                    <td className="py-3 px-2 text-right font-mono text-foreground">{formatCurrency(item.revenue, currency)}</td>
                    <td className="py-3 px-2 text-right font-mono text-teal-electric">{(item.payment_count ?? 0).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sales quick lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold text-sm">Recent Invoices</h3>
            </div>
            <Link href="/sales/invoices" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.invoices?.length ? (
            <div className="space-y-2">
              {recent.invoices.map((inv) => (
                <Link
                  key={inv.id}
                  href={`/sales/invoices/${inv.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">
                      {inv.invoice_number || `Invoice #${inv.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {inv.customer_name || 'Unknown'} • {formatDate(inv.invoice_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(inv.total_amount || 0, inv.currency || currency)}</p>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Payments</h3>
            </div>
            <Link href="/sales/payments" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.payments?.length ? (
            <div className="space-y-2">
              {recent.payments.map((pay) => (
                <Link
                  key={pay.id}
                  href={`/sales/payments/${pay.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">
                      {pay.receipt_number || `Payment #${pay.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {pay.customer_name || 'Unknown'} • {formatDate(pay.payment_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(pay.amount || 0, pay.currency || currency)}</p>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Credit Notes</h3>
            </div>
            <Link href="/sales/credit-notes" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.credit_notes?.length ? (
            <div className="space-y-2">
              {recent.credit_notes.map((note) => (
                <Link
                  key={note.id}
                  href={`/sales/credit-notes/${note.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">
                      {note.credit_number || `Credit #${note.id}`}
                    </p>
                    <p className="text-xs text-slate-muted">
                      {note.customer_name || 'Unknown'} • {formatDate(note.issue_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(note.amount || 0, note.currency || currency)}</p>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Purchases</h3>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <Link href="/purchasing" className="text-teal-electric hover:text-teal-glow">Purchasing</Link>
              <span className="text-slate-muted">•</span>
              <Link href="/purchasing/payments" className="text-teal-electric hover:text-teal-glow">Payments</Link>
            </div>
          </div>
          {(recent?.bills?.length || recent?.purchase_payments?.length) ? (
            <div className="space-y-3">
              {recent?.bills?.slice(0, 3).map((bill) => (
                <Link
                  key={`bill-${bill.id}`}
                  href={`/purchasing/bills/${bill.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div>
                    <p className="text-foreground text-sm font-medium">Bill #{bill.id}</p>
                    <p className="text-xs text-slate-muted">
                      {bill.supplier_name || 'Unknown'} • {formatDate(bill.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(bill.grand_total || 0, bill.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{bill.status}</p>
                  </div>
                </Link>
              ))}
              {recent?.purchase_payments?.slice(0, 2).map((pay) => (
                <div key={`pay-${pay.id}`} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div>
                    <p className="text-foreground text-sm font-medium">Payment #{pay.id}</p>
                    <p className="text-xs text-slate-muted">
                      {pay.supplier || 'Unknown'} • {formatDate(pay.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(pay.amount || 0, currency)}</p>
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
