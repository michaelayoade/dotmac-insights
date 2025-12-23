'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Activity } from 'lucide-react';
import { useActivityMutations } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton, LoadingState } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function NewActivityPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:write');
  const router = useRouter();
  const { createActivity } = useActivityMutations();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [activityType, setActivityType] = useState('call');
  const [subject, setSubject] = useState('');
  const [status, setStatus] = useState('open');
  const [priority, setPriority] = useState('medium');
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!subject.trim()) errs.subject = 'Subject is required';
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
        activity_type: activityType,
        subject: subject.trim(),
        status,
        priority,
        due_date: dueDate || undefined,
        notes: notes.trim() || undefined,
      };
      const created = await createActivity(payload);
      router.push('/crm/activities');
    } catch (err: any) {
      setError(err?.message || 'Failed to create activity');
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:write permission to create activities."
        backHref="/crm/activities"
        backLabel="Back to Activities"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/crm/activities" label="Activities" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">CRM</p>
            <h1 className="text-xl font-semibold text-foreground">New Activity</h1>
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
            <Activity className="w-4 h-4 text-cyan-400" />
            Activity Details
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Activity Type</label>
              <select
                value={activityType}
                onChange={(e) => setActivityType(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              >
                <option value="call">Call</option>
                <option value="email">Email</option>
                <option value="meeting">Meeting</option>
                <option value="task">Task</option>
                <option value="demo">Demo</option>
                <option value="follow_up">Follow Up</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Subject *</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50',
                fieldErrors.subject && 'border-red-500/60'
              )}
              placeholder="Activity subject"
            />
            {fieldErrors.subject && <p className="text-xs text-red-400">{fieldErrors.subject}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              >
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              placeholder="Activity notes..."
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
            className="bg-cyan-500 hover:bg-cyan-600"
          >
            Create Activity
          </Button>
        </div>
      </form>
    </div>
  );
}
