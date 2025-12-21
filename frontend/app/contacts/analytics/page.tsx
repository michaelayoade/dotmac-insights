'use client';

import {
  Activity,
  BarChart3,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react';
import {
  useUnifiedContactsDashboard,
  useUnifiedContactsFunnel,
  type UnifiedContactsDashboard,
  type UnifiedContactsFunnel,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/ui';
import { EmptyState, ErrorDisplay, LoadingState } from '@/components/insights/shared';

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatCurrency(value: number, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  className?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, className }: StatCardProps) {
  return (
    <div className={cn('bg-slate-card rounded-xl border border-slate-border p-5', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
          {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
        </div>
        <div className="p-3 bg-slate-elevated rounded-lg">
          <Icon className="w-5 h-5 text-teal-electric" />
        </div>
      </div>
    </div>
  );
}

export default function ContactsAnalyticsPage() {
  const {
    data: dashboard,
    isLoading: dashboardLoading,
    error: dashboardError,
  } = useUnifiedContactsDashboard(30) as {
    data?: UnifiedContactsDashboard;
    isLoading: boolean;
    error?: unknown;
  };
  const {
    data: funnel,
    isLoading: funnelLoading,
    error: funnelError,
  } = useUnifiedContactsFunnel(30) as {
    data?: UnifiedContactsFunnel;
    isLoading: boolean;
    error?: unknown;
  };

  const overview = dashboard?.overview || {};
  const status = dashboard?.status_distribution || {};
  const financials = dashboard?.financials || {};
  const period = dashboard?.period_metrics || {};

  const statusTotal =
    (status.active || 0) + (status.inactive || 0) + (status.churned || 0);

  const funnelCounts = funnel?.funnel || {};
  const funnelRates = funnel?.conversion_rates || {};

  if ((dashboardLoading || funnelLoading) && !dashboard && !funnel) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {Boolean(dashboardError || funnelError) && (
        <ErrorDisplay
          message="Failed to load contact analytics"
          error={(dashboardError || funnelError) as Error}
        />
      )}
      <PageHeader
        title="Contact Analytics"
        subtitle="Performance and engagement insights"
        icon={BarChart3}
        iconClassName="bg-teal-500/10 border border-teal-500/30"
      />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Contacts"
          value={formatNumber(overview.total_contacts || 0)}
          icon={Users}
        />
        <StatCard
          title="Leads"
          value={formatNumber(overview.leads || 0)}
          subtitle={`Prospects: ${formatNumber(overview.prospects || 0)}`}
          icon={TrendingUp}
        />
        <StatCard
          title="Customers"
          value={formatNumber(overview.customers || 0)}
          icon={Target}
        />
        <StatCard
          title="Total MRR"
          value={formatCurrency(financials.total_mrr || 0)}
          subtitle={`Avg: ${formatCurrency(financials.avg_mrr || 0)}`}
          icon={Activity}
        />
      </div>

      {/* Period Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard
          title="New Contacts (30d)"
          value={formatNumber(period.new_contacts || 0)}
          subtitle={`Change: ${formatNumber(period.new_contacts_change || 0)}`}
          icon={Users}
        />
        <StatCard
          title="Engagements (30d)"
          value={formatNumber(period.total_engagements || 0)}
          subtitle={`Change: ${formatNumber(period.total_engagements_change || 0)}`}
          icon={Activity}
        />
      </div>

      {/* Status Distribution */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">Status Distribution</h3>
        {statusTotal > 0 ? (
          <div className="space-y-3">
            {[
              { label: 'Active', value: status.active || 0, color: 'bg-emerald-500' },
              { label: 'Inactive', value: status.inactive || 0, color: 'bg-slate-500' },
              { label: 'Churned', value: status.churned || 0, color: 'bg-rose-500' },
            ].map((item) => {
              const pct = statusTotal ? (item.value / statusTotal) * 100 : 0;
              return (
                <div key={item.label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-muted">{item.label}</span>
                    <span className="text-foreground font-medium">
                      {formatNumber(item.value)} ({formatPercent(pct)})
                    </span>
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                    <div className={cn('h-full', item.color)} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState message="No status distribution data available yet." />
        )}
      </div>

      {/* Funnel */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">Funnel (30d)</h3>
        {(funnelCounts.leads_created || funnelCounts.prospects_qualified || funnelCounts.customers_converted) ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-elevated rounded-lg p-4">
              <p className="text-slate-muted text-sm">Leads Created</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {formatNumber(funnelCounts.leads_created || 0)}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <p className="text-slate-muted text-sm">Prospects Qualified</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {formatNumber(funnelCounts.prospects_qualified || 0)}
              </p>
              <p className="text-xs text-slate-muted mt-2">
                Lead → Prospect: {formatPercent(funnelRates.lead_to_prospect || 0)}
              </p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-4">
              <p className="text-slate-muted text-sm">Customers Converted</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {formatNumber(funnelCounts.customers_converted || 0)}
              </p>
              <p className="text-xs text-slate-muted mt-2">
                Overall: {formatPercent(funnelRates.overall || 0)}
              </p>
            </div>
          </div>
        ) : (
          <EmptyState message="No funnel data available yet." />
        )}
      </div>
    </div>
  );
}
