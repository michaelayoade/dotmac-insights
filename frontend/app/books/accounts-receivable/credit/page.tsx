'use client';

import { useState } from 'react';
import { useCustomerCreditStatus, useCustomerCreditMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { AlertTriangle, ShieldCheck, Lock, Unlock, CreditCard } from 'lucide-react';
import { Button } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

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
          <h1 className="text-2xl font-bold text-foreground">AR Credit Management</h1>
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
            className="input-field"
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
              className="input-field"
            />
            <Button onClick={onUpdateLimit} module="books">
              Update Limit
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1 min-w-[220px]">
          <label className="text-slate-muted text-xs">Hold Reason</label>
          <input
            value={holdReason}
            onChange={(e) => setHoldReason(e.target.value)}
            placeholder="Reason for hold (optional)"
            className="input-field"
          />
          <div className="flex gap-2">
            <Button onClick={() => onToggleHold(true)} variant="secondary" icon={Lock}>
              Place Hold
            </Button>
            <Button onClick={() => onToggleHold(false)} module="books" icon={Unlock}>
              Release
            </Button>
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
            value={formatAccountingCurrency(data.credit_limit)}
            subtitle={`Used: ${formatAccountingCurrency(data.credit_used)}`}
            icon={ShieldCheck}
            colorClass="text-teal-electric"
          />
          <StatCard
            title="Available"
            value={formatAccountingCurrency((data.credit_limit || 0) - (data.credit_used || 0))}
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
