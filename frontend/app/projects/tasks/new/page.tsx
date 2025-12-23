'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, CheckSquare } from 'lucide-react';
import { useTaskMutations, useProjects } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewTaskPage() {
  const router = useRouter();
  const { createTask } = useTaskMutations();
  const { data: projects } = useProjects({ limit: 100 });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [subject, setSubject] = useState('');
  const [projectId, setProjectId] = useState('');
  const [status, setStatus] = useState('open');
  const [priority, setPriority] = useState('medium');
  const [expectedStart, setExpectedStart] = useState('');
  const [expectedEnd, setExpectedEnd] = useState('');
  const [description, setDescription] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!subject.trim()) errs.subject = 'Task subject is required';
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
        subject: subject.trim(),
        project_id: projectId ? Number(projectId) : undefined,
        status: status as any,
        priority: priority as any,
        exp_start_date: expectedStart || undefined,
        exp_end_date: expectedEnd || undefined,
        description: description.trim() || undefined,
      };
      const created = await createTask(payload);
      router.push(`/projects/tasks/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create task');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/projects/tasks" label="Tasks" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Projects</p>
            <h1 className="text-xl font-semibold text-foreground">New Task</h1>
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
            <CheckSquare className="w-4 h-4 text-teal-electric" />
            Task Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Subject *</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                fieldErrors.subject && 'border-red-500/60'
              )}
              placeholder="Task title"
            />
            {fieldErrors.subject && <p className="text-xs text-red-400">{fieldErrors.subject}</p>}
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="">No Project</option>
              {projects?.data?.map((project: any) => (
                <option key={project.id} value={project.id}>{project.project_name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="open">Open</option>
                <option value="working">Working</option>
                <option value="pending_review">Pending Review</option>
                <option value="overdue">Overdue</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Expected Start</label>
              <input
                type="date"
                value={expectedStart}
                onChange={(e) => setExpectedStart(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Expected End</label>
              <input
                type="date"
                value={expectedEnd}
                onChange={(e) => setExpectedEnd(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="Task details..."
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
            module="projects"
          >
            Create Task
          </Button>
        </div>
      </form>
    </div>
  );
}
