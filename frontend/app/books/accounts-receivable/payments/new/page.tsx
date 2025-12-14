'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useFinancePaymentMutations } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save, Calendar as CalendarIcon, CreditCard, Hash, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function NewPaymentPage() {
  const router = useRouter();
  const { createPayment } = useFinancePaymentMutations();
  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [form, setForm] = useState({
    customer_name: '',
    customer_id: '',
    invoice_id: '',
    amount: '',
    receipt_number: '',
    currency: 'NGN',
    payment_method: 'bank_transfer',
    payment_date: '',
    transaction_reference: '',
    notes: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const validate = () => {
    if (!form.customer_name && !form.customer_id) return 'Customer is required';
    if (!form.amount || Number(form.amount) <= 0) return 'Amount must be greater than zero';
    if (!form.payment_date) return 'Payment date is required';
    return null;
  };

  const amountDisplay = useMemo(() => Number(form.amount || 0), [form.amount]);

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
      await createPayment({
        customer_id: form.customer_id ? Number(form.customer_id) : undefined,
        invoice_id: form.invoice_id ? Number(form.invoice_id) : undefined,
        receipt_number: form.receipt_number || undefined,
        amount: form.amount ? Number(form.amount) : undefined,
        currency: form.currency || 'NGN',
        payment_method: form.payment_method as any,
        status: 'pending',
        payment_date: form.payment_date || undefined,
        transaction_reference: form.transaction_reference || undefined,
        notes: form.notes || undefined,
        customer_name: form.customer_name || undefined,
      });
      router.push('/books/accounts-receivable/payments');
    } catch (err: any) {
      setError(err?.message || 'Failed to create payment');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/accounts-receivable/payments"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to payments
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Payment</p>
            <h1 className="text-xl font-semibold text-white">Record Payment</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          {/* Required fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Input label="Customer Name" name="customer_name" value={form.customer_name} onChange={handleChange} required />
            <Input
              label="Amount"
              name="amount"
              value={form.amount}
              onChange={handleChange}
              type="number"
              min={0}
              required
              icon={<Hash className="w-4 h-4 text-slate-muted" />}
            />
            <Input label="Payment Date" name="payment_date" value={form.payment_date} onChange={handleChange} type="date" required icon={<CalendarIcon className="w-4 h-4 text-slate-muted" />} />
            <Select
              label="Payment Method"
              name="payment_method"
              value={form.payment_method}
              onChange={handleChange}
              options={['bank_transfer', 'cash', 'card', 'mobile_money', 'paystack', 'flutterwave', 'other']}
            />
          </div>

          {/* More options toggle */}
          <button
            type="button"
            onClick={() => setShowMoreOptions(!showMoreOptions)}
            className="flex items-center gap-2 text-sm text-slate-muted hover:text-white transition-colors"
          >
            {showMoreOptions ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            More options
          </button>

          {/* Optional fields */}
          {showMoreOptions && (
            <div className="space-y-4 pt-2 border-t border-slate-border/50">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Input label="Invoice ID" name="invoice_id" value={form.invoice_id} onChange={handleChange} type="number" placeholder="Link to invoice" />
                <Input label="Customer ID" name="customer_id" value={form.customer_id} onChange={handleChange} type="number" />
                <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="Receipt Number" name="receipt_number" value={form.receipt_number} onChange={handleChange} />
                <Input
                  label="Transaction Reference"
                  name="transaction_reference"
                  value={form.transaction_reference}
                  onChange={handleChange}
                  icon={<CreditCard className="w-4 h-4 text-slate-muted" />}
                  placeholder="Bank ref or gateway ID"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-2">Notes</label>
                <textarea
                  name="notes"
                  value={form.notes}
                  onChange={handleChange}
                  className="input-field"
                  rows={2}
                  placeholder="Optional internal note"
                />
              </div>
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-2 max-w-xs ml-auto">
            <p className="text-sm text-white font-semibold">Summary</p>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-muted">Amount</span>
              <span className="font-mono text-white">{amountDisplay.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {form.currency}</span>
            </div>
            {form.invoice_id && (
              <p className="text-xs text-slate-muted">Will be applied to Invoice #{form.invoice_id}</p>
            )}
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
            href="/books/accounts-receivable/payments"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Record Payment'}
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

function Select({
  label,
  name,
  value,
  onChange,
  options,
}: {
  label: string;
  name: string;
  value: string;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  options: string[];
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      <select
        name={name}
        value={value}
        onChange={onChange}
        className="input-field"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </div>
  );
}
