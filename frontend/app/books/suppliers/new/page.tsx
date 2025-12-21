'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Save, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { accountingApi, AccountingSupplierPayload } from '@/lib/api/domains/accounting';
import { cn } from '@/lib/utils';

const SUPPLIER_TYPES = ['Company', 'Individual', 'Proprietorship', 'Partnership'] as const;

export default function NewSupplierPage() {
  const router = useRouter();
  const [form, setForm] = useState<AccountingSupplierPayload>({
    supplier_name: '',
    supplier_code: '',
    supplier_type: 'Company',
    supplier_group: '',
    country: 'Nigeria',
    default_currency: 'NGN',
    payment_terms: '',
    tax_id: '',
    email: '',
    phone: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value || null }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.supplier_name.trim()) {
      setError('Supplier name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await accountingApi.createSupplier(form);
      setSuccess(true);
      setTimeout(() => router.push('/books/suppliers'), 800);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create supplier');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/books/suppliers"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Suppliers</p>
          <h1 className="text-xl font-semibold text-foreground">New Supplier</h1>
        </div>
      </div>

      {error && (
        <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-coral-alert" />
          <span className="text-sm text-coral-alert">{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-emerald-success/10 border border-emerald-success/30 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-success" />
          <span className="text-sm text-emerald-success">Supplier created successfully</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h2 className="text-sm font-medium text-slate-muted mb-4">Basic Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Supplier Name *</label>
              <input
                name="supplier_name"
                value={form.supplier_name}
                onChange={handleChange}
                required
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Supplier Code</label>
              <input
                name="supplier_code"
                value={form.supplier_code || ''}
                onChange={handleChange}
                placeholder="Auto-generated if empty"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Supplier Type</label>
              <select
                name="supplier_type"
                value={form.supplier_type || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                {SUPPLIER_TYPES.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Supplier Group</label>
              <input
                name="supplier_group"
                value={form.supplier_group || ''}
                onChange={handleChange}
                placeholder="e.g., Services, Materials"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h2 className="text-sm font-medium text-slate-muted mb-4">Contact & Location</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Email</label>
              <input
                name="email"
                type="email"
                value={form.email || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Phone</label>
              <input
                name="phone"
                value={form.phone || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Country</label>
              <input
                name="country"
                value={form.country || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Tax ID</label>
              <input
                name="tax_id"
                value={form.tax_id || ''}
                onChange={handleChange}
                placeholder="TIN / VAT Number"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h2 className="text-sm font-medium text-slate-muted mb-4">Payment Settings</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Default Currency</label>
              <input
                name="default_currency"
                value={form.default_currency || ''}
                onChange={handleChange}
                placeholder="NGN"
                maxLength={3}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Payment Terms</label>
              <input
                name="payment_terms"
                value={form.payment_terms || ''}
                onChange={handleChange}
                placeholder="e.g., Net 30"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90',
              saving && 'opacity-60 cursor-not-allowed'
            )}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Creating...' : 'Create Supplier'}
          </button>
          <Link
            href="/books/suppliers"
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
