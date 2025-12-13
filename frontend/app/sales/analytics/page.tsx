'use client';

import { useMemo } from 'react';
import { useFinanceAging, useFinanceCollections, useFinanceRevenueBySegment, useFinanceRevenueTrend } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatCurrency(value: number, currency = 'NGN') {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
}

export default function SalesAnalyticsPage() {
  const currency = 'NGN';
  const { data: trend, isLoading: trendLoading } = useFinanceRevenueTrend({ currency, interval: 'month' });
  const { data: collections, isLoading: collectionsLoading } = useFinanceCollections({ currency });
  const { data: aging, isLoading: agingLoading } = useFinanceAging({ currency });
  const { data: byCurrency, isLoading: currencyLoading } = useFinanceRevenueBySegment();

  const latestTrend = useMemo(() => (trend && trend.length > 0 ? trend.slice(-6) : []), [trend]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Revenue Trend</h2>
          {trendLoading ? (
            <div className="h-32 bg-slate-elevated rounded animate-pulse" />
          ) : latestTrend.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-border">
                    <th className="text-left py-2 text-slate-muted font-medium">Period</th>
                    <th className="text-right py-2 text-slate-muted font-medium">Revenue</th>
                    <th className="text-right py-2 text-slate-muted font-medium">Payments</th>
                  </tr>
                </thead>
                <tbody>
                  {latestTrend.map((row, idx) => (
                    <tr key={idx} className="border-b border-slate-border/50">
                      <td className="py-2 text-white">{row.period}</td>
                      <td className="py-2 text-right font-mono text-white">{formatCurrency(row.revenue, currency)}</td>
                      <td className="py-2 text-right font-mono text-teal-electric">{(row.payment_count ?? 0).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No revenue data.</p>
          )}
        </div>

        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Collections</h2>
          {collectionsLoading ? (
            <div className="h-32 bg-slate-elevated rounded animate-pulse" />
          ) : collections ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm text-slate-muted mb-2">By Method</h3>
                <div className="space-y-2">
                  {collections.by_method.map((m) => (
                    <div key={m.method} className="flex items-center justify-between text-sm">
                      <span className="text-white capitalize">{m.method || 'Unknown'}</span>
                      <span className="font-mono text-teal-electric">{formatCurrency(m.amount, currency)} ({m.count})</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm text-slate-muted mb-2">Payment Timing</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-white">Early</span><span className="font-mono text-teal-electric">{collections.timing?.early ?? 0}</span></div>
                  <div className="flex justify-between"><span className="text-white">On time</span><span className="font-mono text-teal-electric">{collections.timing?.on_time ?? 0}</span></div>
                  <div className="flex justify-between"><span className="text-white">Late</span><span className="font-mono text-teal-electric">{collections.timing?.late ?? 0}</span></div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No collection data.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Aging</h2>
          {agingLoading ? (
            <div className="h-40 bg-slate-elevated rounded animate-pulse" />
          ) : aging ? (
            <div className="space-y-3">
              {[
                { key: 'current', label: 'Current', ...aging.buckets.current },
                { key: '1_30', label: '1-30 days', ...aging.buckets['1_30'] },
                { key: '31_60', label: '31-60 days', ...aging.buckets['31_60'] },
                { key: '61_90', label: '61-90 days', ...aging.buckets['61_90'] },
                { key: 'over_90', label: 'Over 90 days', ...aging.buckets.over_90 },
              ].map((b) => (
                <div key={b.key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-muted capitalize">{b.label}</span>
                    <span className="font-mono text-white">{formatCurrency(b.total, currency)} ({b.count})</span>
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                    <div
                      className={cn('h-full bg-teal-electric rounded-full', (b.total || 0) > 0 ? 'opacity-100' : 'opacity-30')}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No aging data.</p>
          )}
        </div>

        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h2 className="text-lg font-semibold text-white mb-4">By Currency</h2>
          {currencyLoading ? (
            <div className="h-32 bg-slate-elevated rounded animate-pulse" />
          ) : byCurrency?.by_currency?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-border">
                    <th className="text-left py-2 text-slate-muted font-medium">Currency</th>
                    <th className="text-right py-2 text-slate-muted font-medium">MRR</th>
                    <th className="text-right py-2 text-slate-muted font-medium">ARR</th>
                    <th className="text-right py-2 text-slate-muted font-medium">Outstanding</th>
                  </tr>
                </thead>
                <tbody>
                  {byCurrency.by_currency.map((row) => (
                    <tr key={row.currency} className="border-b border-slate-border/50">
                      <td className="py-2 text-white">{row.currency}</td>
                      <td className="py-2 text-right font-mono text-white">{formatCurrency(row.mrr, row.currency)}</td>
                      <td className="py-2 text-right font-mono text-white">{formatCurrency(row.arr, row.currency)}</td>
                      <td className="py-2 text-right font-mono text-teal-electric">{formatCurrency(row.outstanding, row.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No currency breakdown.</p>
          )}
        </div>
      </div>
    </div>
  );
}
