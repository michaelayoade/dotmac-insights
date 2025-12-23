'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, FileText } from 'lucide-react';
import { useCreateTemplate } from '@/hooks/usePerformance';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewTemplatePage() {
  const router = useRouter();
  const { trigger: createTemplate } = useCreateTemplate();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [targetDepartment, setTargetDepartment] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = 'Template name is required';
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
        applicable_designations: targetRole.trim() ? [targetRole.trim()] : undefined,
        applicable_departments: targetDepartment.trim() ? [targetDepartment.trim()] : undefined,
      };
      const created = await createTemplate(payload);
      router.push(`/performance/templates/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create template');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/performance/templates" label="Templates" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Performance</p>
            <h1 className="text-xl font-semibold text-foreground">New Scorecard Template</h1>
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
            <FileText className="w-4 h-4 text-amber-400" />
            Template Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Template Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50',
                fieldErrors.name && 'border-red-500/60'
              )}
              placeholder="e.g., Sales Team Scorecard"
            />
            {fieldErrors.name && <p className="text-xs text-red-400">{fieldErrors.name}</p>}
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              placeholder="Describe what this template is for..."
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Target Role</label>
              <input
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                placeholder="e.g., Sales Representative"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Target Department</label>
              <input
                value={targetDepartment}
                onChange={(e) => setTargetDepartment(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                placeholder="e.g., Sales"
              />
            </div>
          </div>
          <p className="text-xs text-slate-muted">
            After creating the template, you can add KRAs and KPIs to it.
          </p>
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
            className="bg-amber-500 hover:bg-amber-600"
          >
            Create Template
          </Button>
        </div>
      </form>
    </div>
  );
}
