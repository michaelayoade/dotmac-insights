'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, StickyNote } from 'lucide-react';
import { useFinanceCustomers, useFinanceQuotationMutations } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

export default function QuotationCreatePage() {
  const router = useRouter();
  const currency = 'NGN';
  const { createQuotation } = useFinanceQuotationMutations();
  const { data: customersData } = useFinanceCustomers({ limit: 100, offset: 0 });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [customerId, setCustomerId] = useState<string>('');
  const [quotationNumber, setQuotationNumber] = useState<string>('');
  const [status, setStatus] = useState<string>('draft');
  const [quotationDate, setQuotationDate] = useState<string>('');
  const [validTill, setValidTill] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [totalAmount, setTotalAmount] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const customers = (customersData as any)?.items || (customersData as any)?.customers || [];

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!customerId) errs.customerId = 'Customer is required';
    if (!quotationDate) errs.quotationDate = 'Quotation date is required';
    if (!totalAmount || totalAmount <= 0) errs.totalAmount = 'Total must be greater than zero';
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
        quotation_to: 'Customer',
        party_name: customerId ? undefined : null,
        customer_name: customerId ? undefined : null,
        order_type: 'Sales',
        company: 'Dotmac',
        currency,
        transaction_date: quotationDate || null,
        valid_till: validTill || null,
        total_qty: 1,
        total: totalAmount,
        net_total: totalAmount,
        grand_total: totalAmount,
        rounded_total: totalAmount,
        total_taxes_and_charges: 0,
        status,
        sales_partner: null,
        territory: null,
        source: 'local',
        campaign: null,
        order_lost_reason: null,
        quotation_number: quotationNumber || null,
        description: description || null,
      };
      const created = await createQuotation(payload);
      router.push(`/sales/quotations/${created.id}/edit`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create quotation');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/quotations"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to quotations
          </Link>
          <h1 className="text-xl font-semibold text-foreground">New Quotation</h1>
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
            <StickyNote className="w-4 h-4 text-teal-electric" />
            Quotation Details
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
              <label className="text-sm text-slate-muted">Quote #</label>
              <input
                type="text"
                value={quotationNumber}
                onChange={(e) => setQuotationNumber(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Optional"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="draft">Draft</option>
                <option value="open">Open</option>
                <option value="replied">Replied</option>
                <option value="ordered">Ordered</option>
                <option value="lost">Lost</option>
                <option value="cancelled">Cancelled</option>
                <option value="expired">Expired</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Quotation Date</label>
              <input
                type="date"
                value={quotationDate}
                onChange={(e) => setQuotationDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.quotationDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.quotationDate && <p className="text-xs text-red-400">{fieldErrors.quotationDate}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Valid Till</label>
              <input
                type="date"
                value={validTill}
                onChange={(e) => setValidTill(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Total Amount</label>
              <input
                type="number"
                min={0}
                value={totalAmount}
                onChange={(e) => setTotalAmount(Number(e.target.value))}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.totalAmount && 'border-red-500/60'
                )}
              />
              {fieldErrors.totalAmount && <p className="text-xs text-red-400">{fieldErrors.totalAmount}</p>}
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
            {submitting ? 'Saving...' : 'Save Quotation'}
          </Button>
        </div>
      </form>
    </div>
  );
}
