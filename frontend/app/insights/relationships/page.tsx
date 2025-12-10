'use client';

import { useRelationshipMap } from '@/hooks/useApi';
import { EntityRelationship } from '@/lib/api';
import {
  InsightCard,
  SummaryCard,
  ProgressBar,
  InsightBadge,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';

export default function RelationshipsPage() {
  const { data, isLoading, error, mutate } = useRelationshipMap();

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load relationship map"
        error={error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data?.entities || data.entities.length === 0) {
    return (
      <EmptyState
        title="No Relationship Data"
        message="Entity relationship data is not yet available. Try syncing your data first."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Overall Linkage */}
      <SummaryCard
        title="Overall Data Linkage Rate"
        value={`${data?.data_quality.overall_linkage_rate.toFixed(1)}%`}
        gradient="from-indigo-500 to-indigo-600"
      />

      {/* Link Quality */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InsightCard title="Strong Links">
          <div className="flex flex-wrap gap-2">
            {data?.data_quality.strong_links.map((link, i) => (
              <InsightBadge key={i} color="green">{link}</InsightBadge>
            ))}
            {data?.data_quality.strong_links.length === 0 && (
              <span className="text-sm text-slate-muted">None identified</span>
            )}
          </div>
        </InsightCard>
        <InsightCard title="Weak Links">
          <div className="flex flex-wrap gap-2">
            {data?.data_quality.weak_links.map((link, i) => (
              <InsightBadge key={i} color="yellow">{link}</InsightBadge>
            ))}
            {data?.data_quality.weak_links.length === 0 && (
              <span className="text-sm text-slate-muted">None identified</span>
            )}
          </div>
        </InsightCard>
        <InsightCard title="Missing Links">
          <div className="flex flex-wrap gap-2">
            {data?.data_quality.missing_links.map((link, i) => (
              <InsightBadge key={i} color="red">{link}</InsightBadge>
            ))}
            {data?.data_quality.missing_links.length === 0 && (
              <span className="text-sm text-slate-muted">None identified</span>
            )}
          </div>
        </InsightCard>
      </div>

      {/* Entity Relationships */}
      <InsightCard title="Entity Relationship Summary">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-border">
            <thead>
              <tr className="bg-slate-elevated">
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Entity</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Total</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Linked</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Orphaned</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Link Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {data?.entities.map((entity: EntityRelationship) => (
                <tr key={entity.entity} className="hover:bg-slate-elevated/50">
                  <td className="px-4 py-3 text-sm font-medium text-white capitalize">
                    {entity.entity.replace(/_/g, ' ')}
                  </td>
                  <td className="px-4 py-3 text-sm text-white">{entity.total.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm text-teal-electric">{entity.linked.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm text-coral-alert">{entity.orphaned.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-20">
                        <ProgressBar
                          value={entity.link_rate}
                          max={100}
                          color={entity.link_rate > 80 ? 'green' : entity.link_rate > 50 ? 'yellow' : 'red'}
                        />
                      </div>
                      <span className="text-sm text-white">{entity.link_rate.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </InsightCard>

      {/* Recommendations */}
      {data?.recommendations && data.recommendations.length > 0 && (
        <InsightCard title="Recommendations">
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
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
