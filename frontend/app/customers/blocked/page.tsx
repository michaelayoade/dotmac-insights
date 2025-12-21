'use client';

import { useMemo, useState } from 'react';
import { useBlockedCustomers } from '@/hooks/useApi';
import { BlockedCustomer } from '@/lib/api';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  LoadingState,
  ErrorDisplay,
  EmptyState,
  SummaryCard,
} from '@/components/insights/shared';

export default function BlockedCustomersPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const [months, setMonths] = useState(3);
  const [minMrr, setMinMrr] = useState<number | undefined>(undefined);
  const [sortBy, setSortBy] = useState<'mrr' | 'days_blocked' | 'tenure' | undefined>(undefined);
  const maxDays = useMemo(() => months * 30, [months]);

  const { data, isLoading, error, mutate } = useBlockedCustomers({
    min_days_blocked: 0,
    max_days_blocked: maxDays,
    min_mrr: minMrr,
    sort_by: sortBy,
    limit: 200,
  });

  if (authLoading || isLoading) {
    return <LoadingState />;
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  const customers = (data as any)?.data || data?.items || [];
  const totalOutstanding = customers.reduce(
    (sum: number, c: any) => sum + ((c as any).outstanding_balance || (c.billing_health?.overdue_amount ?? 0) || 0),
    0
  );

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load blocked customers"
          error={error}
          onRetry={() => mutate()}
        />
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Blocked"
          value={customers.length.toString()}
          subtitle={`Last ${months} months`}
          gradient="from-red-500 to-red-600"
        />
        <SummaryCard
          title="Outstanding Balance"
          value={`₦${totalOutstanding.toLocaleString()}`}
          subtitle="Across blocked accounts"
          gradient="from-orange-500 to-orange-600"
        />
      </div>

      {/* Filter */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 items-end">
        <div className="flex flex-col gap-2">
          <label className="text-sm text-slate-muted">Time Period</label>
          <select
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric"
          >
            <option value={1}>Last 1 month</option>
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm text-slate-muted">Min MRR</label>
          <input
            type="number"
            placeholder="e.g. 50000"
            value={minMrr ?? ''}
            onChange={(e) => setMinMrr(e.target.value ? Number(e.target.value) : undefined)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm text-slate-muted">Sort By</label>
          <select
            value={sortBy || ''}
            onChange={(e) => setSortBy(e.target.value ? (e.target.value as 'mrr' | 'days_blocked' | 'tenure') : undefined)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric"
          >
            <option value="">None</option>
            <option value="mrr">MRR</option>
            <option value="days_blocked">Days Blocked</option>
            <option value="tenure">Tenure</option>
          </select>
        </div>
      </div>

      {/* Blocked Customers Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-border">
          <h3 className="text-lg font-semibold text-foreground">Blocked Customers</h3>
        </div>
        {customers.length === 0 ? (
          <div className="p-6">
            <EmptyState message="No blocked customers found in this period." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-elevated">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Customer</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Blocked Days</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Tenure (days)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Plan</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Type</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-muted uppercase tracking-wider">MRR</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-muted uppercase tracking-wider">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {customers.map((customer: BlockedCustomer) => (
                  <tr key={customer.id} className="hover:bg-slate-elevated/50 transition-colors">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium text-foreground">{customer.name}</div>
                        <div className="text-xs text-slate-muted">
                          {customer.email || `ID: ${customer.id}`}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {customer.days_blocked?.toLocaleString() || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-foreground">
                      {customer.tenure_days?.toLocaleString() || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-foreground">
                      {customer.plan || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted capitalize">
                      {customer.customer_type || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-teal-electric font-medium">
                      ₦{(customer.mrr || 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-coral-alert font-medium">
                      ₦{((customer as any).outstanding_balance ||
                        customer.billing_health?.overdue_amount ||
                        0).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
