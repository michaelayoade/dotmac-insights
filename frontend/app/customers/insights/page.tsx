'use client';

import { useMemo, useState } from 'react';
import {
  useCustomerSegmentsInsights,
  useCustomerHealthInsights,
  useCustomerCompletenessInsights,
  useCustomerPlanChanges,
} from '@/hooks/useApi';
import {
  CustomerSegmentsInsightsResponse,
  CustomerPlanChangesResponse,
  CustomerPlanChange,
} from '@/lib/api';
import {
  InsightCard,
  LoadingState,
  ErrorDisplay,
  EmptyState,
  SummaryCard,
  ProgressBar,
} from '@/components/insights/shared';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { formatCurrency } from '@/lib/utils';

type InsightsTab = 'segments' | 'health' | 'completeness' | 'plan-changes';
type SegmentsView = keyof CustomerSegmentsInsightsResponse;

export default function CustomerInsightsPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');

  const [activeTab, setActiveTab] = useState<InsightsTab>('segments');
  const [segmentsView, setSegmentsView] = useState<SegmentsView>('by_status');
  const [planMonths, setPlanMonths] = useState(6);

  const { data: segmentsData, isLoading: segmentsLoading, error: segmentsError, mutate: mutateSegments } = useCustomerSegmentsInsights();
  const { data: healthData, isLoading: healthLoading, error: healthError, mutate: mutateHealth } = useCustomerHealthInsights();
  const { data: completenessData, isLoading: completenessLoading, error: completenessError, mutate: mutateCompleteness } = useCustomerCompletenessInsights();
  const { data: planChangesData, isLoading: planChangesLoading, error: planChangesError, mutate: mutatePlanChanges } = useCustomerPlanChanges(planMonths);

  const isLoading = segmentsLoading || healthLoading || completenessLoading || planChangesLoading;
  const error = segmentsError || healthError || completenessError || planChangesError;

  const totalCustomers = useMemo(() => {
    if (!segmentsData?.by_status) return 0;
    return segmentsData.by_status.reduce((sum, item) => sum + item.count, 0);
  }, [segmentsData?.by_status]);

  const completenessTotals = useMemo(() => {
    const total = (completenessData as any)?.total_customers ?? 0;
    const overall = (completenessData as any)?.scores?.overall_completeness ?? 0;
    const critical = (completenessData as any)?.scores?.critical_completeness ?? 0;
    return {
      total: Number(total) || 0,
      overall: Number(overall) || 0,
      critical: Number(critical) || 0,
    };
  }, [completenessData]);

  const completenessFields = useMemo(() => {
    const fieldsMap = (completenessData as any)?.fields || {};
    const total = completenessTotals.total || 0;
    return Object.entries(fieldsMap).map(([name, value]) => {
      const count = (value as any)?.count ?? 0;
      const percent = (value as any)?.percent ?? (total > 0 ? (count / total) * 100 : 0);
      const missing = (value as any)?.missing ?? Math.max(total - count, 0);
      return { name, count, percent, missing, total };
    });
  }, [completenessData, completenessTotals.total]);

  if (authLoading || isLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  const tabs: Array<{ key: InsightsTab; label: string }> = [
    { key: 'segments', label: 'Segments' },
    { key: 'health', label: 'Health' },
    { key: 'completeness', label: 'Completeness' },
    { key: 'plan-changes', label: 'Plan Changes' },
  ];

const segmentViews: Array<{ key: SegmentsView; label: string; mrr?: boolean }> = [
  { key: 'by_status', label: 'By Status', mrr: true },
  { key: 'by_type', label: 'By Type', mrr: true },
  { key: 'by_billing', label: 'By Billing', mrr: true },
  { key: 'by_tenure', label: 'By Tenure' },
  { key: 'by_mrr', label: 'By MRR Tier' },
  { key: 'by_city', label: 'By City', mrr: true },
];

  const currentSegments = (segmentsData as CustomerSegmentsInsightsResponse | undefined)?.[segmentsView] || [];

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load customer insights"
          error={error}
          onRetry={() => {
            mutateSegments();
            mutateHealth();
            mutateCompleteness();
            mutatePlanChanges();
          }}
        />
      )}
      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-border pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab.key
                ? 'bg-teal-electric/20 text-teal-electric border-b-2 border-teal-electric'
                : 'text-slate-muted hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Segments Tab */}
      {activeTab === 'segments' && (
        <div className="space-y-6">
          <SummaryCard
            title="Total Customers"
            value={totalCustomers.toLocaleString()}
            subtitle="Across all segments"
            gradient="from-teal-500 to-teal-600"
          />

          <div className="flex flex-wrap gap-2">
            {segmentViews.map((view) => (
              <button
                key={view.key}
                onClick={() => setSegmentsView(view.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  segmentsView === view.key
                    ? 'bg-teal-electric text-slate-deep'
                    : 'bg-slate-elevated text-slate-muted hover:text-foreground'
                }`}
              >
                {view.label}
              </button>
            ))}
          </div>

          <InsightCard title={segmentViews.find((v) => v.key === segmentsView)?.label || 'Segments'}>
            <div className="space-y-3">
              {(currentSegments as Array<Record<string, unknown>>).map((item, index) => {
                const labelField = segmentViews.find((v) => v.key === segmentsView)?.key === 'by_billing' ? 'billing_type' :
                  segmentViews.find((v) => v.key === segmentsView)?.key === 'by_type' ? 'type' :
                  segmentViews.find((v) => v.key === segmentsView)?.key === 'by_status' ? 'status' :
                  segmentViews.find((v) => v.key === segmentsView)?.key === 'by_city' ? 'city' : 'segment';
                const label = String(item[labelField] || 'Unknown');
                const count = Number(item.count || 0);
                const mrrField = segmentViews.find((v) => v.key === segmentsView)?.mrr ? 'total_mrr' : null;
                const mrr = mrrField ? Number(item[mrrField] || 0) : null;
                const percent = totalCustomers > 0 ? (count / totalCustomers) * 100 : 0;

                return (
                  <div key={`${label}-${index}`} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between gap-3">
                        <span className="text-sm font-medium text-foreground truncate">
                          {label}
                        </span>
                        <div className="flex items-center gap-3 text-sm text-slate-muted">
                          <span>{count.toLocaleString()} ({percent.toFixed(1)}%)</span>
                          {mrr !== null && (
                            <span className="text-teal-electric font-medium">
                              {formatCurrency(mrr, 'NGN', { maximumFractionDigits: 0 })}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}

              {(currentSegments as Array<Record<string, unknown>>).length === 0 && (
                <EmptyState message="No segment data available" />
              )}
            </div>
          </InsightCard>
        </div>
      )}

      {/* Health Tab */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SummaryCard
              title="Active Customers"
              value={(healthData?.total_active_customers || 0).toString()}
              subtitle="Currently active"
              gradient="from-teal-500 to-teal-600"
            />
            <SummaryCard
              title="Overdue Rate"
              value={`${healthData?.payment_behavior.overdue_rate.toFixed(1) || '0.0'}%`}
              subtitle="Customers with overdue balances"
              gradient="from-amber-500 to-amber-600"
            />
            <SummaryCard
              title="At Risk"
              value={(healthData?.churn_indicators.at_risk_total || 0).toString()}
              subtitle="Churn indicators"
              gradient="from-red-500 to-red-600"
            />
          </div>

          <InsightCard title="Payment Behavior">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-slate-muted mb-1">Customers with overdue invoices</p>
                <p className="text-2xl font-mono text-coral-alert">
                  {healthData?.payment_behavior.customers_with_overdue || 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">Payment Timing</p>
                <div className="flex gap-2 flex-wrap text-sm">
                  <span className="px-2 py-1 rounded bg-slate-elevated text-slate-muted">Early: {healthData?.payment_behavior.payment_timing.early || 0}</span>
                  <span className="px-2 py-1 rounded bg-slate-elevated text-slate-muted">On Time: {healthData?.payment_behavior.payment_timing.on_time || 0}</span>
                  <span className="px-2 py-1 rounded bg-slate-elevated text-slate-muted">Late: {healthData?.payment_behavior.payment_timing.late || 0}</span>
                </div>
                <p className="text-xs text-slate-muted mt-1">
                  On-time rate: {healthData?.payment_behavior.payment_timing.on_time_rate.toFixed(1) || '0.0'}%
                </p>
              </div>
            </div>
          </InsightCard>

          <InsightCard title="Support & Churn Indicators">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-slate-muted mb-1">Customers with tickets (30d)</p>
                <p className="text-2xl font-mono text-foreground">
                  {healthData?.support_intensity.customers_with_tickets_30d || 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">High support customers</p>
                <p className="text-2xl font-mono text-amber-warn">
                  {healthData?.support_intensity.high_support_customers || 0}
                </p>
                <p className="text-xs text-slate-muted">
                  Rate: {healthData?.support_intensity.high_support_rate.toFixed(1) || '0.0'}%
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">Churn indicators</p>
                <div className="space-y-1 text-sm text-slate-muted">
                  <div>Recently cancelled (30d): {healthData?.churn_indicators.recently_cancelled_30d || 0}</div>
                  <div>Currently suspended: {healthData?.churn_indicators.currently_suspended || 0}</div>
                  <div>Total at risk: {healthData?.churn_indicators.at_risk_total || 0}</div>
                </div>
              </div>
            </div>
          </InsightCard>
        </div>
      )}

      {/* Completeness Tab */}
      {activeTab === 'completeness' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SummaryCard
              title="Overall Completeness"
              value={`${completenessTotals.overall.toFixed(0)}%`}
              subtitle={`${completenessTotals.total.toLocaleString()} customers`}
              gradient="from-blue-500 to-blue-600"
            />
            <SummaryCard
              title="Critical Completeness"
              value={`${completenessTotals.critical.toFixed(0)}%`}
              subtitle="Email, phone, signup date"
              gradient="from-teal-500 to-teal-600"
            />
          </div>

          <InsightCard title="Field Coverage">
            <div className="space-y-2 max-h-[420px] overflow-y-auto">
              {completenessFields.map((field) => (
                <div key={field.name} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-muted truncate">{field.name.replace(/_/g, ' ')}</span>
                      <span className="text-slate-muted ml-2">{field.percent.toFixed(0)}%</span>
                    </div>
                    <ProgressBar
                      value={field.percent}
                      max={100}
                      color={field.percent > 80 ? 'green' : field.percent > 50 ? 'yellow' : 'red'}
                    />
                  </div>
                  <span className="text-xs text-slate-muted whitespace-nowrap">
                    {field.count}/{field.total} filled
                  </span>
                </div>
              ))}
              {completenessFields.length === 0 && (
                <EmptyState message="No completeness data available. Try syncing your customer records." />
              )}
            </div>
          </InsightCard>

          {completenessData?.system_linkage && (
            <InsightCard title="System Linkage">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(completenessData.system_linkage).map(([key, value]: [string, { percent?: number; count?: number }]) => (
                  <div key={key} className="bg-slate-elevated rounded-lg p-3">
                    <div className="text-xs uppercase text-slate-muted mb-1">{key.replace(/_/g, ' ')}</div>
                    <div className="text-foreground text-lg font-mono">{(value.percent ?? 0).toFixed(1)}%</div>
                    <div className="text-xs text-slate-muted">{(value.count ?? 0).toLocaleString()} linked</div>
                  </div>
                ))}
              </div>
            </InsightCard>
          )}

          {completenessData?.recommendations && completenessData.recommendations.length > 0 && (
            <InsightCard title="Recommendations">
              <ul className="space-y-2">
                {completenessData.recommendations.map((rec, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-muted">
                    <span className="text-teal-electric mt-0.5 capitalize">{rec.priority}</span>
                    <div className="flex-1">
                      <div className="text-foreground font-medium">{rec.field}</div>
                      <div>{rec.issue}</div>
                      <div className="text-xs text-slate-muted mt-0.5">{rec.action}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </InsightCard>
          )}
        </div>
      )}

      {/* Plan Changes Tab */}
      {activeTab === 'plan-changes' && (
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-muted">Period:</label>
            <select
              value={planMonths}
              onChange={(e) => setPlanMonths(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric"
            >
              <option value={3}>Last 3 months</option>
              <option value={6}>Last 6 months</option>
              <option value={12}>Last 12 months</option>
            </select>
          </div>

          {planChangesData ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SummaryCard
                  title="Customers with Plan Changes"
                  value={(planChangesData.summary.customers_with_plan_changes || 0).toString()}
                  subtitle={`${planChangesData.summary.total_changes || 0} total changes`}
                  gradient="from-purple-500 to-purple-600"
                />
                <SummaryCard
                  title="Upgrades"
                  value={(planChangesData.summary.upgrades || 0).toString()}
                  subtitle="Upgrade count"
                  gradient="from-green-500 to-green-600"
                />
                <SummaryCard
                  title="Downgrades"
                  value={(planChangesData.summary.downgrades || 0).toString()}
                  subtitle="Downgrade count"
                  gradient="from-amber-500 to-amber-600"
                />
              </div>

              <InsightCard title="Revenue Impact">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-slate-muted">Upgrade MRR Gained</p>
                    <p className="text-2xl font-mono text-teal-electric">
                      {formatCurrency(planChangesData.revenue_impact.upgrade_mrr_gained, 'NGN')}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-muted">Downgrade MRR Lost</p>
                    <p className="text-2xl font-mono text-coral-alert">
                      {formatCurrency(planChangesData.revenue_impact.downgrade_mrr_lost, 'NGN')}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-muted">Net MRR Change</p>
                    <p className="text-2xl font-mono text-foreground">
                      {formatCurrency(planChangesData.revenue_impact.net_mrr_change, 'NGN')}
                    </p>
                  </div>
                </div>
                <div className="text-xs text-slate-muted mt-2">
                  Upgrade/Downgrade Ratio: {planChangesData.rates.upgrade_to_downgrade_ratio.toFixed(2)}
                </div>
              </InsightCard>

              <InsightCard title="Common Transitions">
                {planChangesData.common_transitions.length === 0 ? (
                  <EmptyState message="No plan transition data available" />
                ) : (
                  <div className="space-y-2">
                    {planChangesData.common_transitions.map((t, i: number) => (
                      <div key={`${t.transition}-${i}`} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
                        <div>
                          <p className="text-foreground text-sm font-medium">{t.transition}</p>
                          <p className="text-xs text-slate-muted capitalize">{t.type}</p>
                        </div>
                        <span className="text-sm text-slate-muted">{t.count} customers</span>
                      </div>
                    ))}
                  </div>
                )}
              </InsightCard>

              <InsightCard title="Recent Plan Changes">
                {planChangesData.recent_changes.length === 0 ? (
                  <EmptyState message="No recent plan changes" />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-border">
                          <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Customer</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">From → To</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-slate-muted uppercase">Price Change</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Type</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-border">
                        {planChangesData.recent_changes.map((change: CustomerPlanChange) => (
                          <tr key={`${change.customer_id}-${change.date}`} className="hover:bg-slate-elevated/50">
                            <td className="px-4 py-3 text-foreground font-medium">{change.customer_id}</td>
                            <td className="px-4 py-3 text-slate-muted text-sm">
                              {change.from_plan} → {change.to_plan}
                            </td>
                            <td className="px-4 py-3 text-right text-sm font-mono text-foreground">
                              {formatCurrency(change.price_change, 'NGN')}
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-muted capitalize">{change.change_type}</td>
                            <td className="px-4 py-3 text-xs text-slate-muted">
                              {new Date(change.date).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </InsightCard>
            </>
          ) : (
            <EmptyState message="No plan change data available" />
          )}
        </div>
      )}
    </div>
  );
}
