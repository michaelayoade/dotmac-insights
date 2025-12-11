'use client';

import { useMemo, useState } from 'react';
import { useCustomerSegmentsInsights } from '@/hooks/useApi';
import { CustomerSegmentsInsightsResponse } from '@/lib/api';
import {
  InsightCard,
  SummaryCard,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { formatCurrency } from '@/lib/utils';

type ViewKey = keyof CustomerSegmentsInsightsResponse;

export default function SegmentsPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const canFetch = hasAccess && !authLoading;
  const { data, isLoading, error, mutate } = useCustomerSegmentsInsights({ isPaused: () => !canFetch });
  const [activeView, setActiveView] = useState<ViewKey>('by_status');

  const totalCustomers = useMemo(() => {
    if (!data?.by_status) return 0;
    return data.by_status.reduce((sum, item) => sum + item.count, 0);
  }, [data?.by_status]);

  const viewConfigs: Array<{
    key: ViewKey;
    label: string;
    items: unknown[];
    labelField: string;
    mrrField?: string;
  }> = [
    { key: 'by_status', label: 'By Status', items: data?.by_status || [], labelField: 'status', mrrField: 'total_mrr' },
    { key: 'by_type', label: 'By Type', items: data?.by_type || [], labelField: 'type', mrrField: 'total_mrr' },
    { key: 'by_billing', label: 'By Billing', items: data?.by_billing || [], labelField: 'billing_type', mrrField: 'total_mrr' },
    { key: 'by_tenure', label: 'By Tenure', items: data?.by_tenure || [], labelField: 'segment' },
    { key: 'by_mrr', label: 'By MRR Tier', items: data?.by_mrr || [], labelField: 'segment' },
  ];

  const currentView = viewConfigs.find((view) => view.key === activeView) || viewConfigs[0];
  const currentItems = currentView.items as Array<Record<string, unknown>>;

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
        message="Failed to load customer segments"
        error={error}
        onRetry={() => mutate()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <SummaryCard
        title="Total Customers"
        value={totalCustomers.toLocaleString()}
        gradient="from-purple-500 to-purple-600"
      />

      {/* View Selector */}
      <div className="flex flex-wrap gap-2">
        {viewConfigs.map((view) => (
          <button
            key={view.key}
            onClick={() => setActiveView(view.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeView === view.key
                ? 'bg-teal-electric text-slate-deep'
                : 'bg-slate-elevated text-slate-muted hover:text-white'
            }`}
          >
            {view.label}
          </button>
        ))}
      </div>

      <InsightCard title={currentView.label}>
        <div className="space-y-3">
          {currentItems.map((item, index) => {
            const label = String(item[currentView.labelField] || 'Unknown');
            const count = Number(item.count || 0);
            const mrr = currentView.mrrField ? Number(item[currentView.mrrField] || 0) : null;
            const percent = totalCustomers > 0 ? (count / totalCustomers) * 100 : 0;

            return (
              <div key={`${label}-${index}`} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between gap-3">
                    <span className="text-sm font-medium text-white truncate">
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
          {currentItems.length === 0 && (
            <EmptyState message="No segment data available. Try syncing your customer data." />
          )}
        </div>
      </InsightCard>
    </div>
  );
}
