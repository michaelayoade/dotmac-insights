'use client';

import { useCustomerHealthInsights } from '@/hooks/useApi';
import {
  InsightCard,
  InsightBadge,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function HealthPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const { data, isLoading, error, mutate } = useCustomerHealthInsights();

  if (authLoading || isLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  const pb = data?.payment_behavior;
  const si = data?.support_intensity;
  const ci = data?.churn_indicators;
  const totalActive = data?.total_active_customers || 0;

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load customer health data"
          error={error}
          onRetry={() => mutate()}
        />
      )}
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Active Customers</div>
          <div className="text-2xl font-bold text-white">{totalActive}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">On-time Rate</div>
          <div className="text-2xl font-bold text-teal-electric">
            {pb ? pb.payment_timing.on_time_rate.toFixed(1) : '0.0'}%
          </div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Overdue Rate</div>
          <div className="text-2xl font-bold text-coral-alert">
            {pb ? pb.overdue_rate.toFixed(1) : '0.0'}%
          </div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">At Risk (Churn)</div>
          <div className="text-2xl font-bold text-coral-alert">{ci?.at_risk_total || 0}</div>
        </div>
      </div>

      {/* Payment Behavior */}
      <InsightCard title="Payment Behavior">
        {!pb ? (
          <EmptyState message="No payment behavior data yet" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="text-sm text-slate-muted">Customers with overdue invoices</p>
              <div className="text-2xl font-mono text-coral-alert">{pb.customers_with_overdue}</div>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-slate-muted">Payment timing</p>
              <div className="flex flex-wrap gap-2">
                <InsightBadge color="green">Early: {pb.payment_timing.early}</InsightBadge>
                <InsightBadge color="blue">On Time: {pb.payment_timing.on_time}</InsightBadge>
                <InsightBadge color="red">Late: {pb.payment_timing.late}</InsightBadge>
              </div>
              <p className="text-xs text-slate-muted">
                On-time rate: {pb.payment_timing.on_time_rate.toFixed(1)}%
              </p>
            </div>
          </div>
        )}
      </InsightCard>

      {/* Support Intensity */}
      <InsightCard title="Support Intensity">
        {!si ? (
          <EmptyState message="No support data yet" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-slate-muted">Customers with tickets (30d)</p>
              <p className="text-2xl font-mono text-white">{si.customers_with_tickets_30d}</p>
            </div>
            <div>
              <p className="text-sm text-slate-muted">High support customers</p>
              <p className="text-2xl font-mono text-amber-warn">{si.high_support_customers}</p>
            </div>
            <div>
              <p className="text-sm text-slate-muted">High support rate</p>
              <p className="text-2xl font-mono text-teal-electric">{si.high_support_rate.toFixed(1)}%</p>
            </div>
          </div>
        )}
      </InsightCard>

      {/* Churn Indicators */}
      <InsightCard title="Churn Indicators">
        {!ci ? (
          <EmptyState message="No churn indicator data yet" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-slate-muted">Recently cancelled (30d)</p>
              <p className="text-2xl font-mono text-coral-alert">{ci.recently_cancelled_30d}</p>
            </div>
            <div>
              <p className="text-sm text-slate-muted">Currently suspended</p>
              <p className="text-2xl font-mono text-amber-warn">{ci.currently_suspended}</p>
            </div>
            <div>
              <p className="text-sm text-slate-muted">Total at risk</p>
              <p className="text-2xl font-mono text-coral-alert">{ci.at_risk_total}</p>
            </div>
          </div>
        )}
      </InsightCard>
    </div>
  );
}
