'use client';

import { useFinanceForecasts, useFinancePaymentBehavior } from '@/hooks/useApi';

function formatCurrency(value: number, currency = 'NGN') {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
}

export default function SalesInsightsPage() {
  const currency = 'NGN';
  const { data: behavior, isLoading: behaviorLoading } = useFinancePaymentBehavior({ currency });
  const { data: forecasts, isLoading: forecastsLoading } = useFinanceForecasts(currency);

  return (
    <div className="space-y-6">
      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Payment Behavior</h2>
        {behaviorLoading ? (
          <div className="h-24 bg-slate-elevated rounded animate-pulse" />
        ) : behavior ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Avg Days to Pay</p>
              <p className="text-2xl font-bold text-white mt-1">{(behavior.avg_days_to_pay ?? 0).toFixed(1)}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Late Payments</p>
              <p className="text-2xl font-bold text-amber-warn mt-1">{(behavior.late_payments_percent ?? 0).toFixed(1)}%</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">On-Time Payments</p>
              <p className="text-2xl font-bold text-teal-electric mt-1">{(behavior.on_time_percent ?? 0).toFixed(1)}%</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-muted text-sm">No behavior data.</p>
        )}

        {(behavior?.best_payers?.length || behavior?.worst_payers?.length) && (
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-elevated border border-slate-border rounded-lg p-4">
              <p className="text-sm text-slate-muted mb-2">Best Payers</p>
              <div className="space-y-2">
                {(behavior?.best_payers || []).map((p: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <span className="text-white">{p.customer_name || 'Customer'}</span>
                    <span className="font-mono text-teal-electric">{(p.avg_days_to_pay ?? 0).toFixed(1)} days</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-slate-elevated border border-slate-border rounded-lg p-4">
              <p className="text-sm text-slate-muted mb-2">Needs Attention</p>
              <div className="space-y-2">
                {(behavior?.worst_payers || []).map((p: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <span className="text-white">{p.customer_name || 'Customer'}</span>
                    <span className="font-mono text-amber-warn">{(p.avg_days_to_pay ?? 0).toFixed(1)} days</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Forecasts</h2>
        {forecastsLoading ? (
          <div className="h-24 bg-slate-elevated rounded animate-pulse" />
        ) : forecasts ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Baseline MRR</p>
              <p className="text-2xl font-bold text-white mt-1">{formatCurrency(forecasts.baseline_mrr, currency)}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Next Period</p>
              <p className="text-2xl font-bold text-teal-electric mt-1">
                {forecasts.projection?.[0] ? `${forecasts.projection[0].period}` : 'Upcoming'}
              </p>
              {forecasts.projection?.[0] && (
                <p className="text-slate-muted text-xs mt-1">
                  {formatCurrency(forecasts.projection[0].mrr, currency)}
                </p>
              )}
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Projection Horizon</p>
              <p className="text-2xl font-bold text-white mt-1">{forecasts.projection?.length || 0} periods</p>
              <p className="text-slate-muted text-xs mt-1">Latest: {forecasts.projection?.[forecasts.projection.length - 1]?.period || '-'}</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-muted text-sm">No forecast data.</p>
        )}

        {forecasts?.assumptions && (
          <p className="mt-4 text-slate-muted text-sm">Assumptions available in API response.</p>
        )}
      </div>
    </div>
  );
}
