'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useFinanceCreditNoteMutations, useFinanceCustomers } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save, Plus, Trash2, Percent, Calendar as CalendarIcon, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CustomerSearch } from '@/components/EntitySearch';

export default function NewCreditNotePage() {
  const router = useRouter();
  const { createCreditNote } = useFinanceCreditNoteMutations();
  const { data: customersData, isLoading: customersLoading } = useFinanceCustomers({ limit: 200, offset: 0 });
  const customers = useMemo(() => (customersData as any)?.items || (customersData as any)?.customers || [], [customersData]);

  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<{ id: number; name: string } | null>(null);
  const [form, setForm] = useState({
    customer_name: '',
    customer_id: '',
    invoice_id: '',
    currency: 'NGN',
    issue_date: '',
    reason: '',
    memo: '',
  });
  type LineItem = { description: string; quantity: number; unit_price: number; tax_rate: number };
  const [lineItems, setLineItems] = useState<LineItem[]>([
    { description: '', quantity: 1, unit_price: 0, tax_rate: 0 },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleLineChange = (index: number, field: keyof LineItem, value: string) => {
    const numericFields: Array<keyof LineItem> = ['quantity', 'unit_price', 'tax_rate'];
    const updated = [...lineItems];
    updated[index] = {
      ...updated[index],
      [field]: numericFields.includes(field) ? (Number(value) || 0) : value,
    } as LineItem;
    setLineItems(updated);
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
    if (!form.issue_date) return 'Issue date is required';
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
      await createCreditNote({
        customer_id: selectedCustomer?.id || (form.customer_id ? Number(form.customer_id) : undefined),
        customer_name: selectedCustomer?.name || form.customer_name || undefined,
        invoice_id: form.invoice_id ? Number(form.invoice_id) : undefined,
        description: form.reason || form.memo || undefined,
        amount: totals.total || 0,
        tax_amount: totals.tax || 0,
        currency: form.currency || 'NGN',
        status: 'draft',
        issue_date: form.issue_date || undefined,
        line_items: lineItems.map((item) => ({
          description: item.description,
          quantity: item.quantity || 0,
          unit_price: item.unit_price || 0,
          tax_rate: item.tax_rate || 0,
        })) as any,
        memo: form.memo || undefined,
      } as any);
      router.push('/books/accounts-receivable/credit-notes');
    } catch (err: any) {
      setError(err?.message || 'Failed to create credit note');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/accounts-receivable/credit-notes"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to credit notes
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Credit Note</p>
            <h1 className="text-xl font-semibold text-foreground">Issue Credit</h1>
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
            <Input
              label="Issue Date"
              name="issue_date"
              value={form.issue_date}
              onChange={handleChange}
              type="date"
              required
              icon={<CalendarIcon className="w-4 h-4 text-slate-muted" />}
            />
            <Input
              label="Reason"
              name="reason"
              value={form.reason}
              onChange={handleChange}
              placeholder="Return, discount, correction..."
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
                <Input label="Invoice ID" name="invoice_id" value={form.invoice_id} onChange={handleChange} type="number" placeholder="Link to original invoice" />
                <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-2">Memo / Notes</label>
                <textarea
                  name="memo"
                  value={form.memo}
                  onChange={handleChange}
                  className="input-field"
                  rows={2}
                  placeholder="Optional internal note"
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
                    placeholder="Item or service"
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
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-2 max-w-sm ml-auto">
            <p className="text-sm text-foreground font-semibold">Totals</p>
            <TotalRow label="Subtotal" value={totals.subtotal} currency={form.currency} />
            <TotalRow label="Tax" value={totals.tax} currency={form.currency} />
            <hr className="border-slate-border/60" />
            <TotalRow label="Total Credit" value={totals.total} currency={form.currency} bold />
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
            href="/books/accounts-receivable/credit-notes"
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
            {saving ? 'Saving...' : 'Issue Credit'}
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
