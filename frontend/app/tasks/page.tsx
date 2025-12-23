'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckSquare,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  CalendarClock,
  Inbox,
  Tag,
  ChevronRight,
  ExternalLink,
  MoreHorizontal,
} from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { SelectableStatCard } from '@/components/StatCard';
import { useMyWorkflowTasks, useMyWorkflowTasksSummary, useWorkflowTaskMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { formatDate, formatRelativeTime } from '@/lib/formatters';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay } from '@/components/insights/shared';
import { Button, FilterCard, FilterSelect, LoadingState, StatusPill } from '@/components/ui';
import type { WorkflowTask } from '@/lib/api/domains/workflow-tasks';

// =============================================================================
// COMPONENTS
// =============================================================================

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    urgent: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    low: 'bg-slate-500/10 text-foreground-secondary border-slate-500/30',
  };
  const color = colors[priority] || colors.medium;

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
      <Tag className="w-3 h-3" />
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tones: Record<string, 'info' | 'warning' | 'success' | 'danger' | 'default'> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'default',
    expired: 'danger',
  };

  const labels: Record<string, string> = {
    pending: 'Pending',
    in_progress: 'In Progress',
    completed: 'Completed',
    cancelled: 'Cancelled',
    expired: 'Expired',
  };

  return (
    <StatusPill
      label={labels[status] || status}
      tone={tones[status] || 'default'}
    />
  );
}

function ModuleBadge({ module }: { module: string }) {
  const colors: Record<string, string> = {
    accounting: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
    support: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    expenses: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
    performance: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    inbox: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    crm: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
  };
  const color = colors[module] || 'bg-slate-500/10 text-slate-400 border-slate-500/30';

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border capitalize', color)}>
      {module}
    </span>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function TasksPage() {
  const router = useRouter();
  const [filters, setFilters] = usePersistentState<{
    page: number;
    pageSize: number;
    priority: string;
    status: string;
    module: string;
    quickFilter: string;
  }>('workflow.tasks.filters', {
    page: 1,
    pageSize: 20,
    priority: '',
    status: '',
    module: '',
    quickFilter: '',
  });

  const { page, pageSize, priority, status, module, quickFilter } = filters;
  const offset = (page - 1) * pageSize;

  // Hooks
  const { data, isLoading, error, mutate } = useMyWorkflowTasks({
    status: status || undefined,
    module: module || undefined,
    priority: priority || undefined,
    overdue_only: quickFilter === 'overdue' ? true : undefined,
    limit: pageSize,
    offset,
  });

  const { data: summaryData } = useMyWorkflowTasksSummary();
  const { completeTask } = useWorkflowTaskMutations();

  const tasks = data?.items || [];
  const total = data?.total || 0;

  const pending = summaryData?.pending ?? 0;
  const overdue = summaryData?.overdue ?? 0;
  const dueToday = summaryData?.due_today ?? 0;
  const completedToday = summaryData?.completed_today ?? 0;

  // Handlers
  const handleQuickFilter = (filter: string) => {
    if (quickFilter === filter) {
      setFilters((prev) => ({ ...prev, quickFilter: '', status: '', page: 1 }));
    } else {
      setFilters((prev) => ({ ...prev, quickFilter: filter, page: 1 }));
      if (filter === 'pending') {
        setFilters((prev) => ({ ...prev, status: 'pending' }));
      } else if (filter === 'overdue') {
        setFilters((prev) => ({ ...prev, status: '' })); // overdue_only handled by params
      } else if (filter === 'completed') {
        setFilters((prev) => ({ ...prev, status: 'completed' }));
      }
    }
  };

  const clearFilters = () => {
    setFilters({
      ...filters,
      priority: '',
      status: '',
      module: '',
      quickFilter: '',
      page: 1,
    });
  };

  const handleComplete = async (taskId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await completeTask(taskId);
      mutate();
    } catch (err) {
      console.error('Failed to complete task:', err);
    }
  };

  const handleNavigate = (actionUrl: string | undefined, e: React.MouseEvent) => {
    e.stopPropagation();
    if (actionUrl) {
      router.push(actionUrl);
    }
  };

  const hasActiveFilters = priority || status || module;

  // Table columns
  const columns = [
    {
      key: 'task',
      header: 'Task',
      render: (item: WorkflowTask) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-foreground font-semibold line-clamp-1">{item.title}</span>
            {item.is_overdue && (
              <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-medium">
                OVERDUE
              </span>
            )}
          </div>
          {item.description && (
            <span className="text-slate-muted text-xs line-clamp-1">{item.description}</span>
          )}
        </div>
      ),
    },
    {
      key: 'module',
      header: 'Module',
      render: (item: WorkflowTask) => <ModuleBadge module={item.module} />,
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: WorkflowTask) => <PriorityBadge priority={item.priority} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: WorkflowTask) => <StatusBadge status={item.status} />,
    },
    {
      key: 'due',
      header: 'Due',
      render: (item: WorkflowTask) => {
        if (!item.due_at) return <span className="text-slate-muted text-sm">-</span>;
        const isOverdue = new Date(item.due_at) < new Date();
        return (
          <div className={cn('flex items-center gap-1 text-sm', isOverdue ? 'text-rose-400' : 'text-slate-200')}>
            <Clock className="w-3 h-3" />
            {formatDate(item.due_at)}
          </div>
        );
      },
    },
    {
      key: 'assigned',
      header: 'Assigned',
      render: (item: WorkflowTask) => (
        <div className="text-slate-200 text-sm">
          <div>{formatDate(item.assigned_at)}</div>
          <div className="text-xs text-slate-muted">{formatRelativeTime(item.assigned_at)}</div>
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: WorkflowTask) => (
        <div className="flex items-center gap-2">
          {item.status === 'pending' && (
            <button
              onClick={(e) => handleComplete(item.id, e)}
              className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              title="Mark as completed"
            >
              <CheckCircle className="w-4 h-4" />
            </button>
          )}
          {item.action_url && (
            <button
              onClick={(e) => handleNavigate(item.action_url, e)}
              className="p-1.5 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
              title="Go to source"
            >
              <ExternalLink className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load tasks."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center">
            <CheckSquare className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">My Tasks</h1>
            <p className="text-slate-muted text-sm">Unified view of tasks across all modules</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      {summaryData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SelectableStatCard
            title="Pending"
            value={pending}
            icon={Inbox}
            variant="info"
            onClick={() => handleQuickFilter('pending')}
            active={quickFilter === 'pending'}
          />
          <SelectableStatCard
            title="Overdue"
            value={overdue}
            icon={AlertTriangle}
            variant="danger"
            onClick={() => handleQuickFilter('overdue')}
            active={quickFilter === 'overdue'}
          />
          <SelectableStatCard
            title="Due Today"
            value={dueToday}
            icon={CalendarClock}
            variant="warning"
          />
          <SelectableStatCard
            title="Completed Today"
            value={completedToday}
            icon={CheckCircle}
            variant="success"
            onClick={() => handleQuickFilter('completed')}
            active={quickFilter === 'completed'}
          />
        </div>
      )}

      {/* Module breakdown */}
      {summaryData?.by_module && Object.keys(summaryData.by_module).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(summaryData.by_module).map(([mod, count]) => (
            <button
              key={mod}
              onClick={() => {
                if (module === mod) {
                  setFilters((prev) => ({ ...prev, module: '', page: 1 }));
                } else {
                  setFilters((prev) => ({ ...prev, module: mod, page: 1 }));
                }
              }}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm transition-colors',
                module === mod
                  ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                  : 'bg-slate-elevated text-slate-muted hover:bg-slate-700'
              )}
            >
              <span className="capitalize">{mod}</span>
              <span className="ml-2 px-1.5 py-0.5 rounded bg-slate-800 text-xs">{count}</span>
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <FilterCard
        actions={hasActiveFilters && (
          <Button
            onClick={clearFilters}
            className="text-slate-muted text-sm hover:text-foreground transition-colors flex items-center gap-1"
          >
            <XCircle className="w-3 h-3" />
            Clear all
          </Button>
        )}
        contentClassName="space-y-4"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <FilterSelect
            value={module}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, module: e.target.value, page: 1 }));
            }}
          >
            <option value="">All Modules</option>
            <option value="accounting">Accounting</option>
            <option value="support">Support</option>
            <option value="expenses">Expenses</option>
            <option value="performance">Performance</option>
            <option value="inbox">Inbox</option>
            <option value="crm">CRM</option>
          </FilterSelect>
          <FilterSelect
            value={priority}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, priority: e.target.value, quickFilter: '', page: 1 }));
            }}
          >
            <option value="">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </FilterSelect>
          <FilterSelect
            value={status}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, status: e.target.value, quickFilter: '', page: 1 }));
            }}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="expired">Expired</option>
          </FilterSelect>
        </div>
      </FilterCard>

      {/* Results Info */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-muted">
          Showing {tasks.length} of {total} tasks
        </span>
        {hasActiveFilters && (
          <div className="flex items-center gap-2 flex-wrap">
            {module && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted capitalize">
                Module: {module}
              </span>
            )}
            {priority && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted capitalize">
                Priority: {priority}
              </span>
            )}
            {status && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted capitalize">
                Status: {status}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Data Table */}
      {error ? (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load tasks. Please try again.</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={tasks}
          keyField="id"
          loading={isLoading}
          emptyMessage="No tasks found matching your filters"
          onRowClick={(item) => {
            const task = item as WorkflowTask;
            if (task.action_url) {
              router.push(task.action_url);
            }
          }}
        />
      )}

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={offset}
          onPageChange={(newOffset) =>
            setFilters((prev) => ({ ...prev, page: Math.floor(newOffset / pageSize) + 1 }))
          }
          onLimitChange={(newLimit) => {
            setFilters((prev) => ({ ...prev, pageSize: newLimit, page: 1 }));
          }}
        />
      )}
    </div>
  );
}
