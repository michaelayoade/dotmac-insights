'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  useCustomerSignupTrend,
  useCustomerCohort,
  useCustomersByPlan,
  useCustomersByType,
  useCustomersByLocation,
  useCustomersByPop,
  useCustomersByRouter,
  useCustomersByTicketVolume,
  useCustomerDataQualityOutreach,
  useCustomerRevenueOverdue,
  useCustomerPaymentTimeliness,
  useBlockedAnalytics,
  useActiveAnalytics,
} from '@/hooks/useApi';
import {
  CustomerSignupTrendResponse,
  CustomerCohortItem,
  CustomerCohortResponse,
  CustomerByPlanItem,
  CustomerByType,
  CustomerByLocation,
  CustomerByTypeResponse,
  CustomerByLocationResponse,
  CustomerByPop,
  CustomerByRouter,
  CustomerTicketVolumeBucket,
  CustomerDataQualityOutreach,
  CustomerRevenueOverdue,
  ActiveAnalyticsResponse,
} from '@/lib/api';
import BlockedCustomersPage from '../blocked/page';
import {
  InsightCard,
  LoadingState,
  ErrorDisplay,
  EmptyState,
  SummaryCard,
} from '@/components/insights/shared';
import { formatCurrency } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { DataTable } from '@/components/DataTable';
import {
  LineChart,
  Line,
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

const COLORS = ['#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#3b82f6', '#ec4899', '#22c55e'];

type AnalyticsTab = 'trends' | 'distribution' | 'cohort';
type ExtendedTab = AnalyticsTab | 'operations' | 'active' | 'blocked';

export default function CustomerAnalyticsPage() {
  const [activeTab, setActiveTab] = useState<ExtendedTab>('trends');
  const [months, setMonths] = useState(12);
  const [cohortMonths, setCohortMonths] = useState(12);
  const [ticketDays, setTicketDays] = useState(30);
  const [paymentDays, setPaymentDays] = useState(180);

  const startDate = useMemo(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - months);
    return d.toISOString().split('T')[0];
  }, [months]);

  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const canFetch = hasAccess && !authLoading;

  // Fetch all data
  const swrGuard = { isPaused: () => !canFetch };
  const { data: signupTrend, isLoading: signupLoading, error: signupError } = useCustomerSignupTrend({ start_date: startDate, interval: 'month' }, swrGuard);
  const { data: cohortData, isLoading: cohortLoading, error: cohortError } = useCustomerCohort(cohortMonths, swrGuard);
  const { data: byPlan, isLoading: planLoading, error: planError } = useCustomersByPlan(swrGuard);
  const { data: byType, isLoading: typeLoading, error: typeError } = useCustomersByType(swrGuard);
  const { data: byLocation, isLoading: locationLoading, error: locationError } = useCustomersByLocation(50, swrGuard);
  const { data: byPop, isLoading: popLoading, error: popError } = useCustomersByPop(swrGuard);
  const { data: byRouter, isLoading: routerLoading, error: routerError } = useCustomersByRouter(undefined, swrGuard);
  const { data: ticketVolume, isLoading: ticketLoading, error: ticketError } = useCustomersByTicketVolume(ticketDays, swrGuard);
  const { data: outreach, isLoading: outreachLoading, error: outreachError } = useCustomerDataQualityOutreach(swrGuard);
  const { data: revenueOverdue, isLoading: overdueLoading, error: overdueError } = useCustomerRevenueOverdue(undefined, undefined, swrGuard);
  const { data: paymentTimeliness, isLoading: paymentLoading, error: paymentError } = useCustomerPaymentTimeliness(paymentDays, swrGuard);
  const { data: blockedAnalytics, isLoading: blockedLoading, error: blockedError } = useBlockedAnalytics(swrGuard);
  const { data: activeAnalytics, isLoading: activeLoading, error: activeError } = useActiveAnalytics(swrGuard);

  const isLoading = signupLoading || cohortLoading || planLoading || typeLoading || locationLoading || popLoading || routerLoading || ticketLoading || outreachLoading || overdueLoading || paymentLoading || blockedLoading || activeLoading;
  const error = signupError || cohortError || planError || typeError || locationError || popError || routerError || ticketError || outreachError || overdueError || paymentError || blockedError || activeError;

  const normalizedByType: Array<{ customer_type: string; count: number; mrr?: number }> = useMemo(() => {
    const source = byType as CustomerByTypeResponse | CustomerByType[] | undefined;
    if (!source) return [];
    const payload = (source as CustomerByTypeResponse).by_type
      ? (source as CustomerByTypeResponse).by_type
      : (source as CustomerByType[]);
    if (!Array.isArray(payload)) return [];
    return payload.map((item: any) => ({
      customer_type: item.customer_type || item.type || 'unknown',
      count: item.count ?? item.customer_count ?? 0,
      mrr: item.mrr,
    }));
  }, [byType]);

  const normalizedByLocation: Array<CustomerByLocation> = useMemo(() => {
    const source = byLocation as CustomerByLocationResponse | CustomerByLocation[] | undefined;
    if (!source) return [];
    const payload = (source as CustomerByLocationResponse).by_city
      ? (source as CustomerByLocationResponse).by_city
      : (source as CustomerByLocation[]);
    if (!Array.isArray(payload)) return [];
    return payload.map((item: any) => ({
      city: item.city ?? null,
      state: item.state ?? null,
      customer_count: item.customer_count ?? item.count ?? 0,
      mrr: item.mrr,
    }));
  }, [byLocation]);

  const normalizedByPop: CustomerByPop[] = useMemo(() => {
    const payload = (byPop as any)?.by_pop || byPop;
    if (!Array.isArray(payload)) return [];
    return payload;
  }, [byPop]);

  const normalizedByRouter: CustomerByRouter[] = useMemo(() => {
    if (!Array.isArray(byRouter as any)) return [];
    return byRouter as CustomerByRouter[];
  }, [byRouter]);

  const normalizedTicketBuckets: Array<{ bucket: string; count: number }> = useMemo(() => {
    if (!ticketVolume) return [];
    const buckets = (ticketVolume as any).buckets || {};
    return Object.entries(buckets).map(([bucket, count]) => ({ bucket, count: Number(count) }));
  }, [ticketVolume]);

  const normalizedCohort = useMemo(() => {
    const data = cohortData as CustomerCohortResponse | undefined;
    const cohorts: CustomerCohortItem[] = (data?.cohorts || []).map((c) => ({
      cohort: c.cohort,
      total_customers: c.total_customers,
      active: c.by_status?.active ?? c.active ?? c.current_active,
      churned: c.by_status?.churned ?? c.churned,
      new: c.by_status?.new ?? (c as any).new ?? (c as any).new_customers,
      blocked: c.by_status?.blocked ?? (c as any).blocked,
      inactive: c.by_status?.inactive ?? (c as any).inactive,
      retention_rate: c.retention_rate ?? (c.active && c.total_customers ? (c.active / c.total_customers) * 100 : undefined),
      total_mrr: (c as any).total_mrr,
    }));
    const summary = data?.summary || {};
    return { cohorts, summary };
  }, [cohortData]);

  // Combined trend data
  const signupData = (signupTrend as CustomerSignupTrendResponse | undefined)?.data || [];
  const activeOverview = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.overview;
  const activeByType = activeOverview?.by_type || [];
  const activeTenure = useMemo(() => {
    const source =
      (activeAnalytics as ActiveAnalyticsResponse | undefined)?.by_tenure ||
      (activeAnalytics as any)?.tenure ||
      (activeAnalytics as any)?.buckets ||
      [];
    const FALLBACK_LABELS = ['0-30 days', '1-3 months', '3-6 months', '6-12 months', '12+ months'];
    if (!Array.isArray(source)) return [];

    const mapped = source.map((row: any, idx: number) => {
      const bucket =
        row.bucket ??
        row.bucket_name ??
        row.segment ??
        row.name ??
        row.label ??
        row.range ??
        row.window ??
        row.tenure ??
        row.tenure_label ??
        row.tenure_bucket ??
        row.duration ??
        (() => {
          const min = row.min_days ?? row.min ?? row.days_min;
          const max = row.max_days ?? row.max ?? row.days_max;
          if (min !== undefined || max !== undefined) {
            if (min !== undefined && max !== undefined) return `${min}-${max} days`;
            if (min !== undefined) return `${min}+ days`;
            return `<${max} days`;
          }
          if (row.months !== undefined) return `${row.months}+ months`;
          if (row.days !== undefined) return `${row.days} days`;
          return undefined;
        })() ??
        FALLBACK_LABELS[idx] ??
        'Unspecified';

      return {
        bucket,
        count: row.count ?? row.customer_count ?? row.total ?? 0,
        mrr: row.mrr ?? row.total_mrr,
      };
    });

    // Aggregate duplicates by bucket label to avoid repeated "Unknown/Unspecified"
    const byBucket = mapped.reduce((acc: Record<string, { bucket: string; count: number; mrr?: number }>, row) => {
      const key = row.bucket || 'Unspecified';
      if (!acc[key]) {
        acc[key] = { bucket: key, count: 0, mrr: 0 };
      }
      acc[key].count += row.count || 0;
      acc[key].mrr = (acc[key].mrr || 0) + (row.mrr || 0);
      return acc;
    }, {});

    return Object.values(byBucket);
  }, [activeAnalytics]);
  const activePlans = useMemo(() => {
    const source = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.by_plan || (activeAnalytics as any)?.plans || [];
    return Array.isArray(source)
      ? source.map((row: any) => ({
          plan_name: row.plan_name ?? row.plan ?? row.name ?? row.contract ?? row.contract_name ?? row.plan_code ?? 'Unknown plan',
          customer_count: row.customer_count ?? row.count ?? row.customers ?? row.total_customers ?? 0,
          mrr: row.mrr ?? row.total_mrr ?? row.revenue,
        }))
      : [];
  }, [activeAnalytics]);
  const activeLocations = useMemo(() => {
    const source =
      (activeAnalytics as ActiveAnalyticsResponse | undefined)?.by_location ||
      (activeAnalytics as any)?.locations ||
      [];
    if (!Array.isArray(source)) return [];
    return source.map((row: any) => ({
      pop_name: row.pop_name ?? row.name ?? row.location ?? row.pop ?? undefined,
      pop_id: row.pop_id ?? row.id ?? undefined,
      customer_count: row.customer_count ?? row.count ?? row.customers ?? row.total_customers ?? 0,
      mrr: row.mrr ?? row.total_mrr ?? row.revenue,
    }));
  }, [activeAnalytics]);
  const serviceHealth = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.service_health;
  const paymentRisk = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.payment_risk;
  const topActiveCustomers = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.top_customers || [];
  const supportConcerns = (activeAnalytics as ActiveAnalyticsResponse | undefined)?.support_concerns || [];
  const topPlanRows = useMemo(
    () => activePlans.map((plan, idx) => ({ ...plan, _id: plan.plan_name || `plan-${idx}` })),
    [activePlans]
  );
  const locationRows = useMemo(
    () => normalizedByLocation.map((loc, idx) => ({ ...loc, _id: `${loc.city || 'unknown'}-${loc.state || ''}-${idx}` })),
    [normalizedByLocation]
  );
  const cohortRows = useMemo(
    () => (normalizedCohort.cohorts || []).map((cohort, idx) => ({ ...cohort, _id: cohort.cohort || `cohort-${idx}` })),
    [normalizedCohort.cohorts]
  );

  if (authLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load customer analytics"
        error={error}
      />
    );
  }

  const tabs = [
    { key: 'trends' as ExtendedTab, label: 'Trends' },
    { key: 'active' as ExtendedTab, label: 'Active Health' },
    { key: 'blocked' as ExtendedTab, label: 'Blocked' },
    { key: 'distribution' as ExtendedTab, label: 'Distribution' },
    { key: 'cohort' as ExtendedTab, label: 'Cohort Analysis' },
    { key: 'operations' as ExtendedTab, label: 'Operations & Quality' },
  ];

  return (
    <div className="space-y-6">
      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-border pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab.key
                ? 'bg-teal-electric/20 text-teal-electric border-b-2 border-teal-electric'
                : 'text-slate-muted hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Trends Tab */}
      {activeTab === 'trends' && (
        <div className="space-y-6">
          {/* Time Period Filter */}
          <div className="flex items-center gap-4">
            <label className="text-sm text-slate-muted">Time Period:</label>
            <select
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric"
            >
              <option value={6}>Last 6 months</option>
              <option value={12}>Last 12 months</option>
              <option value={24}>Last 24 months</option>
            </select>
          </div>

          {/* Growth Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <SummaryCard
              title="Total Signups"
              value={((signupTrend as CustomerSignupTrendResponse | undefined)?.data.reduce((sum, s) => sum + s.signups, 0) || 0).toString()}
              subtitle={`Last ${months} months`}
              gradient="from-green-500 to-green-600"
            />
            <SummaryCard
              title="Total Customers"
              value={(blockedAnalytics?.overview?.total_customers || 0).toLocaleString()}
              subtitle="Current total"
              gradient="from-teal-500 to-teal-600"
            />
            <SummaryCard
              title="Blocked Customers"
              value={(blockedAnalytics?.overview?.blocked_customers || blockedAnalytics?.overview?.blocked || 0).toLocaleString()}
              subtitle="Currently blocked"
              gradient="from-red-500 to-red-600"
            />
            <SummaryCard
              title="MRR at Risk"
              value={formatCurrency(blockedAnalytics?.overview?.mrr_at_risk || 0, 'NGN')}
              subtitle="Blocked revenue risk"
              gradient="from-amber-500 to-amber-600"
            />
            <SummaryCard
              title="Blocked Rate"
              value={`${(blockedAnalytics?.overview?.blocked_rate ?? 0).toFixed(1)}%`}
              subtitle="Blocked vs active"
              gradient="from-purple-500 to-purple-600"
            />
          </div>

          {/* Signup Trend */}
          <InsightCard title="Signup Trend">
            {signupData.length === 0 ? (
              <EmptyState message="No trend data available" />
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={signupData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="period" stroke="#9ca3af" fontSize={12} />
                  <YAxis stroke="#9ca3af" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="signups"
                    stroke="#22c55e"
                    strokeWidth={2}
                    name="Signups"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </InsightCard>

        </div>
      )}

      {/* Active Health Tab */}
      {activeTab === 'active' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <SummaryCard
              title="Active Customers"
              value={(activeOverview?.total_active ?? 0).toLocaleString()}
              subtitle="Currently active"
              gradient="from-teal-500 to-teal-600"
            />
            <SummaryCard
              title="Active MRR"
              value={formatCurrency(activeOverview?.total_mrr ?? 0, 'NGN')}
              subtitle="Monthly recurring revenue"
              gradient="from-emerald-500 to-emerald-600"
            />
            <SummaryCard
              title="Avg MRR"
              value={activeOverview?.avg_mrr !== undefined ? formatCurrency(activeOverview.avg_mrr, 'NGN') : '—'}
              subtitle="Per active customer"
              gradient="from-blue-500 to-blue-600"
            />
            <SummaryCard
              title="New Signups"
              value={(activeOverview?.new_signups ?? 0).toLocaleString()}
              subtitle="Recent additions"
              gradient="from-amber-500 to-amber-600"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Customer Type Mix">
              {!activeByType || activeByType.length === 0 ? (
                <EmptyState message="No active type data yet" />
              ) : (
                <div className="space-y-2">
                  {activeByType.map((row) => (
                    <div key={row.type} className="flex items-center justify-between text-sm bg-slate-card/50 rounded-lg px-3 py-2 border border-slate-border/50">
                      <span className="text-white capitalize">{row.type}</span>
                      <div className="flex items-center gap-4 text-slate-muted">
                        <span>{(row.count ?? (row as any).customer_count ?? 0).toLocaleString()} customers</span>
                        {row.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>

            <InsightCard title="Tenure Distribution">
              {!activeTenure || activeTenure.length === 0 ? (
                <EmptyState message="No tenure data available" />
              ) : (
                <div className="space-y-2">
                  {activeTenure.map((row, idx) => (
                    <div key={`${row.bucket}-${idx}`} className="flex items-center justify-between text-sm bg-slate-card/50 rounded-lg px-3 py-2 border border-slate-border/50">
                      <span className="text-white">{row.bucket || 'Unspecified'}</span>
                      <div className="flex items-center gap-4 text-slate-muted">
                        <span>{(row.count ?? 0).toLocaleString()} customers</span>
                        {row.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Top Plans (Active)">
              {!activePlans || activePlans.length === 0 ? (
                <EmptyState message="No active plan data" />
              ) : (
                <DataTable
                  keyField="_id"
                  data={topPlanRows as any[]}
                  columns={[
                    {
                      key: 'plan_name',
                      header: 'Plan',
                      sortable: true,
                      render: (row) => <span className="text-white">{(row.plan_name as string) || 'Unknown plan'}</span>,
                    },
                    {
                      key: 'customer_count',
                      header: 'Customers',
                      sortable: true,
                      align: 'right',
                      render: (row) => <span className="text-slate-muted">{(row.customer_count as number)?.toLocaleString() ?? 0}</span>,
                    },
                    {
                      key: 'mrr',
                      header: 'MRR',
                      sortable: true,
                      align: 'right',
                      render: (row) => <span className="text-teal-electric">{formatCurrency((row.mrr as number) ?? 0, 'NGN')}</span>,
                    },
                  ]}
                />
              )}
            </InsightCard>

            <InsightCard title="Active Customers by POP">
              {!activeLocations || activeLocations.length === 0 ? (
                <EmptyState message="No POP distribution data" />
              ) : (
                <div className="space-y-2">
                  {activeLocations.map((pop) => (
                    <div key={pop.pop_name || pop.pop_id} className="flex items-center justify-between text-sm bg-slate-card/50 rounded-lg px-3 py-2 border border-slate-border/50">
                      <div className="text-white">{pop.pop_name || `POP ${pop.pop_id ?? ''}`}</div>
                      <div className="text-right text-slate-muted">
                        <span className="mr-3">{(pop.customer_count ?? 0).toLocaleString()} customers</span>
                        {pop.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(pop.mrr, 'NGN')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Service Health (active paying)">
              {!serviceHealth || (
                (serviceHealth.no_recent_usage?.length ?? 0) === 0 &&
                (serviceHealth.low_usage?.length ?? 0) === 0 &&
                (serviceHealth.inactive_7_days?.length ?? 0) === 0
              ) ? (
                <EmptyState message="No service health flags right now" />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-slate-card/60 rounded-lg p-3 border border-slate-border/60">
                    <p className="text-xs uppercase text-slate-muted mb-2">No recent usage</p>
                    <div className="space-y-2">
                      {serviceHealth?.no_recent_usage?.slice(0, 5).map((row, idx) => (
                        <div key={`${row.name}-${idx}`} className="flex items-center justify-between text-xs text-slate-muted">
                          <span className="text-white">{row.name}</span>
                          <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>
                        </div>
                      )) || <p className="text-slate-muted text-xs">No entries</p>}
                    </div>
                  </div>
                  <div className="bg-slate-card/60 rounded-lg p-3 border border-slate-border/60">
                    <p className="text-xs uppercase text-slate-muted mb-2">Low usage</p>
                    <div className="space-y-2">
                      {serviceHealth?.low_usage?.slice(0, 5).map((row, idx) => (
                        <div key={`${row.name}-${idx}`} className="flex items-center justify-between text-xs text-slate-muted">
                          <span className="text-white">{row.name}</span>
                          <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>
                        </div>
                      )) || <p className="text-slate-muted text-xs">No entries</p>}
                    </div>
                  </div>
                  <div className="bg-slate-card/60 rounded-lg p-3 border border-slate-border/60">
                    <p className="text-xs uppercase text-slate-muted mb-2">Inactive 7d</p>
                    <div className="space-y-2">
                      {serviceHealth?.inactive_7_days?.slice(0, 5).map((row, idx) => (
                        <div key={`${row.name}-${idx}`} className="flex items-center justify-between text-xs text-slate-muted">
                          <span className="text-white">{row.name}</span>
                          <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>
                        </div>
                      )) || <p className="text-slate-muted text-xs">No entries</p>}
                    </div>
                  </div>
                </div>
              )}
            </InsightCard>

            <InsightCard title="Payment Risk">
              {!paymentRisk ? (
                <EmptyState message="No payment risk data" />
              ) : (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-amber-warn/10 border border-amber-warn/30 rounded-lg p-3">
                    <p className="text-xs uppercase text-amber-warn">Blocking soon</p>
                    <p className="text-white font-mono text-xl">{(paymentRisk.blocking_soon ?? 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3">
                    <p className="text-xs uppercase text-coral-alert">Overdue invoices</p>
                    <p className="text-white font-mono text-xl">{(paymentRisk.overdue_invoices ?? 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
                    <p className="text-xs uppercase text-purple-300">Negative deposits</p>
                    <p className="text-white font-mono text-xl">{(paymentRisk.negative_deposit ?? 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-teal-electric/10 border border-teal-electric/30 rounded-lg p-3">
                    <p className="text-xs uppercase text-teal-electric">MRR at risk</p>
                    <p className="text-white font-mono text-xl">{formatCurrency(paymentRisk.mrr_at_risk ?? 0, 'NGN')}</p>
                  </div>
                </div>
              )}
            </InsightCard>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Top Active Customers">
              {!topActiveCustomers || topActiveCustomers.length === 0 ? (
                <EmptyState message="No top customer data" />
              ) : (
                <div className="space-y-2">
                  {topActiveCustomers.slice(0, 10).map((cust, idx) => (
                    <div key={cust.customer_id ?? cust.name ?? idx} className="flex items-center justify-between text-sm bg-slate-card/50 rounded-lg px-3 py-2 border border-slate-border/50">
                      <div>
                        <p className="text-white font-medium">{cust.name}</p>
                        <p className="text-xs text-slate-muted">
                          {cust.last_seen ? `Last seen ${new Date(cust.last_seen).toLocaleDateString()}` : 'No last seen data'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-teal-electric font-mono">{formatCurrency(cust.mrr, 'NGN')}</p>
                        {cust.status && <p className="text-xs text-slate-muted uppercase">{cust.status}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>

            <InsightCard title="Support Concerns">
              {!supportConcerns || supportConcerns.length === 0 ? (
                <EmptyState message="No support concerns flagged" />
              ) : (
                <div className="space-y-2">
                  {supportConcerns.slice(0, 10).map((row, idx) => (
                    <div key={row.customer_id ?? row.name ?? idx} className="flex items-center justify-between text-sm bg-slate-card/50 rounded-lg px-3 py-2 border border-slate-border/50">
                      <div className="text-white">{row.name}</div>
                      <div className="text-right text-slate-muted flex items-center gap-3">
                        {row.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(row.mrr, 'NGN')}</span>}
                        <span className="px-2 py-1 bg-amber-warn/10 text-amber-warn rounded-lg border border-amber-warn/30 text-xs font-medium">
                          {row.ticket_count} open
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>
          </div>
        </div>
      )}

      {/* Blocked Tab */}
      {activeTab === 'blocked' && (
        <div className="space-y-6">
          <BlockedCustomersPage />
        </div>
      )}

      {/* Distribution Tab */}
      {activeTab === 'distribution' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* By Plan */}
            <InsightCard title="Customers by Plan">
              {!byPlan || byPlan.length === 0 ? (
                <EmptyState message="No plan distribution data" />
              ) : (
                <div className="space-y-4">
                  <ResponsiveContainer width="100%" height={320}>
                    <PieChart>
                      <Pie
                        data={byPlan}
                        dataKey="customer_count"
                        nameKey="plan_name"
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={110}
                        paddingAngle={2}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {byPlan.map((_: CustomerByPlanItem, index: number) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '8px',
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
                    {byPlan.map((plan: CustomerByPlanItem, index: number) => (
                      <div key={plan.plan_name} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                          />
                          <span className="text-white">{plan.plan_name}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-slate-muted">{plan.customer_count} customers</span>
                          <span className="text-slate-muted">{plan.subscription_count} subs</span>
                          <span className="text-teal-electric">{formatCurrency(plan.mrr, 'NGN')}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </InsightCard>

            {/* By Type */}
            <InsightCard title="Customers by Type">
              {normalizedByType.length === 0 ? (
                <EmptyState message="No type distribution data" />
              ) : (
                <div className="space-y-4">
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={normalizedByType} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis type="number" stroke="#9ca3af" fontSize={12} />
                      <YAxis type="category" dataKey="customer_type" stroke="#9ca3af" fontSize={12} width={100} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '8px',
                        }}
                      />
                      <Bar dataKey="count" fill="#14b8a6" />
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="space-y-2">
                    {normalizedByType.map((type) => (
                      <div key={type.customer_type} className="flex items-center justify-between text-sm">
                        <span className="text-white capitalize">{type.customer_type}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-slate-muted">{type.count} customers</span>
                          {type.mrr !== undefined && (
                            <span className="text-teal-electric">{formatCurrency(type.mrr, 'NGN')}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </InsightCard>

            {/* By Location */}
      <InsightCard title="Customers by Location" className="lg:col-span-2">
              {normalizedByLocation.length === 0 ? (
                <EmptyState message="No location data available" />
              ) : (
                <DataTable
                  keyField="_id"
                  data={locationRows as any[]}
                  columns={[
                    {
                      key: 'city',
                      header: 'City',
                      sortable: true,
                      render: (row) => <span className="text-white capitalize">{(row.city as string) || 'Unknown'}</span>,
                    },
                    {
                      key: 'state',
                      header: 'State',
                      sortable: true,
                      render: (row) => <span className="text-slate-muted capitalize">{(row.state as string) || '-'}</span>,
                    },
                    {
                      key: 'customer_count',
                      header: 'Customers',
                      sortable: true,
                      align: 'right',
                      render: (row) => <span className="text-white">{(row.customer_count as number)?.toLocaleString() ?? 0}</span>,
                    },
                    {
                      key: 'mrr',
                      header: 'MRR',
                      sortable: true,
                      align: 'right',
                      render: (row) => (
                        <span className="text-teal-electric">
                          {row.mrr !== undefined ? formatCurrency((row.mrr as number) ?? 0, 'NGN') : '—'}
                        </span>
                      ),
                    },
                  ]}
                />
              )}
            </InsightCard>
          </div>
        </div>
      )}

      {/* Cohort Tab */}
      {activeTab === 'cohort' && (
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-muted">Window:</label>
            <select
              value={cohortMonths}
              onChange={(e) => setCohortMonths(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric"
            >
              <option value={12}>Last 12 months</option>
              <option value={24}>Last 24 months</option>
              <option value={36}>Last 36 months</option>
            </select>
          </div>
          {/* Cohort Summary */}
          {normalizedCohort.summary && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SummaryCard
                title="Average Retention"
                value={`${(normalizedCohort.summary.avg_retention || 0).toFixed(1)}%`}
                subtitle={`Across ${normalizedCohort.summary.total_cohorts || 0} cohorts`}
                gradient="from-teal-500 to-teal-600"
              />
              <SummaryCard
                title="Total Cohorts"
                value={normalizedCohort.summary.total_cohorts?.toString() || '0'}
                subtitle="Monthly signup cohorts"
                gradient="from-blue-500 to-blue-600"
              />
              <SummaryCard
                title="Total Customers"
                value={(normalizedCohort.summary as any).total_customers?.toString() || '0'}
                subtitle="Across cohorts in window"
                gradient="from-purple-500 to-purple-600"
              />
            </div>
          )}

          {/* Cohort Table */}
          <InsightCard title="Customer Retention Cohorts">
            {!normalizedCohort.cohorts || normalizedCohort.cohorts.length === 0 ? (
              <EmptyState message="No cohort data available" />
            ) : (
              <DataTable
                keyField="_id"
                data={cohortRows as any[]}
                columns={[
                  { key: 'cohort', header: 'Cohort', sortable: true, render: (row) => <span className="text-white font-medium">{row.cohort as string}</span> },
                  { key: 'total_customers', header: 'Total', sortable: true, align: 'right', render: (row) => <span className="text-white">{row.total_customers as number}</span> },
                  { key: 'active', header: 'Active', sortable: true, align: 'right', render: (row) => <span className="text-teal-electric">{row.active ?? '—'}</span> },
                  { key: 'new', header: 'New', sortable: true, align: 'right', render: (row) => <span className="text-slate-muted">{(row as any).new ?? '—'}</span> },
                  { key: 'blocked', header: 'Blocked', sortable: true, align: 'right', render: (row) => <span className="text-slate-muted">{(row as any).blocked ?? '—'}</span> },
                  { key: 'inactive', header: 'Inactive', sortable: true, align: 'right', render: (row) => <span className="text-slate-muted">{(row as any).inactive ?? '—'}</span> },
                  { key: 'churned', header: 'Churned', sortable: true, align: 'right', render: (row) => <span className="text-slate-muted">{row.churned ?? '—'}</span> },
                  { key: 'total_mrr', header: 'MRR', sortable: true, align: 'right', render: (row) => <span className="text-teal-electric">{(row as any).total_mrr ? formatCurrency((row as any).total_mrr, 'NGN') : '—'}</span> },
                  {
                    key: 'retention_rate',
                    header: 'Retention',
                    sortable: true,
                    align: 'right',
                    render: (row) => (
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          (row.retention_rate ?? 0) >= 80
                            ? 'bg-green-500/20 text-green-400'
                            : (row.retention_rate ?? 0) >= 60
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-red-500/20 text-red-400'
                        }`}
                      >
                        {(row.retention_rate ?? 0).toFixed(1)}%
                      </span>
                    ),
                  },
                  {
                    key: 'actions',
                    header: 'View',
                    align: 'right',
                    render: (row) => (
                      <div className="flex justify-end gap-2 text-xs">
                        <Link
                          href={`/customers?cohort=${encodeURIComponent(row.cohort as string)}`}
                          className="text-teal-electric hover:text-teal-glow underline"
                        >
                          View all
                        </Link>
                        {(row as any).blocked > 0 && (
                          <Link
                            href={`/customers?cohort=${encodeURIComponent(row.cohort as string)}&status=blocked`}
                            className="text-amber-warn hover:text-amber-400 underline"
                          >
                            View blocked
                          </Link>
                        )}
                      </div>
                    ),
                  },
                ]}
              />
            )}
          </InsightCard>
        </div>
      )}

      {/* Operations Tab */}
      {activeTab === 'operations' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Customers by POP">
              {normalizedByPop.length === 0 ? (
                <EmptyState message="No POP data available" />
              ) : (
                <div className="space-y-2">
                  {normalizedByPop.map((pop) => (
                    <div key={pop.pop_id ?? pop.pop_name} className="flex items-center justify-between text-sm">
                      <div className="text-white">{pop.pop_name || `POP ${pop.pop_id}`}</div>
                      <div className="text-right text-slate-muted">
                        <span className="mr-3">{pop.customer_count} customers</span>
                        {pop.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(pop.mrr, 'NGN')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>

            <InsightCard title="Customers by Router">
              {normalizedByRouter.length === 0 ? (
                <EmptyState message="No router data available" />
              ) : (
                <div className="space-y-2 max-h-[320px] overflow-y-auto">
                  {normalizedByRouter.map((router) => (
                    <div key={router.router_id} className="flex items-center justify-between text-sm border-b border-slate-border/60 pb-2">
                      <div>
                        <p className="text-white font-medium">{router.router_name}</p>
                        <p className="text-xs text-slate-muted">POP {router.pop_id}</p>
                      </div>
                      <div className="text-right text-slate-muted">
                        <span className="mr-3">{router.customer_count} customers</span>
                        {router.mrr !== undefined && <span className="text-teal-electric">{formatCurrency(router.mrr, 'NGN')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </InsightCard>
          </div>

          <InsightCard title={`Ticket Volume (last ${ticketDays} days)`}>
            <div className="flex items-center gap-3 mb-3">
              <label className="text-xs text-slate-muted">Window:</label>
              <select
                value={ticketDays}
                onChange={(e) => setTicketDays(Number(e.target.value))}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-xs text-white"
              >
                <option value={30}>30 days</option>
                <option value={60}>60 days</option>
                <option value={90}>90 days</option>
              </select>
            </div>
            {normalizedTicketBuckets.length === 0 ? (
              <EmptyState message="No ticket volume data" />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {normalizedTicketBuckets.map((b) => (
                  <div key={b.bucket} className="bg-slate-card/60 rounded-lg p-3 text-sm">
                    <p className="text-slate-muted capitalize">{b.bucket.replace(/_/g, ' ')}</p>
                    <p className="text-white font-mono text-lg">{b.count.toLocaleString()}</p>
                  </div>
                ))}
              </div>
            )}
          </InsightCard>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <InsightCard title="Data Quality & Outreach">
              {!outreach ? (
                <EmptyState message="No outreach data available" />
              ) : (
                <div className="space-y-3 text-sm text-slate-muted">
                  <div>
                    <p className="text-xs uppercase text-slate-muted mb-1">Missing Contact by POP</p>
                    {(outreach as any).missing_contact?.by_pop?.map((row: any) => (
                      <div key={row.pop_name || row.pop_id} className="flex justify-between">
                        <span className="text-white">{row.pop_name || `POP ${row.pop_id}`}</span>
                        <span>{row.missing_count ?? row.missing_email ?? 0} missing</span>
                      </div>
                    )) || <p>No POP gaps</p>}
                  </div>
                  <div>
                    <p className="text-xs uppercase text-slate-muted mb-1">Missing Contact by Plan</p>
                    {(outreach as any).missing_contact?.by_plan?.map((row: any) => (
                      <div key={row.plan_name} className="flex justify-between">
                        <span className="text-white">{row.plan_name}</span>
                        <span>{row.missing_count ?? row.missing_email ?? 0} missing</span>
                      </div>
                    )) || <p>No plan gaps</p>}
                  </div>
                  <div>
                    <p className="text-xs uppercase text-slate-muted mb-1">Linkage Gaps</p>
                    {(outreach as any).linkage_gaps?.map((row: any) => (
                      <div key={row.customer_type} className="flex justify-between">
                        <span className="text-white capitalize">{row.customer_type}</span>
                        <span>{row.total ?? 0} missing links</span>
                      </div>
                    )) || <p>No linkage gaps</p>}
                  </div>
                </div>
              )}
            </InsightCard>

            <InsightCard title="Revenue Overdue & Payment Timeliness">
              {!revenueOverdue && !paymentTimeliness ? (
                <EmptyState message="No revenue or payment data" />
              ) : (
                <div className="space-y-4 text-sm">
                  {revenueOverdue && (
                    <div>
                      <p className="text-xs uppercase text-slate-muted mb-1">Overdue by Segment</p>
                      <div className="space-y-2">
                        {(revenueOverdue as CustomerRevenueOverdue).by_segment?.map((seg: any, idx: number) => (
                          <div key={idx} className="flex justify-between">
                            <span className="text-white">
                              {seg.pop_name || seg.pop_id || ''} {seg.plan_name ? `• ${seg.plan_name}` : ''}
                            </span>
                            <span className="text-coral-alert font-mono">{formatCurrency(seg.balance || 0, 'NGN')}</span>
                          </div>
                        )) || <p className="text-slate-muted">No overdue balances</p>}
                      </div>
                    </div>
                  )}
                  {paymentTimeliness && Array.isArray(paymentTimeliness) && paymentTimeliness.length > 0 && (
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <p className="text-xs uppercase text-slate-muted">Payment Timeliness</p>
                        <select
                          value={paymentDays}
                          onChange={(e) => setPaymentDays(Number(e.target.value))}
                          className="bg-slate-elevated border border-slate-border rounded-lg px-2 py-1 text-xs text-white"
                        >
                          <option value={90}>90 days</option>
                          <option value={180}>180 days</option>
                          <option value={365}>365 days</option>
                        </select>
                      </div>
                      <div className="space-y-2 max-h-[240px] overflow-y-auto">
                        {paymentTimeliness.map((row: any, idx: number) => (
                          <div key={idx} className="flex justify-between text-xs text-slate-muted bg-slate-card/60 rounded-lg p-2">
                            <span className="text-white">{row.customer_type} {row.plan_name ? `• ${row.plan_name}` : ''}</span>
                            <span className="text-teal-electric">{(row.on_time_rate ?? 0).toFixed(1)}% on-time</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </InsightCard>
          </div>
        </div>
      )}
    </div>
  );
}
