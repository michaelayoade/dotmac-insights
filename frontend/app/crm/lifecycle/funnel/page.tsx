'use client';

import { Target, TrendingUp, Users } from 'lucide-react';
import { LoadingState, PageHeader } from '@/components/ui';
import { EmptyState, ErrorDisplay } from '@/components/insights/shared';
import { useUnifiedContactsFunnel, type UnifiedContactsFunnel } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export default function CRMFunnelPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = useUnifiedContactsFunnel(30, undefined, { isPaused: () => !canFetch }) as {
    data?: UnifiedContactsFunnel;
    isLoading: boolean;
    error?: unknown;
  };

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view the sales funnel."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading && !data) {
    return <LoadingState />;
  }

  const funnel = data?.funnel || {};
  const rates = data?.conversion_rates || {};
  const maxValue = Math.max(
    funnel.leads_created || 0,
    funnel.prospects_qualified || 0,
    funnel.customers_converted || 0
  );

  const stages = [
    {
      label: 'Leads Created',
      value: funnel.leads_created || 0,
      color: 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300',
    },
    {
      label: 'Prospects Qualified',
      value: funnel.prospects_qualified || 0,
      color: 'bg-amber-500/20 border-amber-500/40 text-amber-300',
      rate: `Lead → Prospect: ${formatPercent(rates.lead_to_prospect || 0)}`,
    },
    {
      label: 'Customers Converted',
      value: funnel.customers_converted || 0,
      color: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300',
      rate: `Overall: ${formatPercent(rates.overall || 0)}`,
    },
  ];

  return (
    <div className="space-y-6">
      {Boolean(error) && (
        <ErrorDisplay
          message="Failed to load funnel analytics"
          error={error as Error}
        />
      )}
      <PageHeader
        title="Sales Funnel"
        subtitle="Conversion stages and drop-offs"
        icon={TrendingUp}
        iconClassName="bg-teal-500/10 border border-teal-500/30"
      />

      {maxValue > 0 ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm text-slate-muted">
            <Target className="w-4 h-4 text-teal-electric" />
            <span>Last 30 days</span>
          </div>
          <div className="space-y-3">
            {stages.map((stage, index) => {
              const widthPct = maxValue > 0 ? (stage.value / maxValue) * 100 : 0;
              return (
                <div key={stage.label} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-slate-muted" />
                      <span className="text-foreground">{stage.label}</span>
                    </div>
                    <span className="text-foreground font-medium">{formatNumber(stage.value)}</span>
                  </div>
                  <div className="h-10 bg-slate-elevated rounded-lg overflow-hidden border border-slate-border">
                    <div
                      className={cn('h-full border rounded-lg flex items-center px-3 text-sm font-semibold', stage.color)}
                      style={{ width: `${Math.max(widthPct, 8)}%` }}
                    >
                      {stage.rate || `${formatPercent(widthPct)} of top`}
                    </div>
                  </div>
                  {index < stages.length - 1 && (
                    <div className="h-px bg-slate-border/60" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <EmptyState message="No funnel activity recorded yet." />
      )}
    </div>
  );
}
