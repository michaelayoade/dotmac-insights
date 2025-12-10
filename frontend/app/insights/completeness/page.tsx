'use client';

import { useDataCompleteness } from '@/hooks/useApi';
import { FieldCompleteness } from '@/lib/api';
import {
  InsightCard,
  ProgressBar,
  InsightBadge,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';

export default function CompletenessPage() {
  const { data, isLoading, error, mutate } = useDataCompleteness();

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load data completeness"
        error={error}
        onRetry={() => mutate()}
      />
    );
  }

  const entities = Object.entries(data?.entities || {});

  return (
    <div className="space-y-6">
      {/* Priority Fields */}
      {data?.priority_fields && data.priority_fields.length > 0 && (
        <InsightCard title="Priority Fields to Complete">
          <div className="flex flex-wrap gap-2">
            {data.priority_fields.map((field) => (
              <InsightBadge key={field} color="red">{field}</InsightBadge>
            ))}
          </div>
        </InsightCard>
      )}

      {/* Entity Completeness */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {entities.map(([entityName, entityData]) => (
          <InsightCard key={entityName} title={entityName.replace(/_/g, ' ').toUpperCase()}>
            <div className="space-y-1 mb-4">
              <div className="flex justify-between text-sm">
                <span className="text-slate-muted">Overall Score</span>
                <span className="font-semibold text-white">
                  {entityData.overall_score.toFixed(0)}%
                </span>
              </div>
              <ProgressBar
                value={entityData.overall_score}
                max={100}
                color={entityData.overall_score > 80 ? 'green' : entityData.overall_score > 50 ? 'yellow' : 'red'}
              />
              <div className="text-xs text-slate-muted">{entityData.total} records</div>
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {entityData.fields.slice(0, 15).map((field: FieldCompleteness) => (
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
                </div>
              ))}
            </div>
          </InsightCard>
        ))}
      </div>

      {/* Recommendations */}
      <InsightCard title="Recommendations">
        <ul className="space-y-2">
          {data?.recommendations.map((rec, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-muted">
              <span className="text-teal-electric mt-0.5">•</span>
              {rec}
            </li>
          ))}
        </ul>
      </InsightCard>
    </div>
  );
}
