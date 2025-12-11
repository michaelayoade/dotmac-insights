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

export default function FinanceInsightsPage() {
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
              <p className="text-slate-muted">Customers With Payments</p>
              <p className="text-2xl font-bold text-white mt-1">{behavior.summary.customers_with_payments.toLocaleString()}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Customers With Overdue</p>
              <p className="text-2xl font-bold text-amber-warn mt-1">{behavior.summary.customers_with_overdue.toLocaleString()}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Avg Late Delay (days)</p>
              <p className="text-2xl font-bold text-teal-electric mt-1">{behavior.summary.avg_late_payment_delay_days.toFixed(1)}</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-muted text-sm">No behavior data.</p>
        )}

        {behavior?.recommendations?.length ? (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-white mb-2">Recommendations</h3>
            <div className="space-y-2">
              {behavior.recommendations.map((rec, idx) => (
                <div key={idx} className="p-3 bg-slate-elevated rounded border border-slate-border text-sm">
                  <div className="flex items-center gap-2 text-teal-electric">
                    <span className="text-xs uppercase tracking-wide">{rec.priority}</span>
                    <span className="text-white font-medium">{rec.issue}</span>
                  </div>
                  <p className="text-slate-muted mt-1">{rec.action}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Forecasts</h2>
        {forecastsLoading ? (
          <div className="h-24 bg-slate-elevated rounded animate-pulse" />
        ) : forecasts ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Current MRR</p>
              <p className="text-2xl font-bold text-white mt-1">{formatCurrency(forecasts.current.mrr, forecasts.currency)}</p>
              <p className="text-slate-muted text-xs mt-1">ARR: {formatCurrency(forecasts.current.arr, forecasts.currency)}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">New Subs (30d)</p>
              <p className="text-2xl font-bold text-teal-electric mt-1">{forecasts.activity_30d.new_subscriptions}</p>
            </div>
            <div className="p-4 bg-slate-elevated rounded-lg border border-slate-border">
              <p className="text-slate-muted">Quarter Projection</p>
              <p className="text-2xl font-bold text-white mt-1">{formatCurrency(forecasts.projections.quarter_total, forecasts.currency)}</p>
              <p className="text-slate-muted text-xs mt-1">1M/2M/3M: {[
                forecasts.projections.month_1,
                forecasts.projections.month_2,
                forecasts.projections.month_3,
              ].map((v) => formatCurrency(v, forecasts.currency)).join(' / ')}</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-muted text-sm">No forecast data.</p>
        )}

        {forecasts?.notes && (
          <p className="mt-4 text-slate-muted text-sm">{forecasts.notes}</p>
        )}
      </div>
    </div>
  );
}
