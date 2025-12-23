'use client';

import { useMemo } from 'react';
import { useCustomerCompletenessInsights } from '@/hooks/useApi';
import { CustomerCompletenessField } from '@/lib/api';
import {
  InsightCard,
  ProgressBar,
  LoadingState,
  ErrorDisplay,
  EmptyState,
  SummaryCard,
} from '@/components/insights/shared';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function CompletenessPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const canFetch = hasAccess && !authLoading;

  // All hooks must be called before any conditional returns
  const { data, isLoading, error, mutate } = useCustomerCompletenessInsights({
    isPaused: () => !canFetch,
  });

  const totalCustomers = useMemo(() => {
    const value = (data as any)?.total ?? data?.total_customers ?? 0;
    return Number.isFinite(value) ? Number(value) : 0;
  }, [data]);

  const overallScore = useMemo(() => {
    const score = (data as any)?.scores?.overall_completeness ?? 0;
    return Number.isFinite(score) ? Number(score) : 0;
  }, [data]);

  const criticalScore = useMemo(() => {
    const score = (data as any)?.scores?.critical_completeness ?? 0;
    return Number.isFinite(score) ? Number(score) : 0;
  }, [data]);

  const normalizedFields = useMemo(() => {
    const fieldEntries = Object.entries((data as any)?.fields || {});
    return fieldEntries
      .map(([name, value]) => {
        const count = (value as any)?.count ?? 0;
        const percent = (value as any)?.percent ?? 0;
        const missing = (value as any)?.missing ?? Math.max(totalCustomers - count, 0);
        return {
          field: name,
          filled: count,
          total: totalCustomers,
          percent,
          missing,
        } as CustomerCompletenessField;
      })
      .sort((a, b) => a.percent - b.percent);
  }, [data, totalCustomers]);

  // Auth loading state
  if (authLoading) {
    return <LoadingState />;
  }

  // Access denied state
  if (!hasAccess) {
    return <AccessDenied />;
  }

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load data completeness"
          error={error}
          onRetry={() => mutate()}
        />
      )}
      {/* Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SummaryCard
          title="Overall Completeness"
          value={`${overallScore.toFixed(0)}%`}
          subtitle={`${totalCustomers.toLocaleString()} customers`}
          gradient="from-blue-500 to-blue-600"
        />
        <SummaryCard
          title="Critical Completeness"
          value={`${criticalScore.toFixed(0)}%`}
          subtitle="Email, phone, signup date"
          gradient="from-teal-500 to-teal-600"
        />
        <InsightCard title="Quick View">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-muted">Completion Score</span>
              <span className="font-semibold text-foreground">{overallScore.toFixed(1)}%</span>
            </div>
            <ProgressBar
              value={overallScore}
              max={100}
              color={overallScore > 80 ? 'green' : overallScore > 50 ? 'yellow' : 'red'}
            />
          </div>
        </InsightCard>
      </div>

      {/* Field Coverage */}
      <InsightCard title="Field Coverage">
        <div className="space-y-2 max-h-[420px] overflow-y-auto">
          {normalizedFields.map((field: CustomerCompletenessField) => (
            <div key={field.field} className="flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-slate-muted truncate">{field.field}</span>
                  <span className="text-slate-muted ml-2">{field.percent.toFixed(0)}%</span>
                </div>
                <ProgressBar
                  value={field.percent}
                  max={100}
                  color={field.percent > 80 ? 'green' : field.percent > 50 ? 'yellow' : 'red'}
                />
              </div>
              <span className="text-xs text-slate-muted whitespace-nowrap">
                {field.filled}/{field.total} filled
              </span>
            </div>
          ))}
          {normalizedFields.length === 0 && (
            <EmptyState
              message="No completeness data available. Try syncing your customer records."
            />
          )}
        </div>
      </InsightCard>

      {/* Recommendations */}
      {data?.recommendations && data.recommendations.length > 0 && (
        <InsightCard title="Recommendations">
          <ul className="space-y-2">
            {data.recommendations.map((rec: any, i: number) => (
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

      {/* System Linkage */}
      {data?.system_linkage && (
        <InsightCard title="System Linkage">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {Object.entries(data.system_linkage).map(([key, value]: [string, any]) => (
              <div key={key} className="bg-slate-elevated rounded-lg p-3">
                <div className="text-xs uppercase text-slate-muted mb-1">{key.replace(/_/g, ' ')}</div>
                <div className="text-foreground text-lg font-mono">{value.percent?.toFixed(1) ?? 0}%</div>
                <div className="text-xs text-slate-muted">{value.count?.toLocaleString() || 0} linked</div>
              </div>
            ))}
          </div>
        </InsightCard>
      )}
    </div>
  );
}
