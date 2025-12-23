'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Target } from 'lucide-react';
import { useCreateKRA, useKRACategories } from '@/hooks/usePerformance';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewKRAPage() {
  const router = useRouter();
  const { trigger: createKRA } = useCreateKRA();
  const { data: categories } = useKRACategories();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [defaultWeight, setDefaultWeight] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!code.trim()) errs.code = 'KRA code is required';
    if (!name.trim()) errs.name = 'KRA name is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = {
        code: code.trim().toUpperCase(),
        name: name.trim(),
        description: description.trim() || undefined,
        category: category || undefined,
      };
      const created = await createKRA(payload);
      router.push(`/performance/kras/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create KRA');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/performance/kras" label="KRAs" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Performance</p>
            <h1 className="text-xl font-semibold text-foreground">New Key Result Area</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="max-w-2xl">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Target className="w-4 h-4 text-emerald-400" />
            KRA Details
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">KRA Code *</label>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50',
                  fieldErrors.code && 'border-red-500/60'
                )}
                placeholder="e.g., CUST_SAT"
              />
              {fieldErrors.code && <p className="text-xs text-red-400">{fieldErrors.code}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Name *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50',
                  fieldErrors.name && 'border-red-500/60'
                )}
                placeholder="Customer Satisfaction"
              />
              {fieldErrors.name && <p className="text-xs text-red-400">{fieldErrors.name}</p>}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              placeholder="Describe this key result area..."
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              >
                <option value="">Select Category</option>
                {categories?.categories?.map((cat: string) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Default Weight (%)</label>
              <input
                type="number"
                value={defaultWeight}
                onChange={(e) => setDefaultWeight(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                placeholder="e.g., 20"
                min="0"
                max="100"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.back()}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            loading={submitting}
            className="bg-emerald-500 hover:bg-emerald-600"
          >
            Create KRA
          </Button>
        </div>
      </form>
    </div>
  );
}
