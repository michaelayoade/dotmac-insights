'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Calendar,
  Play,
  Pause,
  Plus,
  Trash2,
  Edit2,
  Clock,
  Zap,
} from 'lucide-react';
import { adminApi, type SyncSchedule, type AvailableTask, type ScheduleCreatePayload } from '@/lib/api/domains/admin';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function StatusBadge({ status, isEnabled }: { status?: string | null; isEnabled: boolean }) {
  if (!isEnabled) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-slate-500/10 border border-slate-500/30 text-slate-400">
        <Pause className="w-3 h-3" />
        Disabled
      </span>
    );
  }

  const config: Record<string, { bg: string; border: string; text: string; label: string }> = {
    success: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Success' },
    running: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', label: 'Running' },
    failed: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', label: 'Failed' },
    pending: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', label: 'Pending' },
  };
  const c = config[status || 'pending'] || config.pending;
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', c.bg, c.border, c.text)}>
      {status === 'success' && <CheckCircle2 className="w-3 h-3" />}
      {status === 'running' && <RefreshCw className="w-3 h-3 animate-spin" />}
      {status === 'failed' && <XCircle className="w-3 h-3" />}
      {(!status || status === 'pending') && <Clock className="w-3 h-3" />}
      {c.label}
    </span>
  );
}

function ScheduleRow({
  schedule,
  onToggle,
  onRun,
  onEdit,
  onDelete,
}: {
  schedule: SyncSchedule;
  onToggle: (id: number, enabled: boolean) => void;
  onRun: (id: number) => void;
  onEdit: (schedule: SyncSchedule) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="px-5 py-4 flex items-center gap-4 hover:bg-slate-elevated/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-foreground font-medium">{schedule.name}</span>
          {schedule.is_system && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/30">
              System
            </span>
          )}
        </div>
        {schedule.description && (
          <p className="text-sm text-slate-muted truncate">{schedule.description}</p>
        )}
        <div className="flex items-center gap-4 mt-1 text-xs text-slate-muted">
          <span className="font-mono">{schedule.cron_expression}</span>
          <span>{schedule.task_name.split('.').pop()}</span>
          {schedule.run_count > 0 && <span>Runs: {schedule.run_count}</span>}
          {schedule.last_run_at && (
            <span>Last: {formatRelativeTime(new Date(schedule.last_run_at))}</span>
          )}
        </div>
      </div>
      <StatusBadge status={schedule.last_run_status} isEnabled={schedule.is_enabled} />
      <div className="flex items-center gap-1">
        <Button
          onClick={() => onRun(schedule.id)}
          className="p-2 text-slate-muted hover:text-teal-400 hover:bg-teal-500/10"
          title="Run now"
        >
          <Zap className="w-4 h-4" />
        </Button>
        <Button
          onClick={() => onToggle(schedule.id, !schedule.is_enabled)}
          className={cn(
            'p-2',
            schedule.is_enabled
              ? 'text-emerald-400 hover:bg-emerald-500/10'
              : 'text-slate-muted hover:bg-slate-elevated'
          )}
          title={schedule.is_enabled ? 'Disable' : 'Enable'}
        >
          {schedule.is_enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
        {!schedule.is_system && (
          <>
            <Button
              onClick={() => onEdit(schedule)}
              className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated"
              title="Edit"
            >
              <Edit2 className="w-4 h-4" />
            </Button>
            <Button
              onClick={() => onDelete(schedule.id)}
              className="p-2 text-slate-muted hover:text-rose-400 hover:bg-rose-500/10"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function CreateEditModal({
  schedule,
  tasks,
  onClose,
  onSave,
}: {
  schedule: SyncSchedule | null;
  tasks: AvailableTask[];
  onClose: () => void;
  onSave: (data: ScheduleCreatePayload) => void;
}) {
  const [name, setName] = useState(schedule?.name || '');
  const [description, setDescription] = useState(schedule?.description || '');
  const [taskName, setTaskName] = useState(schedule?.task_name || tasks[0]?.name || '');
  const [cronExpression, setCronExpression] = useState(schedule?.cron_expression || '0 */4 * * *');
  const [isEnabled, setIsEnabled] = useState(schedule?.is_enabled ?? true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      name,
      description: description || undefined,
      task_name: taskName,
      cron_expression: cronExpression,
      is_enabled: isEnabled,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-card border border-slate-border rounded-xl max-w-lg w-full">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">
            {schedule ? 'Edit Schedule' : 'Create Schedule'}
          </h3>
          <Button onClick={onClose} className="text-slate-muted hover:text-foreground">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="text-xs text-slate-muted uppercase mb-1 block">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
              placeholder="e.g., Hourly Customer Sync"
            />
          </div>
          <div>
            <label className="text-xs text-slate-muted uppercase mb-1 block">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
              placeholder="Optional description"
            />
          </div>
          <div>
            <label className="text-xs text-slate-muted uppercase mb-1 block">Task</label>
            <select
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground"
            >
              {tasks.map((task) => (
                <option key={task.name} value={task.name}>
                  {task.description}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-muted uppercase mb-1 block">Cron Expression</label>
            <input
              type="text"
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              required
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground font-mono"
              placeholder="0 */4 * * *"
            />
            <p className="text-xs text-slate-muted mt-1">
              Format: minute hour day month weekday (e.g., &quot;0 */4 * * *&quot; = every 4 hours)
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_enabled"
              checked={isEnabled}
              onChange={(e) => setIsEnabled(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="is_enabled" className="text-foreground text-sm">
              Enabled
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-elevated text-foreground hover:bg-slate-border rounded-lg"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="px-4 py-2 bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30 rounded-lg"
            >
              {schedule ? 'Update' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function SchedulesPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope(['sync:read', 'admin:read']);
  const canFetch = !authLoading && !missingScope;

  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<SyncSchedule | null>(null);

  const {
    data: schedulesData,
    isLoading,
    error,
    mutate: refetch,
  } = useSWR(
    canFetch ? 'sync-schedules' : null,
    () => adminApi.getSchedules()
  );

  const { data: tasks } = useSWR(
    canFetch ? 'available-tasks' : null,
    () => adminApi.getAvailableTasks()
  );

  const handleToggle = async (id: number, enabled: boolean) => {
    try {
      await adminApi.updateSchedule(id, { is_enabled: enabled });
      refetch();
    } catch (err) {
      console.error('Failed to toggle schedule:', err);
    }
  };

  const handleRun = async (id: number) => {
    try {
      const result = await adminApi.runScheduleNow(id);
      alert(`Task triggered: ${result.task_id || 'started'}`);
      refetch();
    } catch (err) {
      console.error('Failed to run schedule:', err);
      alert('Failed to run schedule');
    }
  };

  const handleEdit = (schedule: SyncSchedule) => {
    setEditingSchedule(schedule);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return;
    try {
      await adminApi.deleteSchedule(id);
      refetch();
    } catch (err) {
      console.error('Failed to delete schedule:', err);
    }
  };

  const handleSave = async (data: ScheduleCreatePayload) => {
    try {
      if (editingSchedule) {
        await adminApi.updateSchedule(editingSchedule.id, data);
      } else {
        await adminApi.createSchedule(data);
      }
      setShowModal(false);
      setEditingSchedule(null);
      refetch();
    } catch (err) {
      console.error('Failed to save schedule:', err);
      alert('Failed to save schedule');
    }
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need sync:read or admin:read permission to view this page."
        backHref="/admin/sync"
        backLabel="Back to Sync Dashboard"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-amber-500/20 to-orange-500/20 rounded-xl">
            <Calendar className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Sync Schedules</h1>
            <p className="text-slate-muted text-sm">
              Manage automated sync schedules
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => refetch()}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </Button>
          <Button
            onClick={() => {
              setEditingSchedule(null);
              setShowModal(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Schedule
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load schedules</p>
            <p className="text-rose-300/70 text-sm">{error.message}</p>
          </div>
        </div>
      )}

      {/* Schedules List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <h3 className="font-semibold text-foreground">
            Schedules ({schedulesData?.total || 0})
          </h3>
          <p className="text-xs text-slate-muted">
            System schedules cannot be edited or deleted
          </p>
        </div>

        {isLoading ? (
          <div className="p-8 flex justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
          </div>
        ) : schedulesData && schedulesData.items.length > 0 ? (
          <div className="divide-y divide-slate-border">
            {schedulesData.items.map((schedule) => (
              <ScheduleRow
                key={schedule.id}
                schedule={schedule}
                onToggle={handleToggle}
                onRun={handleRun}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <Calendar className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-foreground font-medium">No schedules configured</p>
            <p className="text-slate-muted text-sm mb-4">Create a schedule to automate sync operations</p>
            <Button
              onClick={() => {
                setEditingSchedule(null);
                setShowModal(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30"
            >
              <Plus className="w-4 h-4" />
              Create Schedule
            </Button>
          </div>
        )}
      </div>

      {/* Cron Help */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="font-semibold text-foreground mb-3">Cron Expression Help</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="font-mono text-foreground">*/15 * * * *</p>
            <p className="text-slate-muted text-xs mt-1">Every 15 minutes</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="font-mono text-foreground">0 */4 * * *</p>
            <p className="text-slate-muted text-xs mt-1">Every 4 hours</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="font-mono text-foreground">0 0 * * *</p>
            <p className="text-slate-muted text-xs mt-1">Daily at midnight</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="font-mono text-foreground">0 6 * * 1-5</p>
            <p className="text-slate-muted text-xs mt-1">Weekdays at 6am</p>
          </div>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && tasks && (
        <CreateEditModal
          schedule={editingSchedule}
          tasks={tasks}
          onClose={() => {
            setShowModal(false);
            setEditingSchedule(null);
          }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
