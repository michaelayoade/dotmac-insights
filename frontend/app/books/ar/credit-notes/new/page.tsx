'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useFinanceCreditNoteMutations } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save } from 'lucide-react';

export default function NewCreditNotePage() {
  const router = useRouter();
  const { createCreditNote } = useFinanceCreditNoteMutations();
  const [form, setForm] = useState({
    customer_name: '',
    customer_id: '',
    invoice_id: '',
    amount: '',
    currency: 'NGN',
    status: 'issued',
    issue_date: '',
    description: '',
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
      await createCreditNote({
        customer_id: form.customer_id ? Number(form.customer_id) : undefined,
        customer_name: form.customer_name || undefined,
        invoice_id: form.invoice_id ? Number(form.invoice_id) : undefined,
        description: form.description || undefined,
        amount: form.amount ? Number(form.amount) : undefined,
        currency: form.currency || 'NGN',
        status: form.status as any,
        issue_date: form.issue_date || undefined,
      });
      router.push('/books/ar/credit-notes');
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
            href="/books/ar/credit-notes"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to credit notes
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Credit Note</p>
            <h1 className="text-xl font-semibold text-white">Issue Credit</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Customer Name" name="customer_name" value={form.customer_name} onChange={handleChange} />
          <Input label="Customer ID" name="customer_id" value={form.customer_id} onChange={handleChange} type="number" />
          <Input label="Invoice ID" name="invoice_id" value={form.invoice_id} onChange={handleChange} type="number" />
          <Input label="Amount" name="amount" value={form.amount} onChange={handleChange} type="number" />
          <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
          <Select
            label="Status"
            name="status"
            value={form.status}
            onChange={handleChange}
            options={['draft', 'issued', 'applied', 'cancelled']}
          />
          <Input label="Issue Date" name="issue_date" value={form.issue_date} onChange={handleChange} type="date" />
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
          {saving ? 'Saving...' : 'Create Credit Note'}
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
