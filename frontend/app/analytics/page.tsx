'use client';

import { useState, useMemo } from 'react';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Users,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  ShoppingCart,
  Headphones,
  CheckCircle,
  XCircle,
  Server,
  MapPin,
  Wallet,
  Activity,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import { Badge } from '@/components/Badge';
import { DateRangePicker, DateRange } from '@/components/DateRangePicker';
import {
  RevenueChart,
  ChurnChart,
  DSOChart,
  SLAGauge,
  FunnelChart,
  AgentBarChart,
  ExpenseTrendChart,
} from '@/components/Charts';
import { DataTable } from '@/components/DataTable';
import {
  useOverview,
  useRevenueTrend,
  useChurnTrend,
  useInvoiceAging,
  useChurnRisk,
  useDSOTrend,
  useSalesPipeline,
  useSLAAttainment,
  useAgentProductivity,
  useAgingBySegment,
  useRevenueByTerritory,
  useQuotationTrend,
  useTicketsByType,
  useNetworkDeviceStatus,
  useIPUtilization,
  useExpensesByCategory,
  useVendorSpend,
  useExpenseTrend,
} from '@/hooks/useApi';
import { formatCurrency, formatNumber, formatPercent, cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

type TimeRange = 6 | 12 | 24;
type ActiveTab = 'revenue' | 'sales' | 'support' | 'collections' | 'operations';

function formatDateParam(date: Date | null): string | undefined {
  if (!date) return undefined;
  return date.toISOString().split('T')[0];
}

export default function AnalyticsPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');

  // All hooks must be called before any conditional returns
  const [timeRange, setTimeRange] = useState<TimeRange>(12);
  const [activeTab, setActiveTab] = useState<ActiveTab>('revenue');
  const [dateRange, setDateRange] = useState<DateRange>({ startDate: null, endDate: null });

  // Date params for API calls
  const startDateStr = formatDateParam(dateRange.startDate);
  const endDateStr = formatDateParam(dateRange.endDate);

  // Core data
  const { data: overview, isLoading: overviewLoading } = useOverview();
  const { data: revenueTrend } = useRevenueTrend(timeRange, startDateStr, endDateStr);
  const { data: churnTrend } = useChurnTrend(timeRange, startDateStr, endDateStr);
  const { data: invoiceAging } = useInvoiceAging();
  const { data: churnRisk } = useChurnRisk(20);

  // New analytics data
  const { data: dsoData } = useDSOTrend(timeRange, startDateStr, endDateStr);
  const { data: pipelineData } = useSalesPipeline();
  const { data: slaData } = useSLAAttainment(30);
  const { data: agentData } = useAgentProductivity(30);
  const { data: agingBySegment } = useAgingBySegment();
  const { data: revenueByTerritory } = useRevenueByTerritory(timeRange, startDateStr, endDateStr);
  const { data: quotationTrend } = useQuotationTrend(timeRange, startDateStr, endDateStr);
  const { data: ticketsByType } = useTicketsByType(30);
  const { data: networkStatus } = useNetworkDeviceStatus();
  const { data: ipUtilization } = useIPUtilization();
  const { data: expensesByCategory } = useExpensesByCategory(timeRange, startDateStr, endDateStr);
  const { data: vendorSpend } = useVendorSpend(timeRange, 10, startDateStr, endDateStr);
  const { data: expenseTrend } = useExpenseTrend(timeRange, startDateStr, endDateStr);

  // Auth loading state - after all hooks
  if (authLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric" />
      </div>
    );
  }

  // Access denied state
  if (!hasAccess) {
    return <AccessDenied />;
  }

  const currency = overview?.revenue?.currency || 'NGN';
  const latestExpense = expenseTrend?.[expenseTrend.length - 1]?.total || 0;
  const uptime = networkStatus?.summary.uptime_percent || 0;
  const ipOverall = ipUtilization?.summary.overall_utilization || 0;
  const topVendor = vendorSpend?.vendors?.[0];

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

  // Prepare funnel data
  const funnelData = pipelineData ? [
    { name: 'Quotations', value: pipelineData.quotations.total, fill: '#3b82f6' },
    { name: 'Orders', value: pipelineData.orders.total, fill: '#00d4aa' },
    { name: 'Completed', value: pipelineData.conversion.orders_completed, fill: '#a855f7' },
  ] : [];

  const tabs = [
    { id: 'revenue' as const, label: 'Revenue', icon: DollarSign },
    { id: 'sales' as const, label: 'Sales Pipeline', icon: ShoppingCart },
    { id: 'support' as const, label: 'Support/SLA', icon: Headphones },
    { id: 'collections' as const, label: 'Collections', icon: AlertTriangle },
    { id: 'operations' as const, label: 'Operations', icon: Server },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Analytics</h1>
          <p className="text-slate-muted mt-1">
            Business intelligence and performance metrics
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Date Range Picker */}
          <DateRangePicker
            value={dateRange}
            onChange={setDateRange}
          />

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
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Days Sales Outstanding"
          value={dsoData ? `${dsoData.current_dso.toFixed(1)} days` : '—'}
          subtitle={dsoData ? `Avg: ${dsoData.average_dso.toFixed(1)} days` : 'Loading...'}
          icon={Clock}
          variant={dsoData && dsoData.current_dso > 90 ? 'danger' : dsoData && dsoData.current_dso > 60 ? 'warning' : 'default'}
          loading={!dsoData}
          animateValue={false}
        />
        <StatCard
          title="SLA Attainment"
          value={slaData ? formatPercent(slaData.sla_attainment.rate) : '—'}
          subtitle={slaData ? `${slaData.sla_attainment.met} met / ${slaData.total_tickets} total` : 'Loading...'}
          icon={slaData && slaData.sla_attainment.rate >= 90 ? CheckCircle : XCircle}
          variant={slaData && slaData.sla_attainment.rate >= 90 ? 'success' : slaData && slaData.sla_attainment.rate >= 70 ? 'warning' : 'danger'}
          loading={!slaData}
          animateValue={false}
        />
        <StatCard
          title="Pipeline Conversion"
          value={pipelineData ? formatPercent(pipelineData.conversion.quotation_to_order_rate) : '—'}
          subtitle={pipelineData ? `${pipelineData.quotations.total} quotations` : 'Loading...'}
          icon={ShoppingCart}
          variant={pipelineData && pipelineData.conversion.quotation_to_order_rate >= 30 ? 'success' : 'warning'}
          loading={!pipelineData}
          animateValue={false}
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

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 bg-slate-elevated rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all',
              activeTab === tab.id
                ? 'bg-slate-card text-white'
                : 'text-slate-muted hover:text-white'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'revenue' && (
        <div className="space-y-6">
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

            {/* DSO Trend */}
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>DSO Trend</CardTitle>
                  <CardDescription>Days Sales Outstanding over time</CardDescription>
                </div>
              </CardHeader>
              {dsoData ? (
                <DSOChart data={dsoData.trend} height={320} avgDSO={dsoData.average_dso} />
              ) : (
                <div className="h-[320px] skeleton rounded-lg" />
              )}
            </Card>
          </div>

          {/* Revenue by Territory */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Revenue by Territory</CardTitle>
                  <CardDescription>MRR distribution across territories</CardDescription>
                </div>
                {revenueByTerritory && (
                  <Badge variant="default">{revenueByTerritory.length} territories</Badge>
                )}
              </div>
            </CardHeader>
            <DataTable
              columns={[
                { key: 'territory', header: 'Territory', render: (item) => String(item.territory || 'Unassigned') },
                { key: 'customer_count', header: 'Customers', align: 'right', sortable: true },
                {
                  key: 'mrr',
                  header: 'MRR',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatCurrency(item.mrr as number, currency),
                },
              ]}
              data={(revenueByTerritory || []) as unknown as Record<string, unknown>[]}
              keyField="territory"
              loading={!revenueByTerritory}
              emptyMessage="No territory data"
            />
          </Card>

          {/* Churn Analysis */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Churn Trend Chart */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Churn Trend</CardTitle>
                    <CardDescription>Monthly customer cancellations</CardDescription>
                  </div>
                  <Badge variant={avgChurn > 5 ? 'danger' : avgChurn > 2 ? 'warning' : 'success'}>
                    Avg: {avgChurn.toFixed(1)}/mo
                  </Badge>
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
                    <Badge variant={(churnRisk.summary.overdue_customers + churnRisk.summary.suspended_customers) > 10 ? 'danger' : 'warning'}>
                      {churnRisk.summary.overdue_customers + churnRisk.summary.suspended_customers} at risk
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
                        <p className="text-slate-muted text-xs">{String(item.account_number || '—')}</p>
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
                ]}
                data={(churnRisk?.customers || []) as unknown as Record<string, unknown>[]}
                keyField="id"
                loading={!churnRisk}
                emptyMessage="No customers at risk"
              />
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'sales' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Sales Funnel */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Sales Pipeline Funnel</CardTitle>
                    <CardDescription>Quotation to completion conversion</CardDescription>
                  </div>
                  {pipelineData && (
                    <Badge variant="success">
                      {formatPercent(pipelineData.conversion.quotation_to_order_rate)} conversion
                    </Badge>
                  )}
                </div>
              </CardHeader>
              {pipelineData ? (
                <FunnelChart data={funnelData} height={250} />
              ) : (
                <div className="h-[250px] skeleton rounded-lg" />
              )}
            </Card>

            {/* Pipeline Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Pipeline Summary</CardTitle>
                <CardDescription>Current quotation and order status</CardDescription>
              </CardHeader>
              {pipelineData ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-elevated/50 rounded-lg text-center">
                      <p className="text-slate-muted text-sm mb-1">Total Quotations</p>
                      <p className="text-2xl font-bold font-mono text-white">
                        {pipelineData.quotations.total.toLocaleString()}
                      </p>
                      <p className="text-teal-electric text-sm font-mono">
                        {formatCurrency(pipelineData.quotations.total_value, currency)}
                      </p>
                    </div>
                    <div className="p-4 bg-slate-elevated/50 rounded-lg text-center">
                      <p className="text-slate-muted text-sm mb-1">Total Orders</p>
                      <p className="text-2xl font-bold font-mono text-white">
                        {pipelineData.orders.total.toLocaleString()}
                      </p>
                      <p className="text-teal-electric text-sm font-mono">
                        {formatCurrency(pipelineData.orders.total_value, currency)}
                      </p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-border">
                    <h4 className="text-sm font-medium text-white mb-3">Quotations by Status</h4>
                    <div className="space-y-2">
                      {Object.entries(pipelineData.quotations.by_status).map(([status, data]) => (
                        <div key={status} className="flex items-center justify-between text-sm">
                          <span className="text-slate-muted capitalize">{status.replace(/_/g, ' ')}</span>
                          <div className="text-right">
                            <span className="text-white font-mono">{data.count}</span>
                            <span className="text-slate-muted ml-2">
                              ({formatCurrency(data.value, currency)})
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="skeleton h-8 rounded" />
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Quotation Trend */}
          <Card>
            <CardHeader>
              <CardTitle>Quotation Trend</CardTitle>
              <CardDescription>Monthly quotations, conversions, and losses</CardDescription>
            </CardHeader>
            <DataTable
              columns={[
                { key: 'period', header: 'Period' },
                { key: 'total', header: 'Total', align: 'right', sortable: true },
                { key: 'converted', header: 'Converted', align: 'right', sortable: true },
                { key: 'lost', header: 'Lost', align: 'right', sortable: true },
                {
                  key: 'conversion_rate',
                  header: 'Conversion',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatPercent(item.conversion_rate as number),
                },
                {
                  key: 'value',
                  header: 'Value',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatCurrency(item.value as number, currency),
                },
              ]}
              data={(quotationTrend || []) as unknown as Record<string, unknown>[]}
              keyField="period"
              loading={!quotationTrend}
              emptyMessage="No quotation history"
            />
          </Card>
        </div>
      )}

      {activeTab === 'support' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* SLA Gauge */}
            <Card>
              <CardHeader>
                <CardTitle>SLA Performance</CardTitle>
                <CardDescription>Last 30 days SLA attainment</CardDescription>
              </CardHeader>
              {slaData ? (
                <div className="flex flex-col items-center py-4">
                  <SLAGauge value={slaData.sla_attainment.rate} size={220} />
                  <div className="grid grid-cols-2 gap-8 mt-6 w-full">
                    <div className="text-center">
                      <p className="text-teal-electric text-2xl font-bold font-mono">
                        {slaData.sla_attainment.met}
                      </p>
                      <p className="text-slate-muted text-sm">Met</p>
                    </div>
                    <div className="text-center">
                      <p className="text-coral-alert text-2xl font-bold font-mono">
                        {slaData.sla_attainment.breached}
                      </p>
                      <p className="text-slate-muted text-sm">Breached</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-[300px] skeleton rounded-lg" />
              )}
            </Card>

            {/* Response Times */}
            <Card>
              <CardHeader>
                <CardTitle>Response Metrics</CardTitle>
                <CardDescription>Average resolution times</CardDescription>
              </CardHeader>
              {slaData ? (
                <div className="space-y-6 py-4">
                  <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
                    <p className="text-slate-muted text-sm mb-1">Avg Response Time</p>
                    <p className="text-3xl font-bold font-mono text-amber-warn">
                      {slaData.avg_response_hours.toFixed(1)}h
                    </p>
                  </div>
                  <div className="text-center p-4 bg-slate-elevated/50 rounded-lg">
                    <p className="text-slate-muted text-sm mb-1">Avg Resolution Time</p>
                    <p className="text-3xl font-bold font-mono text-teal-electric">
                      {slaData.avg_resolution_hours.toFixed(1)}h
                    </p>
                  </div>
                  <div className="pt-4 border-t border-slate-border">
                    <p className="text-slate-muted text-sm mb-3">Total Tickets: <span className="text-white font-mono">{slaData.total_tickets.toLocaleString()}</span></p>
                    <p className="text-slate-muted text-sm">Period: <span className="text-white">{slaData.period_days} days</span></p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="skeleton h-16 rounded" />
                  ))}
                </div>
              )}
            </Card>

            {/* Agent Productivity */}
            <Card>
              <CardHeader>
                <CardTitle>Agent Productivity</CardTitle>
                <CardDescription>Tickets resolved by agent</CardDescription>
              </CardHeader>
              {agentData ? (
                <AgentBarChart data={agentData} height={300} />
              ) : (
                <div className="h-[300px] skeleton rounded-lg" />
              )}
            </Card>
          </div>

          {/* Ticket Mix */}
          <Card>
            <CardHeader>
              <CardTitle>Tickets by Type</CardTitle>
              <CardDescription>Distribution of ticket categories and resolution rates</CardDescription>
            </CardHeader>
            <DataTable
              columns={[
                { key: 'type', header: 'Type' },
                { key: 'count', header: 'Tickets', align: 'right', sortable: true },
                { key: 'resolved', header: 'Resolved', align: 'right', sortable: true },
                {
                  key: 'resolution_rate',
                  header: 'Resolution Rate',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatPercent(item.resolution_rate as number),
                },
              ]}
              data={(ticketsByType?.by_type || []) as unknown as Record<string, unknown>[]}
              keyField="type"
              loading={!ticketsByType}
              emptyMessage="No ticket distribution data"
            />
          </Card>
        </div>
      )}

      {activeTab === 'collections' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
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

            {/* Aging by Segment */}
            <Card>
              <CardHeader>
                <CardTitle>Aging by Customer Segment</CardTitle>
                <CardDescription>Outstanding amounts by customer type</CardDescription>
              </CardHeader>
              {agingBySegment ? (
                <div className="space-y-4">
                  {Object.entries(agingBySegment.by_segment).map(([segment, data]) => (
                    <div key={segment} className="p-4 bg-slate-elevated/50 rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-white font-medium capitalize">{segment}</span>
                        <span className="text-amber-warn font-mono font-bold">
                          {formatCurrency(data.total.amount, currency)}
                        </span>
                      </div>
                      <div className="grid grid-cols-5 gap-2 text-xs">
                        {[
                          { key: 'current', label: 'Current', color: 'text-teal-electric' },
                          { key: '1_30_days', label: '1-30d', color: 'text-blue-400' },
                          { key: '31_60_days', label: '31-60d', color: 'text-amber-warn' },
                          { key: '61_90_days', label: '61-90d', color: 'text-orange-400' },
                          { key: 'over_90_days', label: '90+d', color: 'text-coral-alert' },
                        ].map(({ key, label, color }) => {
                          const bucket = data[key as keyof typeof data] as { count: number; amount: number };
                          return (
                            <div key={key} className="text-center">
                              <p className="text-slate-muted">{label}</p>
                              <p className={cn('font-mono', color)}>
                                {formatCurrency(bucket.amount, currency)}
                              </p>
                              <p className="text-slate-muted">({bucket.count})</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}

                  <div className="pt-4 border-t border-slate-border">
                    <div className="flex items-center justify-between">
                      <span className="text-white font-semibold">Total Outstanding</span>
                      <span className="text-amber-warn font-mono font-bold">
                        {formatCurrency(agingBySegment.total_outstanding, currency)}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="skeleton h-24 rounded" />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'operations' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard
              title="Network Uptime"
              value={networkStatus ? formatPercent(uptime) : '—'}
              subtitle={networkStatus ? `${networkStatus.summary.up} up / ${networkStatus.summary.down} down` : 'Monitoring devices'}
              icon={Server}
              variant={uptime >= 95 ? 'success' : uptime >= 85 ? 'warning' : 'danger'}
              loading={!networkStatus}
              animateValue={false}
            />
            <StatCard
              title="IP Pool Utilization"
              value={ipUtilization ? formatPercent(ipOverall) : '—'}
              subtitle={ipUtilization ? `${ipUtilization.summary.total_used} / ${ipUtilization.summary.total_capacity} addresses` : 'Calculating pools'}
              icon={MapPin}
              variant={ipOverall <= 70 ? 'success' : ipOverall <= 85 ? 'warning' : 'danger'}
              loading={!ipUtilization}
              animateValue={false}
            />
            <StatCard
              title="Monthly Expense Run-Rate"
              value={formatCurrency(latestExpense, currency)}
              subtitle={`${timeRange}M window`}
              icon={Wallet}
              variant="default"
              loading={!expenseTrend}
              animateValue={false}
            />
            <StatCard
              title="Top Vendor"
              value={topVendor ? formatCurrency(topVendor.total_spend, currency) : '—'}
              subtitle={topVendor ? (topVendor.supplier_name || topVendor.supplier || 'Vendor') : 'Waiting for data'}
              icon={Activity}
              variant="default"
              loading={!vendorSpend}
              animateValue={false}
            />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Network Health</CardTitle>
                    <CardDescription>Uptime by monitored location</CardDescription>
                  </div>
                  {networkStatus && (
                    <Badge variant="default">{networkStatus.summary.total} devices</Badge>
                  )}
                </div>
              </CardHeader>
              <DataTable
                columns={[
                  {
                    key: 'location_id',
                    header: 'Location',
                    render: (item) => `Location ${item.location_id}`,
                  },
                  { key: 'total', header: 'Devices', align: 'right', sortable: true },
                  { key: 'up', header: 'Up', align: 'right', sortable: true },
                  { key: 'down', header: 'Down', align: 'right', sortable: true },
                  {
                    key: 'uptime',
                    header: 'Uptime',
                    align: 'right',
                    render: (item) => {
                      const total = (item.total as number) || 0;
                      const up = (item.up as number) || 0;
                      const rate = total > 0 ? (up / total) * 100 : 0;
                      return (
                        <span className={cn(
                          'font-mono text-sm',
                          rate >= 95 ? 'text-teal-electric' : rate >= 85 ? 'text-amber-warn' : 'text-coral-alert'
                        )}>
                          {formatPercent(rate)}
                        </span>
                      );
                    },
                  },
                ]}
                data={(networkStatus?.by_location || []) as unknown as Record<string, unknown>[]}
                keyField="location_id"
                loading={!networkStatus}
                emptyMessage="No network monitoring data"
              />
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>IP Utilization</CardTitle>
                    <CardDescription>Top address pools by usage</CardDescription>
                  </div>
                  {ipUtilization && (
                    <Badge variant="default">
                      {ipUtilization.summary.total_networks} pools
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <DataTable
                columns={[
                  { key: 'network', header: 'Network' },
                  {
                    key: 'title',
                    header: 'Label',
                    render: (item) => String(item.title || '—'),
                  },
                  { key: 'capacity', header: 'Capacity', align: 'right', sortable: true, render: (item) => formatNumber(item.capacity as number) },
                  { key: 'used', header: 'Used', align: 'right', sortable: true, render: (item) => formatNumber(item.used as number) },
                  {
                    key: 'utilization_percent',
                    header: 'Utilization',
                    align: 'right',
                    sortable: true,
                    render: (item) => (
                      <span className={cn(
                        'font-mono text-sm',
                        (item.utilization_percent as number) <= 70 ? 'text-teal-electric' :
                        (item.utilization_percent as number) <= 85 ? 'text-amber-warn' : 'text-coral-alert'
                      )}>
                        {formatPercent(item.utilization_percent as number)}
                      </span>
                    ),
                  },
                ]}
                data={(ipUtilization?.networks || []) as unknown as Record<string, unknown>[]}
                keyField="network"
                loading={!ipUtilization}
                emptyMessage="No IP pool data"
              />
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Expense Trend</CardTitle>
                    <CardDescription>Approved & paid expenses over {timeRange} months</CardDescription>
                  </div>
                  {expenseTrend && (
                    <Badge variant="default">
                      {expenseTrend.length} months
                    </Badge>
                  )}
                </div>
              </CardHeader>
              {expenseTrend ? (
                <ExpenseTrendChart data={expenseTrend} height={300} />
              ) : (
                <div className="h-[300px] skeleton rounded-lg" />
              )}
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Expenses by Category</CardTitle>
                    <CardDescription>Where spend is concentrated</CardDescription>
                  </div>
                  {expensesByCategory && (
                    <Badge variant="default">
                      {formatCurrency(expensesByCategory.total_expenses, currency)}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <DataTable
                columns={[
                  { key: 'category', header: 'Category' },
                  { key: 'count', header: 'Count', align: 'right', sortable: true },
                  {
                    key: 'total',
                    header: 'Total',
                    align: 'right',
                    sortable: true,
                    render: (item) => formatCurrency(item.total as number, currency),
                  },
                ]}
                data={(expensesByCategory?.by_category || []) as unknown as Record<string, unknown>[]}
                keyField="category"
                loading={!expensesByCategory}
                emptyMessage="No expense data"
              />
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Top Vendors</CardTitle>
                  <CardDescription>Purchase invoice spend by supplier</CardDescription>
                </div>
                {vendorSpend && (
                  <Badge variant="default">
                    {formatCurrency(vendorSpend.total_spend, currency)}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <DataTable
              columns={[
                {
                  key: 'supplier_label',
                  header: 'Supplier',
                  render: (item) => String(item.supplier_name || item.supplier || 'Unknown'),
                },
                { key: 'invoice_count', header: 'Invoices', align: 'right', sortable: true },
                {
                  key: 'total_spend',
                  header: 'Spend',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatCurrency(item.total_spend as number, currency),
                },
                {
                  key: 'outstanding',
                  header: 'Outstanding',
                  align: 'right',
                  sortable: true,
                  render: (item) => formatCurrency(item.outstanding as number, currency),
                },
              ]}
              data={((vendorSpend?.vendors || []).map((vendor, idx) => ({
                ...vendor,
                supplier_label: vendor.supplier_name || vendor.supplier || 'Unknown',
                row_id: vendor.supplier || vendor.supplier_name || `vendor-${idx}`,
              })) || []) as unknown as Record<string, unknown>[]}
              keyField="row_id"
              loading={!vendorSpend}
              emptyMessage="No vendor spend data"
            />
          </Card>
        </div>
      )}

      {/* Revenue Summary - Always visible at bottom */}
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
