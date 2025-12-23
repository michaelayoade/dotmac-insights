'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Receipt } from 'lucide-react';
import { useFinanceCreditNoteMutations, useFinanceCustomers } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

export default function CreditNoteCreatePage() {
  const router = useRouter();
  const currency = 'NGN';
  const { createCreditNote } = useFinanceCreditNoteMutations();
  const { data: customersData } = useFinanceCustomers({ limit: 100, offset: 0 });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [customerId, setCustomerId] = useState<string>('');
  const [invoiceId, setInvoiceId] = useState<string>('');
  const [creditNumber, setCreditNumber] = useState<string>('');
  const [amount, setAmount] = useState<number>(0);
  const [status, setStatus] = useState<string>('draft');
  const [issueDate, setIssueDate] = useState<string>('');
  const [appliedDate, setAppliedDate] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const customers = (customersData as any)?.items || (customersData as any)?.customers || [];

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!customerId) errs.customerId = 'Customer is required';
    if (!amount || amount <= 0) errs.amount = 'Amount must be greater than zero';
    if (!issueDate) errs.issueDate = 'Issue date is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        customer_id: Number(customerId),
        invoice_id: invoiceId ? Number(invoiceId) : null,
        credit_number: creditNumber || null,
        amount,
        currency,
        status,
        issue_date: issueDate || null,
        applied_date: appliedDate || null,
        description: description || null,
      };
      const created = await createCreditNote(payload);
      router.push(`/sales/credit-notes/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create credit note');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/credit-notes"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to credit notes
          </Link>
          <h1 className="text-xl font-semibold text-foreground">New Credit Note</h1>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Receipt className="w-4 h-4 text-teal-electric" />
            Credit Note Details
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Customer</label>
              <select
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.customerId && 'border-red-500/60'
                )}
              >
                <option value="">Select customer</option>
                {customers.map((c: any) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.customer_name || `Customer ${c.id}`} {c.id ? `(#${c.id})` : ''}
                  </option>
                ))}
              </select>
              {fieldErrors.customerId && <p className="text-xs text-red-400">{fieldErrors.customerId}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Invoice ID (optional)</label>
              <input
                type="number"
                value={invoiceId}
                onChange={(e) => setInvoiceId(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Amount</label>
              <input
                type="number"
                min={0}
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.amount && 'border-red-500/60'
                )}
              />
              {fieldErrors.amount && <p className="text-xs text-red-400">{fieldErrors.amount}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="draft">Draft</option>
                <option value="issued">Issued</option>
                <option value="applied">Applied</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Issue Date</label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.issueDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.issueDate && <p className="text-xs text-red-400">{fieldErrors.issueDate}</p>}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Applied Date (optional)</label>
              <input
                type="date"
                value={appliedDate}
                onChange={(e) => setAppliedDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Credit #</label>
              <input
                type="text"
                value={creditNumber}
                onChange={(e) => setCreditNumber(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Optional"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="Optional notes"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 rounded-md border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-md bg-teal-electric text-slate-deep font-semibold hover:bg-teal-glow disabled:opacity-60"
          >
            {submitting ? 'Saving...' : 'Save Credit Note'}
          </Button>
        </div>
      </form>
    </div>
  );
}
