'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useFinanceInvoiceMutations, useFinanceCustomers } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save, Plus, Trash2, Percent, Hash, Calendar as CalendarIcon, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CustomerSearch } from '@/components/EntitySearch';

export default function NewInvoicePage() {
  const router = useRouter();
  const { createInvoice } = useFinanceInvoiceMutations();
  const { data: customersData, isLoading: customersLoading } = useFinanceCustomers({ limit: 200, offset: 0 });
  const customers = useMemo(() => (customersData as any)?.items || (customersData as any)?.customers || [], [customersData]);

  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<{ id: number; name: string } | null>(null);
  const [form, setForm] = useState({
    customer_name: '',
    customer_id: '',
    description: '',
    currency: 'NGN',
    invoice_date: '',
    due_date: '',
    payment_terms: '30',
  });
  const [lineItems, setLineItems] = useState([
    { description: '', quantity: 1, unit_price: 0, tax_rate: 0 },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Auto-set due date based on payment terms when invoice date changes
  useEffect(() => {
    if (!form.invoice_date || !form.payment_terms) return;
    const days = Number(form.payment_terms) || 0;
    if (days <= 0) return;
    const base = new Date(form.invoice_date);
    const due = new Date(base);
    due.setDate(base.getDate() + days);
    const iso = due.toISOString().slice(0, 10);
    setForm((prev) => ({ ...prev, due_date: prev.due_date || iso }));
  }, [form.invoice_date, form.payment_terms]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleLineChange = (index: number, field: keyof typeof lineItems[number], value: string) => {
    setLineItems((prev) => {
      const updated = [...prev];
      if (field === 'description') {
        updated[index] = { ...updated[index], description: value };
      } else if (field === 'quantity') {
        updated[index] = { ...updated[index], quantity: Number(value) || 0 };
      } else if (field === 'unit_price') {
        updated[index] = { ...updated[index], unit_price: Number(value) || 0 };
      } else if (field === 'tax_rate') {
        updated[index] = { ...updated[index], tax_rate: Number(value) || 0 };
      }
      return updated;
    });
  };

  const addLine = () => setLineItems((prev) => [...prev, { description: '', quantity: 1, unit_price: 0, tax_rate: 0 }]);
  const removeLine = (idx: number) => setLineItems((prev) => prev.filter((_, i) => i !== idx));

  const totals = useMemo(() => {
    const subtotal = lineItems.reduce((acc, item) => acc + (item.quantity || 0) * (item.unit_price || 0), 0);
    const tax = lineItems.reduce(
      (acc, item) => acc + ((item.quantity || 0) * (item.unit_price || 0) * (item.tax_rate || 0)) / 100,
      0
    );
    const total = subtotal + tax;
    return { subtotal, tax, total };
  }, [lineItems]);

  const validate = () => {
    if (!selectedCustomer && !form.customer_name && !form.customer_id) return 'Customer is required';
    if (!form.invoice_date) return 'Invoice date is required';
    if (!form.due_date) return 'Due date is required';
    if (form.due_date && form.invoice_date && form.due_date < form.invoice_date) return 'Due date must be on/after invoice date';
    if (totals.total <= 0) return 'Add at least one line item with amount';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await createInvoice({
        customer_id: selectedCustomer?.id || (form.customer_id ? Number(form.customer_id) : undefined),
        customer_name: selectedCustomer?.name || form.customer_name || undefined,
        description: form.description || undefined,
        amount: totals.subtotal || 0,
        tax_amount: totals.tax || 0,
        total_amount: totals.total || 0,
        currency: form.currency || 'NGN',
        status: 'draft',
        invoice_date: form.invoice_date || undefined,
        due_date: form.due_date || undefined,
        line_items: lineItems.map((item) => ({
          description: item.description,
          quantity: item.quantity || 0,
          unit_price: item.unit_price || 0,
          tax_rate: item.tax_rate || 0,
        })),
      });
      router.push('/books/accounts-receivable/invoices');
    } catch (err: any) {
      setError(err?.message || 'Failed to create invoice');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/accounts-receivable/invoices"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to invoices
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Invoice</p>
            <h1 className="text-xl font-semibold text-foreground">Create Invoice</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          {/* Required fields */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <CustomerSearch
              label="Customer"
              customers={customers}
              value={selectedCustomer}
              onSelect={setSelectedCustomer}
              loading={customersLoading}
              required
            />
            <Input label="Invoice Date" name="invoice_date" value={form.invoice_date} onChange={handleChange} type="date" required />
            <Input
              label="Due Date"
              name="due_date"
              value={form.due_date}
              onChange={handleChange}
              type="date"
              min={form.invoice_date || undefined}
              required
              icon={<CalendarIcon className="w-4 h-4 text-slate-muted" />}
            />
          </div>

          {/* More options toggle */}
          <button
            type="button"
            onClick={() => setShowMoreOptions(!showMoreOptions)}
            className="flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
          >
            {showMoreOptions ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            More options
          </button>

          {/* Optional fields */}
          {showMoreOptions && (
            <div className="space-y-4 pt-2 border-t border-slate-border/50">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
                <Input
                  label="Payment Terms (days)"
                  name="payment_terms"
                  value={form.payment_terms}
                  onChange={handleChange}
                  type="number"
                  icon={<Hash className="w-4 h-4 text-slate-muted" />}
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-2">Memo / Customer Note</label>
                <textarea
                  name="description"
                  value={form.description}
                  onChange={handleChange}
                  className="input-field"
                  rows={2}
                  placeholder="Optional note for the customer"
                />
              </div>
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-foreground font-semibold">Line Items</p>
              <p className="text-xs text-slate-muted">Item, quantity, unit price, and per-line tax</p>
            </div>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-foreground hover:bg-slate-elevated"
            >
              <Plus className="w-4 h-4" />
              Add line
            </button>
          </div>
          <div className="space-y-3">
            {lineItems.map((item, idx) => (
              <div key={idx} className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr_1fr_auto] gap-3 items-center bg-slate-elevated border border-slate-border rounded-lg p-3">
                <div>
                  <label className="text-xs text-slate-muted">Description</label>
                  <input
                    type="text"
                    value={item.description}
                    onChange={(e) => handleLineChange(idx, 'description', e.target.value)}
                    placeholder="Service or item name"
                    className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-muted">Qty</label>
                  <input
                    type="number"
                    min={0}
                    value={item.quantity}
                    onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                    className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-muted">Unit Price</label>
                  <input
                    type="number"
                    min={0}
                    value={item.unit_price}
                    onChange={(e) => handleLineChange(idx, 'unit_price', e.target.value)}
                    className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-muted flex items-center gap-1"><Percent className="w-3 h-3" />Tax %</label>
                  <input
                    type="number"
                    min={0}
                    value={item.tax_rate}
                    onChange={(e) => handleLineChange(idx, 'tax_rate', e.target.value)}
                    className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="p-2 text-slate-muted hover:text-coral-alert hover:bg-slate-card rounded-lg"
                    aria-label="Remove line"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-2 max-w-xs ml-auto">
            <p className="text-sm text-foreground font-semibold">Totals</p>
            <TotalRow label="Subtotal" value={totals.subtotal} currency={form.currency} />
            <TotalRow label="Tax" value={totals.tax} currency={form.currency} />
            <hr className="border-slate-border/60" />
            <TotalRow label="Total" value={totals.total} currency={form.currency} bold />
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Link
            href="/books/accounts-receivable/invoices"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Create Invoice'}
          </button>
        </div>
      </form>
    </div>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; icon?: React.ReactNode }) {
  const { label, icon, ...rest } = props;
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      <div className="relative">
        {icon && <div className="absolute left-3 top-1/2 -translate-y-1/2">{icon}</div>}
        <input
          {...rest}
          className={cn('input-field', icon && 'pl-9')}
        />
      </div>
    </div>
  );
}

function TotalRow({ label, value, currency, bold }: { label: string; value: number; currency?: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-muted">{label}</span>
      <span className={cn('font-mono', bold ? 'text-foreground font-semibold' : 'text-foreground')}>
        {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {currency || ''}
      </span>
    </div>
  );
}
