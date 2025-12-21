'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { useInventoryItemMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function InventoryItemCreatePage() {
  const router = useRouter();
  const { createItem } = useInventoryItemMutations();
  const [form, setForm] = useState({
    item_code: '',
    item_name: '',
    description: '',
    item_group: '',
    uom: 'Nos',
    brand: '',
    is_stock_item: true,
    default_warehouse: '',
    reorder_level: '',
    reorder_qty: '',
    valuation_rate: '',
    standard_selling_rate: '',
    standard_buying_rate: '',
    serial_number_series: '',
    barcode: '',
    status: 'active',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement;
    const { name, value, type } = target;
    const nextValue = type === 'checkbox' ? target.checked : value;
    setForm((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createItem({
        ...form,
        reorder_level: form.reorder_level ? Number(form.reorder_level) : undefined,
        reorder_qty: form.reorder_qty ? Number(form.reorder_qty) : undefined,
        valuation_rate: form.valuation_rate ? Number(form.valuation_rate) : undefined,
        standard_selling_rate: form.standard_selling_rate ? Number(form.standard_selling_rate) : undefined,
        standard_buying_rate: form.standard_buying_rate ? Number(form.standard_buying_rate) : undefined,
      });
      setSuccess(true);
      setTimeout(() => router.push('/inventory'), 800);
    } catch (err: any) {
      setError(err?.message || 'Failed to create item');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/inventory"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <h1 className="text-xl font-semibold text-foreground">New Inventory Item</h1>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>Item created</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { label: 'Item Code', name: 'item_code', required: true },
            { label: 'Item Name', name: 'item_name', required: true },
            { label: 'Item Group', name: 'item_group' },
            { label: 'Brand', name: 'brand' },
            { label: 'Default Warehouse', name: 'default_warehouse' },
            { label: 'UOM', name: 'uom' },
          ].map((field) => (
            <div key={field.name} className="space-y-1">
              <label className="text-sm text-slate-muted">{field.label}</label>
              <input
                name={field.name}
                value={(form as any)[field.name]}
                onChange={handleChange}
                required={field.required}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          ))}
          <div className="space-y-1 md:col-span-2">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              rows={3}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              name="is_stock_item"
              checked={form.is_stock_item}
              onChange={handleChange}
              className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
            />
            <label className="text-sm text-slate-muted">Stock Item</label>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Status</label>
            <select
              name="status"
              value={form.status}
              onChange={handleChange}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'Reorder Level', name: 'reorder_level' },
            { label: 'Reorder Qty', name: 'reorder_qty' },
            { label: 'Valuation Rate', name: 'valuation_rate' },
            { label: 'Selling Rate', name: 'standard_selling_rate' },
            { label: 'Buying Rate', name: 'standard_buying_rate' },
            { label: 'Serial Number Series', name: 'serial_number_series' },
            { label: 'Barcode', name: 'barcode' },
          ].map((field) => (
            <div key={field.name} className="space-y-1">
              <label className="text-sm text-slate-muted">{field.label}</label>
              <input
                name={field.name}
                value={(form as any)[field.name]}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          ))}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className={cn(
            'inline-flex items-center gap-2 px-4 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70',
            submitting && 'opacity-70 cursor-not-allowed'
          )}
        >
          <Save className="w-4 h-4" />
          {submitting ? 'Saving...' : 'Create Item'}
        </button>
      </form>
    </div>
  );
}
