'use client';

import { useFinanceDashboard, useFinanceAging, useFinanceRevenueTrend } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  FileText,
  CreditCard,
  Clock,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';

function formatCurrency(value: number, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-NG').format(value);
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  className?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, trend, trendValue, className }: StatCardProps) {
  return (
    <div className={cn('bg-slate-card rounded-xl border border-slate-border p-6', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-slate-muted text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
          {trend && trendValue && (
            <div className={cn(
              'flex items-center gap-1 mt-2 text-sm',
              trend === 'up' && 'text-green-400',
              trend === 'down' && 'text-red-400',
              trend === 'neutral' && 'text-slate-muted'
            )}>
              {trend === 'up' && <TrendingUp className="w-4 h-4" />}
              {trend === 'down' && <TrendingDown className="w-4 h-4" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        <div className="p-3 bg-slate-elevated rounded-lg">
          <Icon className="w-6 h-6 text-teal-electric" />
        </div>
      </div>
    </div>
  );
}

function AgingChart({ buckets }: { buckets: Array<{ bucket: string; outstanding: number; count: number }> }) {
  if (!buckets || buckets.length === 0) return null;

  const colorMap: Record<string, string> = {
    current: 'bg-green-500',
    '1-30 days': 'bg-yellow-500',
    '31-60 days': 'bg-orange-500',
    '61-90 days': 'bg-red-400',
    'over 90 days': 'bg-red-600',
  };

  const total = buckets.reduce((sum, b) => sum + (b.outstanding || 0), 0);

  return (
    <div className="bg-slate-card rounded-xl border border-slate-border p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Invoice Aging</h3>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const amount = bucket.outstanding || 0;
          const count = bucket.count || 0;
          const percent = total > 0 ? (amount / total) * 100 : 0;

          return (
            <div key={bucket.bucket}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-muted capitalize">{bucket.bucket.replace(/_/g, ' ')}</span>
                <span className="text-white font-mono">
                  {formatCurrency(amount)} ({count})
                </span>
              </div>
              <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all', colorMap[bucket.bucket] || 'bg-teal-electric')}
                  style={{ width: `${Math.max(percent, percent > 0 ? 2 : 0)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 pt-4 border-t border-slate-border">
        <div className="flex justify-between">
          <span className="text-slate-muted">Total Outstanding</span>
          <span className="text-white font-bold font-mono">{formatCurrency(total)}</span>
        </div>
      </div>
    </div>
  );
}

export default function FinanceDashboardPage() {
  const currency = 'NGN';
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError } = useFinanceDashboard(currency);
  const { data: aging, isLoading: agingLoading } = useFinanceAging({ currency });
  const { data: revenueTrend, isLoading: trendLoading } = useFinanceRevenueTrend({ currency, interval: 'month' });

  if (dashboardLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-slate-card rounded-xl border border-slate-border p-6 animate-pulse">
              <div className="h-4 bg-slate-elevated rounded w-1/2 mb-3" />
              <div className="h-8 bg-slate-elevated rounded w-3/4" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (dashboardError) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load finance dashboard</p>
        <p className="text-slate-muted text-sm mt-1">
          {dashboardError instanceof Error ? dashboardError.message : 'Unknown error'}
        </p>
      </div>
    );
  }

  const collectionRate = dashboard?.collections?.collection_rate ?? 0;
  const outstandingTotal = dashboard?.outstanding?.total ?? 0;
  const overdueTotal = dashboard?.outstanding?.overdue ?? 0;
  const invoiced30d = dashboard?.collections?.invoiced_30_days ?? 0;
  const collected30d = dashboard?.collections?.last_30_days ?? 0;

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Monthly Recurring Revenue"
          value={formatCurrency(dashboard?.revenue?.mrr || 0, dashboard?.currency || currency)}
          subtitle={`ARR: ${formatCurrency(dashboard?.revenue?.arr || 0, dashboard?.currency || currency)}`}
          icon={TrendingUp}
        />
        <StatCard
          title="Invoiced (30d)"
          value={formatCurrency(invoiced30d, dashboard?.currency || currency)}
          subtitle="Last 30 days"
          icon={FileText}
        />
        <StatCard
          title="Collected (30d)"
          value={formatCurrency(collected30d, dashboard?.currency || currency)}
          subtitle={`Collection Rate: ${(collectionRate * 100).toFixed(1)}%`}
          icon={CreditCard}
          trend={collectionRate >= 0.8 ? 'up' : 'down'}
          trendValue={collectionRate >= 0.8 ? 'Healthy' : 'Below Target'}
        />
        <StatCard
          title="Outstanding"
          value={formatCurrency(outstandingTotal, dashboard?.currency || currency)}
          subtitle={`Overdue: ${formatCurrency(overdueTotal, dashboard?.currency || currency)}`}
          icon={Clock}
        />
      </div>

      {/* DSO and Collection Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Days Sales Outstanding (DSO)</h3>
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <p className="text-5xl font-bold text-teal-electric">{dashboard?.metrics?.dso?.toFixed(0) || '-'}</p>
              <p className="text-slate-muted mt-2">days</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center justify-center gap-4 text-sm">
              {(dashboard?.metrics?.dso || 0) <= 30 ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <span className="text-green-400">Excellent - Below 30 days</span>
                </>
              ) : (dashboard?.metrics?.dso || 0) <= 45 ? (
                <>
                  <CheckCircle className="w-5 h-5 text-yellow-400" />
                  <span className="text-yellow-400">Good - Monitor closely</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <span className="text-red-400">High - Action needed</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Aging Chart */}
        {agingLoading ? (
          <div className="bg-slate-card rounded-xl border border-slate-border p-6 animate-pulse">
            <div className="h-6 bg-slate-elevated rounded w-1/3 mb-4" />
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i}>
                  <div className="h-4 bg-slate-elevated rounded w-full mb-2" />
                  <div className="h-2 bg-slate-elevated rounded" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <AgingChart buckets={aging?.buckets || []} />
        )}
      </div>

      {/* Revenue Trend */}
      {trendLoading ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6 animate-pulse">
          <div className="h-6 bg-slate-elevated rounded w-1/4 mb-4" />
          <div className="h-48 bg-slate-elevated rounded" />
        </div>
      ) : revenueTrend && revenueTrend.length > 0 ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Revenue Trend (12 Months)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border">
                  <th className="text-left py-3 px-2 text-slate-muted font-medium">Period</th>
                  <th className="text-right py-3 px-2 text-slate-muted font-medium">Revenue</th>
                  <th className="text-right py-3 px-2 text-slate-muted font-medium">Payments</th>
                </tr>
              </thead>
              <tbody>
                {revenueTrend.slice(-6).map((item, i) => (
                  <tr key={i} className="border-b border-slate-border/50 hover:bg-slate-elevated/30">
                    <td className="py-3 px-2 text-white">{item.period}</td>
                    <td className="py-3 px-2 text-right font-mono text-white">{formatCurrency(item.revenue, dashboard?.currency || currency)}</td>
                    <td className="py-3 px-2 text-right font-mono text-teal-electric">{item.payment_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Period Info */}
      {dashboard?.period && (
        <p className="text-xs text-slate-muted text-center">
          Data period: {dashboard.period.start} to {dashboard.period.end}
        </p>
      )}
    </div>
  );
}
