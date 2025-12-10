'use client';

import { Users, DollarSign, Headphones, Radio, AlertTriangle, TrendingDown, Clock } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import { Badge, StatusBadge } from '@/components/Badge';
import { RevenueChart, ChurnChart, PlanPieChart, PopChart } from '@/components/Charts';
import { DataTable } from '@/components/DataTable';
import {
  useOverview,
  useRevenueTrend,
  useChurnTrend,
  usePlanDistribution,
  usePopPerformance,
  useInvoiceAging,
} from '@/hooks/useApi';
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils';

export default function OverviewPage() {
  const { data: overview, isLoading: overviewLoading } = useOverview();
  const { data: revenueTrend } = useRevenueTrend(12);
  const { data: churnTrend } = useChurnTrend(12);
  const { data: planDistribution } = usePlanDistribution();
  const { data: popPerformance } = usePopPerformance();
  const { data: invoiceAging } = useInvoiceAging();

  const currency = overview?.revenue?.currency || 'NGN';

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-muted mt-1">
            Overview of Dotmac Technologies performance
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="success" pulse>
            Live Data
          </Badge>
          <span className="text-slate-muted text-sm font-mono">
            {new Date().toLocaleDateString('en-GB', {
              weekday: 'short',
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Total Customers"
          value={overview?.customers.total || 0}
          subtitle={`${overview?.customers.active || 0} active`}
          icon={Users}
          variant="default"
          loading={overviewLoading}
        />
        <StatCard
          title="Monthly Revenue"
          value={formatCurrency(overview?.revenue.mrr || 0, currency)}
          subtitle="MRR from subscriptions"
          icon={DollarSign}
          variant="success"
          loading={overviewLoading}
          animateValue={false}
        />
        <StatCard
          title="Open Tickets"
          value={overview?.support.open_tickets || 0}
          subtitle="Awaiting resolution"
          icon={Headphones}
          variant={overview?.support.open_tickets && overview.support.open_tickets > 10 ? 'warning' : 'default'}
          loading={overviewLoading}
        />
        <StatCard
          title="Active POPs"
          value={overview?.operations.pop_count || 0}
          subtitle="Network locations"
          icon={Radio}
          variant="default"
          loading={overviewLoading}
        />
      </div>

      {/* Alert Cards */}
      {overview && (overview.customers.churn_rate > 5 || overview.revenue.overdue_invoices > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {overview.customers.churn_rate > 5 && (
            <Card className="border-coral-alert/30 bg-coral-alert/5">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-coral-alert/20 flex items-center justify-center">
                  <TrendingDown className="w-5 h-5 text-coral-alert" />
                </div>
                <div>
                  <h3 className="font-semibold text-coral-alert">High Churn Rate</h3>
                  <p className="text-slate-muted text-sm mt-1">
                    {formatPercent(overview.customers.churn_rate)} of customers have churned.
                    {overview.customers.churned} total cancellations.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {overview.revenue.overdue_invoices > 0 && (
            <Card className="border-amber-warn/30 bg-amber-warn/5">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-amber-warn/20 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-amber-warn" />
                </div>
                <div>
                  <h3 className="font-semibold text-amber-warn">Overdue Invoices</h3>
                  <p className="text-slate-muted text-sm mt-1">
                    {overview.revenue.overdue_invoices} invoices are past due.
                    {invoiceAging && ` ${formatCurrency(invoiceAging.total_outstanding, currency)} outstanding.`}
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Revenue Trend</CardTitle>
              <CardDescription>Monthly payment collections</CardDescription>
            </div>
          </CardHeader>
          {revenueTrend ? (
            <RevenueChart data={revenueTrend} height={280} currency={currency} />
          ) : (
            <div className="h-[280px] skeleton rounded-lg" />
          )}
        </Card>

        {/* Churn Trend */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Churn Trend</CardTitle>
              <CardDescription>Monthly customer cancellations</CardDescription>
            </div>
          </CardHeader>
          {churnTrend ? (
            <ChurnChart data={churnTrend} height={280} />
          ) : (
            <div className="h-[280px] skeleton rounded-lg" />
          )}
        </Card>
      </div>

      {/* Secondary Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Plan Distribution */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Plan Distribution</CardTitle>
              <CardDescription>Customers by subscription plan</CardDescription>
            </div>
          </CardHeader>
          {planDistribution ? (
            <PlanPieChart data={planDistribution} height={260} />
          ) : (
            <div className="h-[260px] skeleton rounded-lg" />
          )}
        </Card>

        {/* Top POPs */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Top POPs by Revenue</CardTitle>
              <CardDescription>Network locations ranked by MRR</CardDescription>
            </div>
          </CardHeader>
          {popPerformance ? (
            <PopChart data={popPerformance} height={260} />
          ) : (
            <div className="h-[260px] skeleton rounded-lg" />
          )}
        </Card>
      </div>

      {/* Invoice Aging */}
      {invoiceAging && (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Invoice Aging</CardTitle>
              <CardDescription>Outstanding receivables by age</CardDescription>
            </div>
          </CardHeader>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: 'Current', key: 'current', variant: 'success' },
              { label: '1-30 Days', key: '1_30_days', variant: 'info' },
              { label: '31-60 Days', key: '31_60_days', variant: 'warning' },
              { label: '61-90 Days', key: '61_90_days', variant: 'warning' },
              { label: '90+ Days', key: 'over_90_days', variant: 'danger' },
            ].map(({ label, key, variant }) => {
              const bucket = invoiceAging.aging[key as keyof typeof invoiceAging.aging];
              return (
                <div
                  key={key}
                  className="bg-slate-elevated/50 rounded-lg p-4 border border-slate-border"
                >
                  <p className="text-slate-muted text-xs uppercase tracking-wide mb-2">{label}</p>
                  <p className="font-mono text-lg font-bold text-white">
                    {formatCurrency(bucket.amount, currency)}
                  </p>
                  <p className="text-slate-muted text-sm">
                    {bucket.count} invoice{bucket.count !== 1 ? 's' : ''}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* POP Performance Table */}
      {popPerformance && (
        <Card padding="none">
          <div className="p-6 border-b border-slate-border">
            <CardTitle>POP Performance</CardTitle>
            <CardDescription>Detailed metrics by network location</CardDescription>
          </div>
          <DataTable
            columns={[
              {
                key: 'name',
                header: 'POP Name',
                sortable: true,
                render: (item) => (
                  <span className="text-white font-medium font-body">{String(item.name)}</span>
                ),
              },
              {
                key: 'active_customers',
                header: 'Customers',
                sortable: true,
                align: 'right',
              },
              {
                key: 'mrr',
                header: 'MRR',
                sortable: true,
                align: 'right',
                render: (item) => (
                  <span className="text-teal-electric">{formatCurrency(item.mrr as number, currency)}</span>
                ),
              },
              {
                key: 'churn_rate',
                header: 'Churn Rate',
                sortable: true,
                align: 'right',
                render: (item) => {
                  const rate = item.churn_rate as number;
                  return (
                    <span className={rate > 5 ? 'text-coral-alert' : rate > 2 ? 'text-amber-warn' : 'text-slate-muted'}>
                      {formatPercent(rate)}
                    </span>
                  );
                },
              },
              {
                key: 'open_tickets',
                header: 'Open Tickets',
                sortable: true,
                align: 'right',
                render: (item) => {
                  const tickets = item.open_tickets as number;
                  return (
                    <span className={tickets > 5 ? 'text-amber-warn' : 'text-slate-muted'}>
                      {tickets}
                    </span>
                  );
                },
              },
              {
                key: 'outstanding',
                header: 'Outstanding',
                sortable: true,
                align: 'right',
                render: (item) => formatCurrency(item.outstanding as number, currency),
              },
            ]}
            data={popPerformance as unknown as Record<string, unknown>[]}
            keyField="id"
          />
        </Card>
      )}
    </div>
  );
}
