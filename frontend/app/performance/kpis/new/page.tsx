'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, Gauge } from 'lucide-react';
import { useCreateKPI } from '@/hooks/usePerformance';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';
import type { Aggregation, DataSource, ScoringMethod } from '@/lib/performance.types';

export default function NewKPIPage() {
  const router = useRouter();
  const { trigger: createKPI } = useCreateKPI();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [dataSource, setDataSource] = useState<DataSource>('manual');
  const [scoringMethod, setScoringMethod] = useState<ScoringMethod>('linear');
  const [higherIsBetter, setHigherIsBetter] = useState(true);
  const aggregation: Aggregation = 'sum';
  const [targetValue, setTargetValue] = useState('');
  const [minValue, setMinValue] = useState('');
  const [maxValue, setMaxValue] = useState('');
  const [unit, setUnit] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!code.trim()) errs.code = 'KPI code is required';
    if (!name.trim()) errs.name = 'KPI name is required';
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
        data_source: dataSource,
        aggregation,
        scoring_method: scoringMethod,
        higher_is_better: higherIsBetter,
        target_value: targetValue ? Number(targetValue) : undefined,
        min_value: minValue ? Number(minValue) : undefined,
        max_value: maxValue ? Number(maxValue) : undefined,
      };
      const created = await createKPI(payload);
      router.push(`/performance/kpis/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create KPI');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/performance/kpis" label="KPIs" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Performance</p>
            <h1 className="text-xl font-semibold text-foreground">New KPI Definition</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Gauge className="w-4 h-4 text-violet-400" />
            Basic Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">KPI Code *</label>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50',
                  fieldErrors.code && 'border-red-500/60'
                )}
                placeholder="e.g., CSAT_SCORE"
              />
              {fieldErrors.code && <p className="text-xs text-red-400">{fieldErrors.code}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Name *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50',
                  fieldErrors.name && 'border-red-500/60'
                )}
                placeholder="Customer Satisfaction Score"
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
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              placeholder="Describe what this KPI measures..."
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Data Source</label>
              <select
                value={dataSource}
                onChange={(e) => setDataSource(e.target.value as DataSource)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              >
                <option value="manual">Manual</option>
                <option value="ticketing">Ticketing</option>
                <option value="field_service">Field Service</option>
                <option value="crm">CRM / Sales</option>
                <option value="project">Projects</option>
                <option value="finance">Finance</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Unit</label>
              <input
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="%, points, hours..."
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Gauge className="w-4 h-4 text-violet-400" />
            Scoring Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Scoring Method</label>
              <select
                value={scoringMethod}
                onChange={(e) => setScoringMethod(e.target.value as ScoringMethod)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              >
                <option value="linear">Linear</option>
                <option value="threshold">Threshold</option>
                <option value="tiered">Tiered</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Direction</label>
              <select
                value={higherIsBetter ? 'higher' : 'lower'}
                onChange={(e) => setHigherIsBetter(e.target.value === 'higher')}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              >
                <option value="higher">Higher is Better</option>
                <option value="lower">Lower is Better</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Target Value</label>
              <input
                type="number"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="100"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Min Value</label>
              <input
                type="number"
                value={minValue}
                onChange={(e) => setMinValue(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="0"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Max Value</label>
              <input
                type="number"
                value={maxValue}
                onChange={(e) => setMaxValue(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="100"
              />
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 flex justify-end gap-3">
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
            className="bg-violet-500 hover:bg-violet-600"
          >
            Create KPI
          </Button>
        </div>
      </form>
    </div>
  );
}
