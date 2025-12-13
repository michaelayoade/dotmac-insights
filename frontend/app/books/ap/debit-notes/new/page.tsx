'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { usePurchasingDebitNoteMutations } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Save } from 'lucide-react';

export default function NewDebitNotePage() {
  const router = useRouter();
  const { createDebitNote } = usePurchasingDebitNoteMutations();
  const [form, setForm] = useState({
    supplier: '',
    supplier_name: '',
    posting_date: '',
    due_date: '',
    grand_total: '',
    outstanding_amount: '',
    paid_amount: '',
    currency: 'NGN',
    status: 'draft',
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
      await createDebitNote({
        supplier: form.supplier || form.supplier_name,
        supplier_name: form.supplier_name || form.supplier,
        posting_date: form.posting_date || undefined,
        due_date: form.due_date || undefined,
        grand_total: form.grand_total ? Number(form.grand_total) : undefined,
        outstanding_amount: form.outstanding_amount ? Number(form.outstanding_amount) : undefined,
        paid_amount: form.paid_amount ? Number(form.paid_amount) : 0,
        total_taxes_and_charges: 0,
        currency: form.currency || 'NGN',
        conversion_rate: 1,
        status: form.status as any,
      });
      router.push('/books/ap/debit-notes');
    } catch (err: any) {
      setError(err?.message || 'Failed to create debit note');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/ap/debit-notes"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to debit notes
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Debit Note</p>
            <h1 className="text-xl font-semibold text-white">Create Debit Note</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Supplier Name" name="supplier_name" value={form.supplier_name} onChange={handleChange} />
          <Input label="Supplier ID" name="supplier" value={form.supplier} onChange={handleChange} />
          <Input label="Grand Total" name="grand_total" value={form.grand_total} onChange={handleChange} type="number" />
          <Input label="Outstanding Amount" name="outstanding_amount" value={form.outstanding_amount} onChange={handleChange} type="number" />
          <Input label="Paid Amount" name="paid_amount" value={form.paid_amount} onChange={handleChange} type="number" />
          <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
          <Select
            label="Status"
            name="status"
            value={form.status}
            onChange={handleChange}
            options={['draft', 'submitted', 'paid', 'unpaid', 'cancelled']}
          />
          <Input label="Posting Date" name="posting_date" value={form.posting_date} onChange={handleChange} type="date" />
          <Input label="Due Date" name="due_date" value={form.due_date} onChange={handleChange} type="date" />
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
          {saving ? 'Saving...' : 'Create Debit Note'}
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
