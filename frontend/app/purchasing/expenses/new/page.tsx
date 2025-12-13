'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, ClipboardList, Receipt } from 'lucide-react';
import { usePurchasingExpenseMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function PurchasingExpenseCreatePage() {
  const router = useRouter();
  const { createExpense } = usePurchasingExpenseMutations();

  const [employeeId, setEmployeeId] = useState('');
  const [purpose, setPurpose] = useState('');
  const [postingDate, setPostingDate] = useState('');
  const [claimed, setClaimed] = useState('');
  const [sanctioned, setSanctioned] = useState('');
  const [reimbursed, setReimbursed] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [status, setStatus] = useState('pending');
  const [company, setCompany] = useState('');
  const [costCenter, setCostCenter] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!purpose.trim()) errs.purpose = 'Purpose is required';
    if (!postingDate) errs.postingDate = 'Posting date is required';
    if (!claimed || Number(claimed) <= 0) errs.claimed = 'Claimed amount must be greater than 0';
    if (!currency.trim()) errs.currency = 'Currency is required';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      await createExpense({
        employee_id: employeeId ? Number(employeeId) : undefined,
        purpose: purpose || null,
        posting_date: postingDate || null,
        total_claimed_amount: claimed ? Number(claimed) : null,
        total_sanctioned_amount: sanctioned ? Number(sanctioned) : null,
        total_amount_reimbursed: reimbursed ? Number(reimbursed) : null,
        currency: currency || null,
        status: status || null,
        company: company || null,
        cost_center: costCenter || null,
      });
      router.push('/purchasing/expenses');
    } catch (err: any) {
      setError(err?.message || 'Failed to create expense');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/expenses"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to expenses
          </Link>
          <h1 className="text-xl font-semibold text-white">New Expense</h1>
        </div>
        <span className="text-xs text-slate-muted uppercase tracking-[0.12em]">Purchasing</span>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <Receipt className="w-4 h-4 text-teal-electric" />
              Expense Details
            </h3>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Purpose</label>
              <input
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.purpose && 'border-red-500/60'
                )}
                placeholder="Describe the expense"
              />
              {fieldErrors.purpose && <p className="text-xs text-red-400">{fieldErrors.purpose}</p>}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Posting Date</label>
                <input
                  type="date"
                  value={postingDate}
                  onChange={(e) => setPostingDate(e.target.value)}
                  className={cn(
                    'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                    fieldErrors.postingDate && 'border-red-500/60'
                  )}
                />
                {fieldErrors.postingDate && <p className="text-xs text-red-400">{fieldErrors.postingDate}</p>}
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Employee ID</label>
                <input
                  type="number"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="draft">Draft</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="paid">Paid</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Currency</label>
                <input
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  className={cn(
                    'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                    fieldErrors.currency && 'border-red-500/60'
                  )}
                />
                {fieldErrors.currency && <p className="text-xs text-red-400">{fieldErrors.currency}</p>}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Company</label>
                <input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Cost Center</label>
                <input
                  value={costCenter}
                  onChange={(e) => setCostCenter(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="e.g. Sales"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-teal-electric" />
              Amounts
            </h3>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Total Claimed</label>
              <input
                type="number"
                value={claimed}
                onChange={(e) => setClaimed(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.claimed && 'border-red-500/60'
                )}
                placeholder="0"
              />
              {fieldErrors.claimed && <p className="text-xs text-red-400">{fieldErrors.claimed}</p>}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Sanctioned Amount</label>
                <input
                  type="number"
                  value={sanctioned}
                  onChange={(e) => setSanctioned(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="0"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Amount Reimbursed</label>
                <input
                  type="number"
                  value={reimbursed}
                  onChange={(e) => setReimbursed(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="0"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            {submitting ? 'Saving...' : 'Create Expense'}
          </button>
        </div>
      </form>
    </div>
  );
}
