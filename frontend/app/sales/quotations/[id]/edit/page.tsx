'use client';

import { useMemo, useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, StickyNote } from 'lucide-react';
import { useFinanceCustomers, useFinanceQuotationDetail, useFinanceQuotationMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function QuotationEditPage() {
  const params = useParams();
  const router = useRouter();
  const id = useMemo(() => Number(params?.id), [params?.id]);
  const currency = 'NGN';
  const { data, isLoading, error } = useFinanceQuotationDetail(Number.isFinite(id) ? id : null, currency);
  const { updateQuotation } = useFinanceQuotationMutations();
  const { data: customersData } = useFinanceCustomers({ limit: 100, offset: 0 });

  const [customerId, setCustomerId] = useState<string>('');
  const [quotationNumber, setQuotationNumber] = useState<string>('');
  const [status, setStatus] = useState<string>('draft');
  const [quotationDate, setQuotationDate] = useState<string>('');
  const [validTill, setValidTill] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [totalAmount, setTotalAmount] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const customers = (customersData as any)?.items || (customersData as any)?.customers || [];

  useEffect(() => {
    if (data) {
      setCustomerId(data.customer_id ? String(data.customer_id) : '');
      setQuotationNumber(data.quotation_number || '');
      setStatus(data.status || 'draft');
      setQuotationDate((data as any).transaction_date || data.quotation_date || '');
      setValidTill((data as any).valid_till || '');
      setDescription((data as any).description || '');
      setTotalAmount(data.total_amount || 0);
    }
  }, [data]);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!customerId) errs.customerId = 'Customer is required';
    if (!quotationDate) errs.quotationDate = 'Quotation date is required';
    if (!totalAmount || totalAmount <= 0) errs.totalAmount = 'Total must be greater than zero';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!Number.isFinite(id)) return;
    if (!validate()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        quotation_to: 'Customer',
        party_name: data.customer_name || null,
        customer_name: data.customer_name || null,
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
        sales_partner: data.sales_partner || null,
        territory: data.territory || null,
        source: data.source || 'local',
        campaign: data.campaign || null,
        order_lost_reason: data.order_lost_reason || null,
        quotation_number: quotationNumber || null,
        description: description || null,
      };
      const updated = await updateQuotation(id, payload);
      router.push(`/sales/quotations/${updated.id}/edit`);
    } catch (err: any) {
      setSubmitError(err?.message || 'Failed to update quotation');
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="h-6 w-24 bg-slate-elevated rounded mb-4 animate-pulse" />
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load quotation</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/quotations"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to quotations
          </Link>
          <h1 className="text-xl font-semibold text-white">Edit Quotation</h1>
        </div>
      </div>

      {submitError && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{submitError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
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
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
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
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
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
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
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
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Optional notes"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 rounded-md border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-md bg-teal-electric text-slate-deep font-semibold hover:bg-teal-glow disabled:opacity-60"
          >
            {submitting ? 'Saving...' : 'Update Quotation'}
          </button>
        </div>
      </form>

      {(data as any)?.items?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <StickyNote className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Quotation Items</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Item</th>
                  <th className="text-left px-2 py-2">Description</th>
                  <th className="text-right px-2 py-2">Qty</th>
                  <th className="text-right px-2 py-2">Rate</th>
                  <th className="text-right px-2 py-2">Amount</th>
                </tr>
              </thead>
              <tbody>
                {(data as any).items.map((item: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-white font-mono">{item.item_code || '-'}</td>
                    <td className="px-2 py-2 text-slate-200">{item.item_name || item.description || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.qty ?? item.quantity ?? 0}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.rate ?? item.unit_price ?? 0}</td>
                    <td className="px-2 py-2 text-right text-white font-mono">{item.amount ?? item.net_amount ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
