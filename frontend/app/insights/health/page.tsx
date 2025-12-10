'use client';

import { useState } from 'react';
import { useCustomerHealth } from '@/hooks/useApi';
import { CustomerHealthRecord } from '@/lib/api';
import {
  InsightCard,
  ProgressBar,
  InsightBadge,
  LoadingState,
  ErrorDisplay,
  EmptyState,
} from '@/components/insights/shared';

export default function HealthPage() {
  const [riskFilter, setRiskFilter] = useState<string | undefined>(undefined);
  const { data, isLoading, error, mutate } = useCustomerHealth(100, riskFilter);

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load customer health data"
        error={error}
        onRetry={() => mutate()}
      />
    );
  }

  const getRiskColor = (level: string): string => {
    switch (level.toLowerCase()) {
      case 'critical': return 'red';
      case 'high': return 'yellow';
      case 'medium': return 'blue';
      case 'low': return 'green';
      default: return 'gray';
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Total Analyzed</div>
          <div className="text-2xl font-bold text-white">{data?.summary.total_analyzed || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Avg Health Score</div>
          <div className="text-2xl font-bold text-teal-electric">{data?.summary.avg_health_score.toFixed(0) || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">At Risk</div>
          <div className="text-2xl font-bold text-coral-alert">{data?.summary.at_risk_count || 0}</div>
        </div>
        <div className="bg-slate-card rounded-lg border border-slate-border p-4">
          <div className="text-sm text-slate-muted">Health Distribution</div>
          <div className="flex gap-1 mt-1 flex-wrap">
            {Object.entries(data?.summary.health_distribution || {}).map(([level, count]) => (
              <InsightBadge key={level} color={getRiskColor(level)}>
                {level}: {count as number}
              </InsightBadge>
            ))}
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setRiskFilter(undefined)}
          className={`px-3 py-1.5 rounded text-sm ${!riskFilter ? 'bg-teal-electric text-slate-deep' : 'bg-slate-elevated text-slate-muted hover:text-white'}`}
        >
          All
        </button>
        {['critical', 'high', 'medium', 'low'].map((level) => (
          <button
            key={level}
            onClick={() => setRiskFilter(level)}
            className={`px-3 py-1.5 rounded text-sm capitalize ${riskFilter === level ? 'bg-teal-electric text-slate-deep' : 'bg-slate-elevated text-slate-muted hover:text-white'}`}
          >
            {level}
          </button>
        ))}
      </div>

      {/* Customer List */}
      <InsightCard title="Customer Health Details">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-border">
            <thead>
              <tr className="bg-slate-elevated">
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Customer</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Health</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Risk Level</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Outstanding</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-slate-muted uppercase">Risk Factors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {data?.customers.slice(0, 50).map((customer: CustomerHealthRecord) => (
                <tr key={customer.customer_id} className="hover:bg-slate-elevated/50">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-white">{customer.customer_name}</div>
                    <div className="text-xs text-slate-muted">{customer.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <InsightBadge color={customer.status === 'active' ? 'green' : 'gray'}>
                      {customer.status}
                    </InsightBadge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16">
                        <ProgressBar value={customer.health_score} max={100} color={customer.health_score > 70 ? 'green' : customer.health_score > 40 ? 'yellow' : 'red'} />
                      </div>
                      <span className="text-sm font-medium text-white">{customer.health_score}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <InsightBadge color={getRiskColor(customer.risk_level)}>
                      {customer.risk_level}
                    </InsightBadge>
                  </td>
                  <td className="px-4 py-3 text-sm text-white">
                    {customer.payment_health.outstanding_amount.toLocaleString(undefined, { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {customer.risk_factors.slice(0, 2).map((factor, i) => (
                        <InsightBadge key={i} color="red">{factor}</InsightBadge>
                      ))}
                      {customer.risk_factors.length > 2 && (
                        <InsightBadge color="gray">+{customer.risk_factors.length - 2}</InsightBadge>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!data?.customers || data.customers.length === 0) && (
            <EmptyState
              title="No Customer Data"
              message="Customer health data is not yet available. Sync your customer data to see health scores."
            />
          )}
        </div>
      </InsightCard>

      {/* Recommendations */}
      {data?.recommendations && data.recommendations.length > 0 && (
        <InsightCard title="Recommendations">
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-muted">
                <span className="text-teal-electric mt-0.5">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </InsightCard>
      )}
    </div>
  );
}
