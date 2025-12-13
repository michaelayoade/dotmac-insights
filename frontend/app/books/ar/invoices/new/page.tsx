'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useFinanceInvoiceMutations } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save } from 'lucide-react';

export default function NewInvoicePage() {
  const router = useRouter();
  const { createInvoice } = useFinanceInvoiceMutations();
  const [form, setForm] = useState({
    customer_name: '',
    customer_id: '',
    description: '',
    amount: '',
    tax_amount: '',
    currency: 'NGN',
    status: 'pending',
    invoice_date: '',
    due_date: '',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      await createInvoice({
        customer_id: form.customer_id ? Number(form.customer_id) : undefined,
        customer_name: form.customer_name || undefined,
        description: form.description || undefined,
        amount: form.amount ? Number(form.amount) : undefined,
        tax_amount: form.tax_amount ? Number(form.tax_amount) : undefined,
        currency: form.currency || 'NGN',
        status: form.status as any,
        invoice_date: form.invoice_date || undefined,
        due_date: form.due_date || undefined,
      });
      router.push('/books/ar/invoices');
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
            href="/books/ar/invoices"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to invoices
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Invoice</p>
            <h1 className="text-xl font-semibold text-white">Create Invoice</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Customer Name" name="customer_name" value={form.customer_name} onChange={handleChange} />
          <Input label="Customer ID" name="customer_id" value={form.customer_id} onChange={handleChange} type="number" />
          <Input label="Amount" name="amount" value={form.amount} onChange={handleChange} type="number" />
          <Input label="Tax Amount" name="tax_amount" value={form.tax_amount} onChange={handleChange} type="number" />
          <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
          <Select
            label="Status"
            name="status"
            value={form.status}
            onChange={handleChange}
            options={['draft', 'pending', 'paid', 'partially_paid', 'overdue', 'cancelled']}
          />
          <Input label="Invoice Date" name="invoice_date" value={form.invoice_date} onChange={handleChange} type="date" />
          <Input label="Due Date" name="due_date" value={form.due_date} onChange={handleChange} type="date" />
        </div>
        <div>
          <label className="block text-sm text-slate-muted mb-2">Description</label>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            rows={3}
          />
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving...' : 'Create Invoice'}
        </button>
      </form>
    </div>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, ...rest } = props;
  return (
    <div className="space-y-2">
      <label className="text-sm text-slate-muted">{label}</label>
      <input
        {...rest}
        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
      />
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
    <div className="space-y-2">
      <label className="text-sm text-slate-muted">{label}</label>
      <select
        name={name}
        value={value}
        onChange={onChange}
        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </div>
  );
}
