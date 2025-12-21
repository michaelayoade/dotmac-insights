'use client';

import {
  useDataCompleteness,
  useDataAvailability,
  useAnomalies,
  useFinancialInsights,
} from '@/hooks/useApi';
import {
  InsightCard,
  SummaryCard,
  ProgressBar,
  LoadingState,
  ErrorDisplay,
} from '@/components/insights/shared';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function OverviewPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const canFetch = hasAccess && !authLoading;
  const swrGuard = { isPaused: () => !canFetch };

  const { data: completeness, isLoading: loadingCompleteness, error: errorCompleteness, mutate: mutateCompleteness } = useDataCompleteness(swrGuard);
  const { data: availability, isLoading: loadingAvailability, error: errorAvailability, mutate: mutateAvailability } = useDataAvailability(swrGuard);
  const { data: anomalies, isLoading: loadingAnomalies, error: errorAnomalies, mutate: mutateAnomalies } = useAnomalies(swrGuard);
  const { data: financial, isLoading: loadingFinancial, error: errorFinancial, mutate: mutateFinancial } = useFinancialInsights(swrGuard);

  if (authLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  const isLoading = loadingCompleteness || loadingAvailability || loadingAnomalies || loadingFinancial;
  const hasError = errorCompleteness || errorAvailability || errorAnomalies || errorFinancial;

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {hasError && (
        <ErrorDisplay
          message="Failed to load insights overview"
          error={errorCompleteness || errorAvailability || errorAnomalies || errorFinancial}
          onRetry={() => {
            mutateCompleteness();
            mutateAvailability();
            mutateAnomalies();
            mutateFinancial();
          }}
        />
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Entities"
          value={availability?.summary?.total_entities ?? 0}
          subtitle={`${availability?.summary?.total_records?.toLocaleString() ?? 0} records`}
          gradient="from-blue-500 to-blue-600"
        />
        <SummaryCard
          title="Well Populated"
          value={availability?.summary?.well_populated ?? 0}
          subtitle="entities with good data"
          gradient="from-green-500 to-green-600"
        />
        <SummaryCard
          title="Needs Attention"
          value={availability?.summary?.needs_attention ?? 0}
          subtitle="entities with gaps"
          gradient="from-amber-500 to-amber-600"
        />
        <SummaryCard
          title="Data Issues"
          value={anomalies?.summary?.total_issues ?? 0}
          subtitle={`${anomalies?.summary?.critical ?? 0} critical`}
          gradient="from-red-500 to-red-600"
        />
      </div>

      {/* Data Availability Overview */}
      <InsightCard title="Data Availability by Entity">
        <div className="space-y-3">
          {availability?.available?.slice(0, 10).map((entity: any) => (
            <div key={entity.entity} className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex justify-between mb-1">
                  <span className="text-sm font-medium text-foreground capitalize">
                    {entity.entity.replace(/_/g, ' ')}
                  </span>
                  <span className="text-sm text-slate-muted">
                    {entity.total.toLocaleString()} records
                  </span>
                </div>
                <ProgressBar
                  value={entity.total}
                  max={Math.max(...(availability?.available?.map((e: any) => e.total) || [1]))}
                  color={entity.total > 100 ? 'green' : entity.total > 10 ? 'yellow' : 'red'}
                />
              </div>
            </div>
          ))}
          {(!availability?.available || availability.available.length === 0) && (
            <p className="text-sm text-slate-muted">No data availability information yet</p>
          )}
        </div>
      </InsightCard>

      {/* Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InsightCard title="Priority Recommendations">
          <ul className="space-y-2">
            {completeness?.recommendations?.slice(0, 5).map((rec: any, i: number) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-muted">
                <span className="text-teal-electric mt-0.5">•</span>
                {rec}
              </li>
            ))}
            {(!completeness?.recommendations || completeness.recommendations.length === 0) && (
              <li className="text-sm text-slate-muted">No recommendations at this time</li>
            )}
          </ul>
        </InsightCard>

        <InsightCard title="Financial Summary">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-muted">Total MRR</span>
              <span className="font-semibold text-teal-electric">
                {financial?.revenue?.total_mrr?.toLocaleString(undefined, { style: 'currency', currency: 'NGN' }) ?? 'N/A'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-muted">Outstanding</span>
              <span className="font-semibold text-amber-warn">
                {financial?.revenue?.total_outstanding?.toLocaleString(undefined, { style: 'currency', currency: 'NGN' }) ?? 'N/A'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-muted">Collection Rate</span>
              <span className="font-semibold text-blue-400">
                {financial?.revenue?.collection_rate?.toFixed(1) ?? 0}%
              </span>
            </div>
          </div>
        </InsightCard>
      </div>
    </div>
  );
}
