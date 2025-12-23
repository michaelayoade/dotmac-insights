'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Calendar } from 'lucide-react';
import { useCreatePeriod } from '@/hooks/usePerformance';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';
import type { PeriodType } from '@/lib/performance.types';

export default function NewPeriodPage() {
  const router = useRouter();
  const { trigger: createPeriod } = useCreatePeriod();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [name, setName] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [description, setDescription] = useState('');
  const periodType: PeriodType = 'custom';

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = 'Period name is required';
    if (!startDate) errs.startDate = 'Start date is required';
    if (!endDate) errs.endDate = 'End date is required';
    if (startDate && endDate && new Date(startDate) >= new Date(endDate)) {
      errs.endDate = 'End date must be after start date';
    }
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
        code: name.trim().toUpperCase().replace(/\s+/g, '_'),
        name: name.trim(),
        period_type: periodType,
        start_date: startDate,
        end_date: endDate,
      };
      const created = await createPeriod(payload);
      router.push(`/performance/periods/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create period');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/performance/periods" label="Periods" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Performance</p>
            <h1 className="text-xl font-semibold text-foreground">New Review Period</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="max-w-xl">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Calendar className="w-4 h-4 text-blue-400" />
            Period Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Period Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50',
                fieldErrors.name && 'border-red-500/60'
              )}
              placeholder="e.g., Q1 2025 Review"
            />
            {fieldErrors.name && <p className="text-xs text-red-400">{fieldErrors.name}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Start Date *</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50',
                  fieldErrors.startDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.startDate && <p className="text-xs text-red-400">{fieldErrors.startDate}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">End Date *</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50',
                  fieldErrors.endDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.endDate && <p className="text-xs text-red-400">{fieldErrors.endDate}</p>}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              placeholder="Optional notes about this review period..."
            />
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
            className="bg-blue-500 hover:bg-blue-600"
          >
            Create Period
          </Button>
        </div>
      </form>
    </div>
  );
}
