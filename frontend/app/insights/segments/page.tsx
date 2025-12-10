'use client';

import { useState } from 'react';
import { useCustomerSegments } from '@/hooks/useApi';
import { CustomerSegment } from '@/lib/api';
import {
  InsightCard,
  SummaryCard,
  ProgressBar,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';

export default function SegmentsPage() {
  const { data, isLoading, error, mutate } = useCustomerSegments();
  const [selectedView, setSelectedView] = useState<string>('by_status');

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

  const segmentViews = [
    { key: 'by_status', label: 'By Status' },
    { key: 'by_type', label: 'By Type' },
    { key: 'by_billing_type', label: 'By Billing' },
    { key: 'by_tenure', label: 'By Tenure' },
    { key: 'by_mrr_tier', label: 'By MRR Tier' },
    { key: 'by_geography', label: 'By Geography' },
    { key: 'by_pop', label: 'By POP' },
  ];

  const currentData = (data as unknown as Record<string, CustomerSegment[]>)?.[selectedView] || [];
  const colors = ['teal', 'green', 'purple', 'yellow', 'red', 'blue'];

  return (
    <div className="space-y-6">
      {/* Total Customers */}
      <SummaryCard
        title="Total Customers"
        value={data?.total_customers.toLocaleString() || 0}
        gradient="from-purple-500 to-purple-600"
      />

      {/* View Selector */}
      <div className="flex flex-wrap gap-2">
        {segmentViews.map((view) => (
          <button
            key={view.key}
            onClick={() => setSelectedView(view.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selectedView === view.key
                ? 'bg-teal-electric text-slate-deep'
                : 'bg-slate-elevated text-slate-muted hover:text-white'
            }`}
          >
            {view.label}
          </button>
        ))}
      </div>

      {/* Segment Data */}
      <InsightCard title={segmentViews.find(v => v.key === selectedView)?.label || 'Segments'}>
        <div className="space-y-3">
          {currentData.map((segment: CustomerSegment, index: number) => (
            <div key={index} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
              <div className="flex-1">
                <div className="flex justify-between mb-1">
                  <span className="text-sm font-medium text-white">
                    {segment.segment || 'Unknown'}
                  </span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-slate-muted">
                      {segment.count} ({segment.percentage.toFixed(1)}%)
                    </span>
                    {segment.total_mrr !== undefined && (
                      <span className="text-sm text-teal-electric font-medium">
                        {segment.total_mrr.toLocaleString(undefined, { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 })}
                      </span>
                    )}
                  </div>
                </div>
                <ProgressBar
                  value={segment.percentage}
                  max={100}
                  color={colors[index % colors.length]}
                />
              </div>
            </div>
          ))}
          {currentData.length === 0 && (
            <EmptyState
              message="No segment data available for this view. Try syncing your customer data."
            />
          )}
        </div>
      </InsightCard>
    </div>
  );
}
