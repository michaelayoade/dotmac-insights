'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { CheckCircle2, Users } from 'lucide-react';
import { LoadingState, PageHeader } from '@/components/ui';
import { ErrorDisplay, EmptyState } from '@/components/insights/shared';
import { useUnifiedContacts, type UnifiedContactsResponse } from '@/hooks/useApi';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const QUALIFICATION_LABELS: Record<string, string> = {
  unqualified: 'Unqualified',
  cold: 'Cold',
  warm: 'Warm',
  hot: 'Hot',
  qualified: 'Qualified',
};

const QUALIFICATION_COLORS: Record<string, string> = {
  unqualified: '#64748b',
  cold: '#60a5fa',
  warm: '#f59e0b',
  hot: '#fb923c',
  qualified: '#34d399',
};

export default function CRMQualificationPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = useUnifiedContacts({
    page: 1,
    page_size: 200,
    contact_type: 'lead',
    sort_by: 'created_at',
    sort_order: 'desc',
  }, { isPaused: () => !canFetch }) as {
    data?: UnifiedContactsResponse;
    isLoading: boolean;
    error?: unknown;
  };

  const chartData = useMemo(() => {
    const counts: Record<string, number> = {};
    (data?.items || []).forEach((contact) => {
      const key = contact.lead_qualification || 'unqualified';
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.keys(QUALIFICATION_LABELS).map((key) => ({
      key,
      label: QUALIFICATION_LABELS[key],
      value: counts[key] || 0,
      color: QUALIFICATION_COLORS[key],
    }));
  }, [data]);

  const total = chartData.reduce((sum, item) => sum + item.value, 0);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view qualification data."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {Boolean(error) && (
        <ErrorDisplay
          message="Failed to load qualification analytics"
          error={error as Error}
        />
      )}
      <PageHeader
        title="Qualification"
        subtitle="Lead scoring and readiness"
        icon={CheckCircle2}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
      />

      {total > 0 ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6 space-y-4">
          <div className="flex items-center justify-between text-sm text-slate-muted">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-teal-electric" />
              <span>Latest 200 leads</span>
            </div>
            <span>Total: {total}</span>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    color: '#e2e8f0',
                  }}
                  cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.key} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <EmptyState message="No qualification data available yet." />
      )}
    </div>
  );
}
