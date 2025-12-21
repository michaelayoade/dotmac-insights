'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, CheckCircle2, Home, Save } from 'lucide-react';
import { useInventoryWarehouseMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function InventoryWarehouseCreatePage() {
  const router = useRouter();
  const { createWarehouse } = useInventoryWarehouseMutations();
  const [form, setForm] = useState({
    name: '',
    parent_warehouse: '',
    company: '',
    is_group: false,
    address: '',
    latitude: '',
    longitude: '',
    contact_person: '',
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
      await createWarehouse({
        ...form,
        parent_warehouse: form.parent_warehouse || null,
        latitude: form.latitude ? Number(form.latitude) : undefined,
        longitude: form.longitude ? Number(form.longitude) : undefined,
      });
      setSuccess(true);
      setTimeout(() => router.push('/inventory'), 800);
    } catch (err: any) {
      setError(err?.message || 'Failed to create warehouse');
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
        <h1 className="text-xl font-semibold text-foreground">New Warehouse</h1>
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
          <span>Warehouse created</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { label: 'Name', name: 'name', required: true },
            { label: 'Parent Warehouse', name: 'parent_warehouse' },
            { label: 'Company', name: 'company' },
            { label: 'Contact Person', name: 'contact_person' },
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
            <label className="text-sm text-slate-muted">Address</label>
            <textarea
              name="address"
              value={form.address}
              onChange={handleChange}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              rows={2}
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:col-span-2">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Latitude</label>
              <input
                name="latitude"
                value={form.latitude}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Longitude</label>
              <input
                name="longitude"
                value={form.longitude}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
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
          <label className="flex items-center gap-2 text-sm text-slate-muted">
            <input
              type="checkbox"
              name="is_group"
              checked={form.is_group}
              onChange={handleChange}
              className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
            />
            Is group warehouse
          </label>
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
          {submitting ? 'Saving...' : 'Create Warehouse'}
        </button>
      </form>
    </div>
  );
}
