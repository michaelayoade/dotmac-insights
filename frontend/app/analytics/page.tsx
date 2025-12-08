'use client';

import { useState } from 'react';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Calendar,
  Users,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import { Badge } from '@/components/Badge';
import { RevenueChart, ChurnChart } from '@/components/Charts';
import { DataTable } from '@/components/DataTable';
import {
  useOverview,
  useRevenueTrend,
  useChurnTrend,
  useInvoiceAging,
  useChurnRisk,
} from '@/hooks/useApi';
import { formatCurrency, formatNumber, formatPercent, formatDate, cn } from '@/lib/utils';

type TimeRange = 6 | 12 | 24;

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>(12);
  const { data: overview, isLoading: overviewLoading } = useOverview();
  const { data: revenueTrend } = useRevenueTrend(timeRange);
  const { data: churnTrend } = useChurnTrend(timeRange);
  const { data: invoiceAging } = useInvoiceAging();
  const { data: churnRisk } = useChurnRisk(20);

  const currency = overview?.revenue?.currency || 'NGN';

  // Calculate revenue growth from trend data
  const revenueGrowth = revenueTrend && revenueTrend.length >= 2
    ? ((revenueTrend[revenueTrend.length - 1].total - revenueTrend[revenueTrend.length - 2].total) /
        revenueTrend[revenueTrend.length - 2].total) * 100
    : 0;

  // Calculate average monthly churn
  const avgChurn = churnTrend && churnTrend.length > 0
    ? churnTrend.reduce((sum, m) => sum + m.churned, 0) / churnTrend.length
    : 0;

  // Calculate total churned in period
  const totalChurned = churnTrend?.reduce((sum, m) => sum + m.churned, 0) || 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Analytics</h1>
          <p className="text-slate-muted mt-1">
            Revenue trends and churn analysis
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-2 bg-slate-elevated rounded-lg p-1">
          {([6, 12, 24] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-md transition-all',
                timeRange === range
                  ? 'bg-teal-electric/20 text-teal-electric'
                  : 'text-slate-muted hover:text-white'
              )}
            >
              {range}M
            </button>
          ))}
        </div>
      </div>

      {/* Key Revenue Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Monthly Revenue"
          value={formatCurrency(overview?.revenue.mrr || 0, currency)}
          subtitle="Current MRR"
          icon={DollarSign}
          variant="success"
          loading={overviewLoading}
          animateValue={false}
        />
        <StatCard
          title="Revenue Growth"
          value={formatPercent(Math.abs(revenueGrowth))}
          subtitle={revenueGrowth >= 0 ? 'Month over month' : 'Month over month decline'}
          icon={revenueGrowth >= 0 ? TrendingUp : TrendingDown}
          variant={revenueGrowth >= 0 ? 'success' : 'danger'}
          loading={!revenueTrend}
          animateValue={false}
        />
        <StatCard
          title="Avg Monthly Churn"
          value={avgChurn.toFixed(1)}
          subtitle={`${totalChurned} total in ${timeRange}M`}
          icon={TrendingDown}
          variant={avgChurn > 5 ? 'danger' : avgChurn > 2 ? 'warning' : 'default'}
          loading={!churnTrend}
        />
        <StatCard
          title="Outstanding"
          value={formatCurrency(invoiceAging?.total_outstanding || 0, currency)}
          subtitle={`${overview?.revenue.overdue_invoices || 0} overdue invoices`}
          icon={AlertTriangle}
          variant={(invoiceAging?.total_outstanding || 0) > 0 ? 'warning' : 'default'}
          loading={!invoiceAging}
          animateValue={false}
        />
      </div>

      {/* Revenue Analysis */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Revenue Trend Chart */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Revenue Trend</CardTitle>
                <CardDescription>Monthly payment collections over {timeRange} months</CardDescription>
              </div>
              {revenueTrend && revenueTrend.length >= 2 && (
                <div className={cn(
                  'flex items-center gap-1 text-sm font-mono',
                  revenueGrowth >= 0 ? 'text-teal-electric' : 'text-coral-alert'
                )}>
                  {revenueGrowth >= 0 ? (
                    <ArrowUpRight className="w-4 h-4" />
                  ) : (
                    <ArrowDownRight className="w-4 h-4" />
                  )}
                  {formatPercent(Math.abs(revenueGrowth))}
                </div>
              )}
            </div>
          </CardHeader>
          {revenueTrend ? (
            <RevenueChart data={revenueTrend} height={320} currency={currency} />
          ) : (
            <div className="h-[320px] skeleton rounded-lg" />
          )}
        </Card>

        {/* Invoice Aging Breakdown */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Invoice Aging</CardTitle>
              <CardDescription>Outstanding receivables by age</CardDescription>
            </div>
          </CardHeader>
          {invoiceAging ? (
            <div className="space-y-3">
              {[
                { label: 'Current', key: 'current', color: 'bg-teal-electric' },
                { label: '1-30 Days', key: '1_30_days', color: 'bg-blue-500' },
                { label: '31-60 Days', key: '31_60_days', color: 'bg-amber-warn' },
                { label: '61-90 Days', key: '61_90_days', color: 'bg-orange-500' },
                { label: '90+ Days', key: 'over_90_days', color: 'bg-coral-alert' },
              ].map(({ label, key, color }) => {
                const bucket = invoiceAging.aging[key as keyof typeof invoiceAging.aging];
                const percentage = invoiceAging.total_outstanding > 0
                  ? (bucket.amount / invoiceAging.total_outstanding) * 100
                  : 0;

                return (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-muted">{label}</span>
                      <div className="text-right">
                        <span className="text-white font-mono">
                          {formatCurrency(bucket.amount, currency)}
                        </span>
                        <span className="text-slate-muted ml-2">
                          ({bucket.count})
                        </span>
                      </div>
                    </div>
                    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all duration-500', color)}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}

              <div className="pt-4 mt-4 border-t border-slate-border">
                <div className="flex items-center justify-between">
                  <span className="text-white font-semibold">Total Outstanding</span>
                  <span className="text-amber-warn font-mono font-bold">
                    {formatCurrency(invoiceAging.total_outstanding, currency)}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton h-8 rounded" />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Churn Analysis */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Churn Trend Chart */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Churn Trend</CardTitle>
              <CardDescription>Monthly customer cancellations</CardDescription>
            </div>
          </CardHeader>
          {churnTrend ? (
            <ChurnChart data={churnTrend} height={300} />
          ) : (
            <div className="h-[300px] skeleton rounded-lg" />
          )}
        </Card>

        {/* Churn Risk Table */}
        <Card padding="none">
          <div className="p-6 border-b border-slate-border">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Churn Risk</CardTitle>
                <CardDescription>Customers at risk of churning</CardDescription>
              </div>
              {churnRisk && (
                <Badge variant={churnRisk.length > 10 ? 'danger' : 'warning'}>
                  {churnRisk.length} at risk
                </Badge>
              )}
            </div>
          </div>
          <DataTable
            columns={[
              {
                key: 'name',
                header: 'Customer',
                render: (item) => (
                  <div>
                    <p className="text-white font-medium font-body">{item.name as string}</p>
                    <p className="text-slate-muted text-xs">{item.account_number || '—'}</p>
                  </div>
                ),
              },
              {
                key: 'risk_score',
                header: 'Risk',
                align: 'right',
                render: (item) => {
                  const score = item.risk_score as number;
                  return (
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-2 bg-slate-elevated rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            score > 80 ? 'bg-coral-alert' : score > 50 ? 'bg-amber-warn' : 'bg-teal-electric'
                          )}
                          style={{ width: `${score}%` }}
                        />
                      </div>
                      <span className={cn(
                        'font-mono text-sm w-10 text-right',
                        score > 80 ? 'text-coral-alert' : score > 50 ? 'text-amber-warn' : 'text-slate-muted'
                      )}>
                        {score}%
                      </span>
                    </div>
                  );
                },
              },
              {
                key: 'risk_factors',
                header: 'Factors',
                render: (item) => {
                  const factors = item.risk_factors as string[];
                  return (
                    <div className="flex flex-wrap gap-1">
                      {factors.slice(0, 2).map((factor, i) => (
                        <Badge key={i} variant="muted" size="sm">
                          {factor}
                        </Badge>
                      ))}
                      {factors.length > 2 && (
                        <Badge variant="muted" size="sm">
                          +{factors.length - 2}
                        </Badge>
                      )}
                    </div>
                  );
                },
              },
            ]}
            data={(churnRisk || []) as Record<string, unknown>[]}
            keyField="id"
            loading={!churnRisk}
            emptyMessage="No customers at risk"
          />
        </Card>
      </div>

      {/* Revenue Breakdown Summary */}
      {overview && (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Revenue Summary</CardTitle>
              <CardDescription>Financial metrics at a glance</CardDescription>
            </div>
          </CardHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
              <p className="text-slate-muted text-sm mb-2">Active Customers</p>
              <p className="text-3xl font-bold font-mono text-white">
                {formatNumber(overview.customers.active)}
              </p>
              <p className="text-slate-muted text-xs mt-1">
                of {formatNumber(overview.customers.total)} total
              </p>
            </div>

            <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
              <p className="text-slate-muted text-sm mb-2">MRR</p>
              <p className="text-3xl font-bold font-mono text-teal-electric">
                {formatCurrency(overview.revenue.mrr, currency)}
              </p>
              <p className="text-slate-muted text-xs mt-1">
                Monthly recurring
              </p>
            </div>

            <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
              <p className="text-slate-muted text-sm mb-2">Churn Rate</p>
              <p className={cn(
                'text-3xl font-bold font-mono',
                overview.customers.churn_rate > 5 ? 'text-coral-alert' :
                overview.customers.churn_rate > 2 ? 'text-amber-warn' : 'text-white'
              )}>
                {formatPercent(overview.customers.churn_rate)}
              </p>
              <p className="text-slate-muted text-xs mt-1">
                {overview.customers.churned} churned
              </p>
            </div>

            <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
              <p className="text-slate-muted text-sm mb-2">ARPU</p>
              <p className="text-3xl font-bold font-mono text-white">
                {overview.customers.active > 0
                  ? formatCurrency(overview.revenue.mrr / overview.customers.active, currency)
                  : formatCurrency(0, currency)}
              </p>
              <p className="text-slate-muted text-xs mt-1">
                Avg revenue per user
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
