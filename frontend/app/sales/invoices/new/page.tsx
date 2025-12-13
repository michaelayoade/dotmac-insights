'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, FileText, Plus, Trash2 } from 'lucide-react';
import { useFinanceCustomers, useFinanceInvoiceMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

type LineItem = {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
};

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
}

export default function InvoiceCreatePage() {
  const router = useRouter();
  const currency = 'NGN';
  const { createInvoice } = useFinanceInvoiceMutations();
  const { data: customersData } = useFinanceCustomers({ limit: 100, offset: 0 });

  const [customerId, setCustomerId] = useState<string>('');
  const [invoiceNumber, setInvoiceNumber] = useState<string>('');
  const [invoiceDate, setInvoiceDate] = useState<string>('');
  const [dueDate, setDueDate] = useState<string>('');
  const [status, setStatus] = useState<string>('draft');
  const [description, setDescription] = useState<string>('');
  const [lineItems, setLineItems] = useState<LineItem[]>([
    { id: 'li-1', description: '', quantity: 1, unit_price: 0, tax_rate: 0 },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const totals = lineItems.reduce(
    (acc, item) => {
      const subtotal = (item.quantity || 0) * (item.unit_price || 0);
      const tax = subtotal * (item.tax_rate || 0) / 100;
      acc.subtotal += subtotal;
      acc.tax += tax;
      return acc;
    },
    { subtotal: 0, tax: 0 }
  );
  const total = totals.subtotal + totals.tax;
  const customers = (customersData as any)?.items || (customersData as any)?.customers || [];

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!customerId) errs.customerId = 'Customer is required';
    if (!invoiceDate) errs.invoiceDate = 'Invoice date is required';
    if (dueDate && invoiceDate && new Date(dueDate) < new Date(invoiceDate)) {
      errs.dueDate = 'Due date must be after invoice date';
    }
    if (!lineItems.length) errs.lineItems = 'At least one line item is required';
    lineItems.forEach((item, idx) => {
      if (!item.description) errs[`line-${idx}-description`] = 'Description required';
      if (item.quantity <= 0) errs[`line-${idx}-quantity`] = 'Quantity must be positive';
      if (item.unit_price < 0) errs[`line-${idx}-unit_price`] = 'Unit price must be positive';
    });
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = {
        invoice_number: invoiceNumber || null,
        customer_id: customerId ? Number(customerId) : null,
        description: description || null,
        amount: total,
        tax_amount: totals.tax,
        amount_paid: 0,
        currency,
        status,
        invoice_date: invoiceDate || null,
        due_date: dueDate || null,
        paid_date: null,
        category: null,
      };
      const created = await createInvoice(payload);
      router.push(`/sales/invoices/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create invoice');
    } finally {
      setSubmitting(false);
    }
  };

  const updateLine = (id: string, patch: Partial<LineItem>) => {
    setLineItems((items) => items.map((li) => (li.id === id ? { ...li, ...patch } : li)));
  };

  const removeLine = (id: string) => {
    setLineItems((items) => items.filter((li) => li.id !== id));
  };

  const addLine = () => {
    setLineItems((items) => [...items, { id: `li-${Date.now()}`, description: '', quantity: 1, unit_price: 0, tax_rate: 0 }]);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/invoices"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to invoices
          </Link>
          <h1 className="text-xl font-semibold text-white">New Invoice</h1>
        </div>
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
              <FileText className="w-4 h-4 text-teal-electric" />
              Invoice Details
            </h3>
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Invoice #</label>
                <input
                  type="text"
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Status</label>
                <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="draft">Draft</option>
                <option value="pending">Pending</option>
                <option value="partially_paid">Partially Paid</option>
                <option value="paid">Paid</option>
                <option value="overdue">Overdue</option>
                <option value="cancelled">Cancelled</option>
                <option value="refunded">Refunded</option>
              </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Invoice Date</label>
                <input
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  className={cn(
                    'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                    fieldErrors.invoiceDate && 'border-red-500/60'
                  )}
                />
                {fieldErrors.invoiceDate && <p className="text-xs text-red-400">{fieldErrors.invoiceDate}</p>}
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Due Date</label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className={cn(
                    'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                    fieldErrors.dueDate && 'border-red-500/60'
                  )}
                />
                {fieldErrors.dueDate && <p className="text-xs text-red-400">{fieldErrors.dueDate}</p>}
              </div>
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

          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              Summary
            </h3>
            <div className="flex justify-between text-sm">
              <span className="text-slate-muted">Subtotal</span>
              <span className="text-white font-mono">{formatCurrency(totals.subtotal, currency)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-muted">Tax</span>
              <span className="text-white font-mono">{formatCurrency(totals.tax, currency)}</span>
            </div>
            <div className="flex justify-between text-base font-semibold">
              <span className="text-white">Total</span>
              <span className="text-white font-mono">{formatCurrency(total, currency)}</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              Line Items
            </h3>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-white hover:border-teal-electric/50"
            >
              <Plus className="w-4 h-4" />
              Add line
            </button>
          </div>
          {fieldErrors.lineItems && <p className="text-xs text-red-400">{fieldErrors.lineItems}</p>}
          <div className="space-y-2">
            {lineItems.map((item, idx) => (
              <div key={item.id} className="grid grid-cols-1 md:grid-cols-6 gap-2 bg-slate-elevated/50 border border-slate-border/60 rounded-lg p-3">
                <div className="md:col-span-2 space-y-1">
                  <label className="text-xs text-slate-muted">Description</label>
                  <input
                    type="text"
                    value={item.description}
                    onChange={(e) => updateLine(item.id, { description: e.target.value })}
                    className={cn(
                      'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                      fieldErrors[`line-${idx}-description`] && 'border-red-500/60'
                    )}
                    placeholder="Item or service"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Qty</label>
                  <input
                    type="number"
                    min={0}
                    value={item.quantity}
                    onChange={(e) => updateLine(item.id, { quantity: Number(e.target.value) })}
                    className={cn(
                      'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                      fieldErrors[`line-${idx}-quantity`] && 'border-red-500/60'
                    )}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Unit Price</label>
                  <input
                    type="number"
                    min={0}
                    value={item.unit_price}
                    onChange={(e) => updateLine(item.id, { unit_price: Number(e.target.value) })}
                    className={cn(
                      'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                      fieldErrors[`line-${idx}-unit_price`] && 'border-red-500/60'
                    )}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Tax %</label>
                  <input
                    type="number"
                    min={0}
                    value={item.tax_rate}
                    onChange={(e) => updateLine(item.id, { tax_rate: Number(e.target.value) })}
                    className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Line Total</label>
                  <div className="text-white font-mono pt-2">
                    {formatCurrency((item.quantity || 0) * (item.unit_price || 0) * (1 + (item.tax_rate || 0) / 100), currency)}
                  </div>
                </div>
                <div className="flex items-center justify-end">
                  <button
                    type="button"
                    onClick={() => removeLine(item.id)}
                    className="p-2 text-slate-muted hover:text-red-400"
                    aria-label="Remove line item"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 sticky bottom-4 bg-slate-deep/80 backdrop-blur-sm p-3 rounded-lg border border-slate-border/60">
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
            {submitting ? 'Saving...' : 'Save Invoice'}
          </button>
        </div>
      </form>
    </div>
  );
}
