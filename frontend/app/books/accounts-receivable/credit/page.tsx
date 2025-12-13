'use client';

import { useState } from 'react';
import { useCustomerCreditStatus, useCustomerCreditMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { AlertTriangle, ShieldCheck, Lock, Unlock, CreditCard } from 'lucide-react';

function formatCurrency(value: number | null | undefined, currency = 'NGN') {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', { style: 'currency', currency }).format(value);
}

export default function CreditManagementPage() {
  const [customerId, setCustomerId] = useState<string>('');
  const [newLimit, setNewLimit] = useState<string>('');
  const [holdReason, setHoldReason] = useState<string>('');
  const { data, error, mutate } = useCustomerCreditStatus(customerId ? Number(customerId) : null);
  const { updateLimit, updateHold } = useCustomerCreditMutations();

  const onUpdateLimit = async () => {
    if (!customerId) return;
    await updateLimit(Number(customerId), { credit_limit: Number(newLimit) || 0 });
    setNewLimit('');
    mutate();
  };

  const onToggleHold = async (hold: boolean) => {
    if (!customerId) return;
    await updateHold(Number(customerId), { credit_hold: hold, credit_hold_reason: hold ? holdReason : null });
    setHoldReason('');
    mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AR Credit Management</h1>
          <p className="text-slate-muted text-sm">Manage credit limits and holds for customers.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-2">
          <label className="text-slate-muted text-xs">Customer ID</label>
          <input
            type="number"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="Enter customer id"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-slate-muted text-xs">New Credit Limit</label>
          <div className="flex gap-2">
            <input
              type="number"
              value={newLimit}
              onChange={(e) => setNewLimit(e.target.value)}
              placeholder="Amount"
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
            <button
              onClick={onUpdateLimit}
              className="px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              Update Limit
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1 min-w-[220px]">
          <label className="text-slate-muted text-xs">Hold Reason</label>
          <input
            value={holdReason}
            onChange={(e) => setHoldReason(e.target.value)}
            placeholder="Reason for hold (optional)"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <div className="flex gap-2">
            <button
              onClick={() => onToggleHold(true)}
              className="px-3 py-2 rounded-lg border border-slate-border text-white text-sm hover:bg-slate-elevated"
            >
              <Lock className="w-4 h-4 inline" /> Place Hold
            </button>
            <button
              onClick={() => onToggleHold(false)}
              className="px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              <Unlock className="w-4 h-4 inline" /> Release
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-4 h-4" />
          <span>Unable to load credit status. Enter a valid customer ID.</span>
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard
            title="Credit Limit"
            value={formatCurrency(data.credit_limit)}
            subtitle={`Used: ${formatCurrency(data.credit_used)}`}
            icon={ShieldCheck}
            colorClass="text-teal-electric"
          />
          <StatCard
            title="Available"
            value={formatCurrency((data.credit_limit || 0) - (data.credit_used || 0))}
            subtitle={`Usage ${(data.usage_percent ?? 0).toFixed(1)}%`}
            icon={CreditCard}
            colorClass="text-blue-400"
          />
          <StatCard
            title="Hold Status"
            value={data.credit_hold ? 'On Hold' : 'Active'}
            subtitle={data.credit_hold_reason || '—'}
            icon={data.credit_hold ? Lock : Unlock}
            colorClass={data.credit_hold ? 'text-red-400' : 'text-green-400'}
          />
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  colorClass?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={cn('w-4 h-4', colorClass)} />
        <p className="text-slate-muted text-sm">{title}</p>
      </div>
      <p className={cn('text-xl font-semibold', colorClass)}>{value}</p>
      {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
    </div>
  );
}
