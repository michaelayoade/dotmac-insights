'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertTriangle,
  ArrowLeft,
  ListTodo,
  Calendar,
  Tag,
  User,
  CheckCircle2,
  Clock,
  FolderKanban,
  Edit,
  RefreshCw,
  Target,
  Link2,
  FileText,
  Timer,
  TrendingUp,
  Save,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useTaskDetail, useTaskMutations } from '@/hooks/useApi';
import { useEmployeeOptions } from '@/hooks/usePickers';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { EmployeeSearch } from '@/components/EntitySearch';
import { Button, StatusPill } from '@/components/ui';

function StatusBadge({ status }: { status: string }) {
  const icons: Record<string, LucideIcon> = {
    open: ListTodo,
    working: Clock,
    pending_review: Target,
    completed: CheckCircle2,
    cancelled: AlertTriangle,
    overdue: AlertTriangle,
  };
  const tones: Record<string, StatusTone> = {
    open: 'info',
    working: 'warning',
    pending_review: 'info',
    completed: 'success',
    cancelled: 'default',
    overdue: 'danger',
  };
  const labels: Record<string, string> = {
    pending_review: 'Pending Review',
  };
  const Icon = icons[status] || icons.open;

  return (
    <StatusPill
      label={labels[status] || formatStatusLabel(status)}
      tone={tones[status] || 'default'}
      size="md"
      icon={Icon}
      className="border border-current/30"
    />
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    urgent: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
    high: 'text-red-400 bg-red-500/10 border-red-500/30',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    low: 'text-foreground-secondary bg-slate-500/10 border-slate-500/30',
  };
  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', colors[priority] || colors.medium)}>
      <Tag className="w-3 h-3" />
      {priority}
    </span>
  );
}

function ProgressRing({ percent, size = 80, strokeWidth = 8 }: { percent: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percent / 100) * circumference;
  const color = percent >= 100 ? '#10b981' : percent >= 50 ? '#2dd4bf' : '#3b82f6';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#334155"
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-bold text-foreground">{percent}%</span>
      </div>
    </div>
  );
}

function InfoRow({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon?: LucideIcon }) {
  return (
    <div className="flex items-start gap-3 py-2">
      {Icon && <Icon className="w-4 h-4 text-slate-muted mt-0.5" />}
      <div className="flex-1">
        <p className="text-slate-muted text-sm">{label}</p>
        <p className="text-foreground font-medium">{value || '-'}</p>
      </div>
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const isValidId = Number.isFinite(id);

  const { data, isLoading, error, mutate } = useTaskDetail(isValidId ? id : null);
  const { updateTask } = useTaskMutations();
  const { employees } = useEmployeeOptions();

  const [editMode, setEditMode] = useState(false);
  const [assignedEmployee, setAssignedEmployee] = useState<{ id: number; name: string } | null>(null);
  const [assigneeDirty, setAssigneeDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (!isValidId) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Invalid task ID.</p>
        <Button
          onClick={() => router.push('/projects/tasks')}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to tasks
        </Button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-24 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="h-64 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load task</p>
        <Button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
      </div>
    );
  }

  const task = data as any;
  const progress = task.progress || 0;
  const isOverdue = task.exp_end_date && new Date(task.exp_end_date) < new Date() && task.status !== 'completed';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link
            href="/projects/tasks"
            className="mt-1 inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-foreground line-clamp-1">{task.subject}</h1>
              {isOverdue && (
                <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 text-xs font-medium">
                  OVERDUE
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={task.status || 'open'} />
              <PriorityBadge priority={task.priority || 'medium'} />
              {task.erpnext_id && (
                <span className="text-slate-muted font-mono text-sm">{task.erpnext_id}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button
            onClick={() => {
              if (editMode) {
                setEditMode(false);
                setAssignedEmployee(null);
                setAssigneeDirty(false);
                setSaveError(null);
                return;
              }
              setEditMode(true);
              setSaveError(null);
            }}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
              editMode
                ? 'bg-teal-electric text-slate-950 border-teal-electric'
                : 'border-slate-border text-foreground hover:border-teal-electric/50'
            )}
          >
            <Edit className="w-4 h-4" />
            {editMode ? 'Cancel' : 'Edit'}
          </Button>
        </div>
      </div>

      {/* Progress & Project Banner */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-8">
          <ProgressRing percent={progress} size={100} strokeWidth={10} />
          <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-6">
            {task.project_name && (
              <div>
                <p className="text-slate-muted text-sm mb-1 flex items-center gap-1">
                  <FolderKanban className="w-3 h-3" />
                  Project
                </p>
                <Link
                  href={`/projects/${task.project_id}`}
                  className="text-foreground font-semibold hover:text-teal-electric transition-colors"
                >
                  {task.project_name}
                </Link>
              </div>
            )}
            <div>
              <p className="text-slate-muted text-sm mb-1">Expected Start</p>
              <p className="text-foreground font-semibold">{formatDate(task.exp_start_date)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-1">Expected End</p>
              <p className={cn('font-semibold', isOverdue ? 'text-red-400' : 'text-foreground')}>
                {formatDate(task.exp_end_date)}
                {isOverdue && <span className="ml-2 text-xs">(Overdue)</span>}
              </p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-1">Task Type</p>
              <p className="text-foreground font-semibold">{task.task_type || '-'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Details Card */}
        <div className="lg:col-span-2 bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            Task Details
          </h3>

          {task.description && (
            <div className="bg-slate-elevated rounded-lg p-4">
              <p className="text-slate-muted text-sm mb-2">Description</p>
              <p className="text-foreground whitespace-pre-wrap">{task.description}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <InfoRow
              label="Assigned To"
              icon={User}
              value={
                editMode ? (
                  <EmployeeSearch
                    employees={employees.map((e: any) => ({
                      id: e.id,
                      name: e.name,
                      email: e.email,
                      department: e.department,
                    }))}
                    value={assignedEmployee || (task.assigned_employee_name ? { id: task.assigned_to_id, name: task.assigned_employee_name } : null)}
                    onSelect={(emp) => {
                      setAssignedEmployee(emp);
                      setAssigneeDirty(true);
                    }}
                    placeholder="Select employee..."
                  />
                ) : (
                  task.assigned_employee_name || task.assigned_to?.split('@')[0] || 'Unassigned'
                )
              }
            />
            <InfoRow
              label="Completed By"
              icon={CheckCircle2}
              value={task.completed_by_employee_name || task.completed_by?.split('@')[0] || '-'}
            />
            <InfoRow
              label="Actual Start"
              icon={Calendar}
              value={formatDate(task.act_start_date)}
            />
            <InfoRow
              label="Actual End"
              icon={Calendar}
              value={formatDate(task.act_end_date)}
            />
            <InfoRow
              label="Completed On"
              icon={CheckCircle2}
              value={formatDate(task.completed_on)}
            />
            <InfoRow
              label="Review Date"
              icon={Calendar}
              value={formatDate(task.review_date)}
            />
          </div>

          {editMode && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-border">
              {saveError ? (
                <span className="text-sm text-rose-400">{saveError}</span>
              ) : (
                <span />
              )}
              <Button
                onClick={async () => {
                  setSaveError(null);
                  if (!assigneeDirty) {
                    setEditMode(false);
                    return;
                  }
                  const selectedEmployee = assignedEmployee
                    ? employees.find((emp: any) => emp.id === assignedEmployee.id)
                    : null;
                  const assignedTo = assignedEmployee
                    ? selectedEmployee?.email || selectedEmployee?.name || assignedEmployee.name
                    : '';

                  setIsSaving(true);
                  try {
                    await updateTask(id, { assigned_to: assignedTo });
                    setAssigneeDirty(false);
                    setEditMode(false);
                    await mutate();
                  } catch (err) {
                    setSaveError(err instanceof Error ? err.message : 'Failed to update task');
                  } finally {
                    setIsSaving(false);
                  }
                }}
                className={cn(
                  'inline-flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-colors',
                  isSaving
                    ? 'bg-slate-elevated text-slate-muted border border-slate-border cursor-not-allowed'
                    : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
                )}
                disabled={isSaving}
              >
                <Save className="w-4 h-4" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          )}
        </div>

        {/* Right Sidebar */}
        <div className="space-y-4">
          {/* Time Tracking Card */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <Timer className="w-4 h-4 text-teal-electric" />
              Time Tracking
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-muted text-sm">Expected</span>
                <span className="text-foreground font-semibold">{task.expected_time || 0}h</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-muted text-sm">Actual</span>
                <span className={cn(
                  'font-semibold',
                  (task.actual_time || 0) > (task.expected_time || 0) ? 'text-red-400' : 'text-foreground'
                )}>
                  {task.actual_time || 0}h
                </span>
              </div>
              <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full',
                    (task.actual_time || 0) > (task.expected_time || 0) ? 'bg-red-500' : 'bg-teal-electric'
                  )}
                  style={{ width: `${Math.min(((task.actual_time || 0) / Math.max(task.expected_time || 1, 1)) * 100, 100)}%` }}
                />
              </div>
              {(task.actual_time || 0) > (task.expected_time || 0) && (
                <p className="text-red-400 text-xs">
                  Over by {((task.actual_time || 0) - (task.expected_time || 0)).toFixed(1)}h
                </p>
              )}
            </div>
          </div>

          {/* Costing Card */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-teal-electric" />
              Costing
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-muted text-sm">Costing</span>
                <span className="text-foreground font-semibold">
                  {new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 0 }).format(task.total_costing_amount || 0)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-muted text-sm">Billing</span>
                <span className="text-green-400 font-semibold">
                  {new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 0 }).format(task.total_billing_amount || 0)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-muted text-sm">Expense Claims</span>
                <span className="text-foreground font-semibold">
                  {new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 0 }).format(task.total_expense_claim || 0)}
                </span>
              </div>
            </div>
          </div>

          {/* Dependencies Card */}
          {task.depends_on?.length > 0 && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
              <h3 className="text-foreground font-semibold flex items-center gap-2">
                <Link2 className="w-4 h-4 text-teal-electric" />
                Dependencies ({task.depends_on.length})
              </h3>
              <div className="space-y-2">
                {task.depends_on.map((dep: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between p-2 bg-slate-elevated rounded-lg">
                    <span className="text-foreground text-sm truncate">{dep.subject || `Task #${dep.dependent_task_id}`}</span>
                    {dep.dependent_task_id && (
                      <Link
                        href={`/projects/tasks/${dep.dependent_task_id}`}
                        className="text-teal-electric text-xs hover:underline"
                      >
                        View
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metadata Card */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
            <h3 className="text-foreground font-semibold text-sm">Metadata</h3>
            <div className="text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-muted">Department</span>
                <span className="text-foreground">{task.department || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-muted">Company</span>
                <span className="text-foreground">{task.company || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-muted">Created</span>
                <span className="text-foreground">{formatDate(task.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-muted">Updated</span>
                <span className="text-foreground">{formatDate(task.updated_at)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
