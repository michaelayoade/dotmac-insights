'use client';

import { useAnomalies } from '@/hooks/useApi';
import { Anomaly } from '@/lib/api';
import {
  InsightCard,
  InsightBadge,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';
import { CheckCircle } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function AnomaliesPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const canFetch = hasAccess && !authLoading;
  const { data, isLoading, error, mutate } = useAnomalies({ isPaused: () => !canFetch });

  if (authLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  if (isLoading) {
    return <LoadingState />;
  }

  const getSeverityColor = (severity: string): string => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'red';
      case 'warning': return 'yellow';
      case 'info': return 'blue';
      default: return 'gray';
    }
  };

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load anomalies"
          error={error}
          onRetry={() => mutate()}
        />
      )}
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Total Issues</div>
          <div className="text-2xl font-bold text-foreground">{data?.summary.total_issues || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-coral-alert/30 p-4">
          <div className="text-sm text-slate-muted">Critical</div>
          <div className="text-2xl font-bold text-coral-alert">{data?.summary.critical || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-amber-warn/30 p-4">
          <div className="text-sm text-slate-muted">Warnings</div>
          <div className="text-2xl font-bold text-amber-warn">{data?.summary.warning || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-blue-500/30 p-4">
          <div className="text-sm text-slate-muted">Info</div>
          <div className="text-2xl font-bold text-blue-400">{data?.summary.info || 0}</div>
        </div>
      </div>

      {/* Anomaly List */}
      <InsightCard title="Detected Anomalies">
        <div className="space-y-4">
          {data?.anomalies.map((anomaly: Anomaly, index: number) => (
            <div
              key={index}
              className={`p-4 rounded-lg border ${
                anomaly.severity === 'critical' ? 'border-coral-alert/30 bg-coral-alert/5' :
                anomaly.severity === 'warning' ? 'border-amber-warn/30 bg-amber-warn/5' :
                'border-blue-500/30 bg-blue-500/5'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <InsightBadge color={getSeverityColor(anomaly.severity)}>
                      {anomaly.severity}
                    </InsightBadge>
                    <InsightBadge color="gray">{anomaly.type}</InsightBadge>
                    <InsightBadge color="purple">{anomaly.entity}</InsightBadge>
                  </div>
                  <p className="text-sm text-slate-muted">{anomaly.description}</p>
                  <p className="text-xs text-slate-muted mt-1">
                    Affected: {anomaly.affected_count} records
                  </p>
                </div>
              </div>
            </div>
          ))}
          {(!data?.anomalies || data.anomalies.length === 0) && (
            <EmptyState
              title="All Clear"
              message="No anomalies detected in your data. Your records look healthy."
              icon={<CheckCircle className="w-8 h-8 text-green-500" />}
            />
          )}
        </div>
      </InsightCard>

      {/* Recommendations */}
      {data?.recommendations && data.recommendations.length > 0 && (
        <InsightCard title="Recommendations">
          <ul className="space-y-2">
            {data.recommendations.map((rec: string, i: number) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-muted">
                <span className="text-teal-electric mt-0.5">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </InsightCard>
      )}
    </div>
  );
}
