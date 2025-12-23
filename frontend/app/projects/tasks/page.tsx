'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ListTodo,
  Plus,
  AlertTriangle,
  Tag,
  Clock,
  User,
  CheckCircle,
  XCircle,
  Target,
  ChevronRight,
  Search,
  Calendar,
  FolderKanban,
} from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { SelectableStatCard } from '@/components/StatCard';
import { useAllTasks, useProjects } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { useEmployeeOptions } from '@/hooks/usePickers';
import { Button, FilterCard, FilterInput, FilterSelect, StatusPill } from '@/components/ui';


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

  return (
    <StatusPill
      label={labels[status] || formatStatusLabel(status)}
      tone={tones[status] || 'default'}
      className="border border-current/30"
    />
  );
}

export default function TasksPage() {
  const router = useRouter();
  const [filters, setFilters] = usePersistentState<{
    page: number;
    pageSize: number;
    priority: string;
    status: string;
    projectId: string;
    assignedTo: string;
    taskType: string;
    startDate: string;
    endDate: string;
    search: string;
    overdueOnly: boolean;
    quickFilter: string;
  }>('projects.tasks.filters', {
    page: 1,
    pageSize: 20,
    priority: '',
    status: '',
    projectId: '',
    assignedTo: '',
    taskType: '',
    startDate: '',
    endDate: '',
    search: '',
    overdueOnly: false,
    quickFilter: '',
  });
  const { page, pageSize, priority, status, projectId, assignedTo, taskType, startDate, endDate, search, overdueOnly, quickFilter } = filters;
  const offset = (page - 1) * pageSize;

  // Fetch employee options for filter
  const { employees } = useEmployeeOptions();

  // Fetch projects for filter
  const { data: projectsData } = useProjects({ limit: 500 });
  const projects = projectsData?.data || [];

  const { data, isLoading, error, mutate } = useAllTasks({
    priority: priority || undefined,
    status: status || undefined,
    project_id: projectId ? Number(projectId) : undefined,
    assigned_to: assignedTo || undefined,
    task_type: taskType || undefined,
    search: search || undefined,
    overdue_only: overdueOnly || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit: pageSize,
    offset,
  });

  const tasks = useMemo(() => data?.data ?? [], [data?.data]);
  const total = data?.total || 0;

  // Calculate stats
  const stats = useMemo(() => {
    if (!data?.data) return { total: 0, open: 0, completed: 0, overdue: 0 };
    return {
      total: data.total || 0,
      open: tasks.filter((t: any) => t.status === 'open' || t.status === 'working').length,
      completed: tasks.filter((t: any) => t.status === 'completed').length,
      overdue: tasks.filter((t: any) => t.is_overdue).length,
    };
  }, [data, tasks]);

  const handleQuickFilter = (filter: string) => {
    if (quickFilter === filter) {
      setFilters((prev) => ({ ...prev, quickFilter: '', status: '', overdueOnly: false, page: 1 }));
    } else {
      setFilters((prev) => ({ ...prev, quickFilter: filter, page: 1 }));
      if (filter === 'open') {
        setFilters((prev) => ({ ...prev, status: 'open', overdueOnly: false }));
      } else if (filter === 'overdue') {
        setFilters((prev) => ({ ...prev, overdueOnly: true, status: '' }));
      } else if (filter === 'completed') {
        setFilters((prev) => ({ ...prev, status: 'completed', overdueOnly: false }));
      }
    }
  };

  const clearFilters = () => {
    setFilters({
      ...filters,
      priority: '',
      status: '',
      projectId: '',
      assignedTo: '',
      taskType: '',
      startDate: '',
      endDate: '',
      search: '',
      overdueOnly: false,
      quickFilter: '',
      page: 1,
    });
  };

  const hasActiveFilters = priority || status || projectId || assignedTo || taskType || startDate || endDate || search || overdueOnly;

  const columns = [
    {
      key: 'task',
      header: 'Task',
      render: (item: any) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-foreground font-semibold">{item.erpnext_id || `#${item.id}`}</span>
            {item.is_overdue && (
              <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-medium">
                OVERDUE
              </span>
            )}
          </div>
          <span className="text-slate-200 text-sm line-clamp-1">{item.subject || '-'}</span>
          {item.project_name && (
            <span className="text-slate-muted text-xs flex items-center gap-1">
              <FolderKanban className="w-3 h-3" />
              {item.project_name}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: any) => <PriorityBadge priority={item.priority || 'medium'} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <StatusBadge status={item.status || 'open'} />,
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (item: any) => {
        const progress = item.progress || 0;
        return (
          <div className="flex items-center gap-2">
            <div className="w-16 h-2 bg-slate-elevated rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  progress >= 100 ? 'bg-emerald-500' : progress >= 50 ? 'bg-teal-electric' : 'bg-blue-500'
                )}
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <span className="text-sm text-slate-muted">{progress}%</span>
          </div>
        );
      },
    },
    {
      key: 'assigned',
      header: 'Assigned',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <User className="w-3 h-3 text-slate-muted" />
          <span className={cn('text-sm', item.assigned_to || item.assigned_employee_name ? 'text-slate-200' : 'text-amber-400')}>
            {item.assigned_employee_name || item.assigned_to?.split('@')[0] || 'Unassigned'}
          </span>
        </div>
      ),
    },
    {
      key: 'due_date',
      header: 'Due Date',
      render: (item: any) => {
        const isOverdue = item.is_overdue || (item.exp_end_date && new Date(item.exp_end_date) < new Date() && item.status !== 'completed');
        return (
          <div className={cn('flex items-center gap-1 text-sm', isOverdue ? 'text-rose-400' : 'text-slate-200')}>
            <Calendar className="w-3 h-3" />
            {formatDate(item.exp_end_date)}
          </div>
        );
      },
    },
  ];

  if (isLoading) {
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
          <div className="w-10 h-10 rounded-full bg-purple-500/10 border border-purple-500/30 flex items-center justify-center">
            <ListTodo className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Tasks</h1>
            <p className="text-slate-muted text-sm">Browse and manage all project tasks</p>
          </div>
        </div>
        <Link
          href="/projects/tasks/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New task
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SelectableStatCard
          title="Total"
          value={stats.total}
          icon={ListTodo}
        />
        <SelectableStatCard
          title="Open"
          value={stats.open}
          icon={Target}
          variant="info"
          onClick={() => handleQuickFilter('open')}
          active={quickFilter === 'open'}
        />
        <SelectableStatCard
          title="Completed"
          value={stats.completed}
          icon={CheckCircle}
          variant="success"
          onClick={() => handleQuickFilter('completed')}
          active={quickFilter === 'completed'}
        />
        <SelectableStatCard
          title="Overdue"
          value={stats.overdue}
          icon={AlertTriangle}
          variant="danger"
          onClick={() => handleQuickFilter('overdue')}
          active={quickFilter === 'overdue'}
        />
      </div>

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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <FilterInput
              value={search}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, search: e.target.value, page: 1 }));
              }}
              placeholder="Search tasks..."
              className="w-full pl-10 pr-4 focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <FilterSelect
            value={projectId}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, projectId: e.target.value, page: 1 }));
            }}
            className="focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Projects</option>
            {projects.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.project_name}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            value={assignedTo}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, assignedTo: e.target.value, page: 1 }));
            }}
            className="focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Assignees</option>
            {employees.map((emp: any) => (
              <option key={emp.id} value={emp.email || emp.name}>
                {emp.name}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            value={priority}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, priority: e.target.value, quickFilter: '', page: 1 }));
            }}
            className="focus:ring-2 focus:ring-teal-electric/50"
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
            className="focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="working">Working</option>
            <option value="pending_review">Pending Review</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </FilterSelect>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-slate-muted text-xs">Date range:</span>
          <div className="flex items-center gap-2">
            <FilterInput
              type="date"
              value={startDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, startDate: e.target.value, page: 1 }));
              }}
              className="px-3 py-1.5 focus:ring-2 focus:ring-teal-electric/50"
            />
            <ChevronRight className="w-4 h-4 text-slate-muted" />
            <FilterInput
              type="date"
              value={endDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, endDate: e.target.value, page: 1 }));
              }}
              className="px-3 py-1.5 focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
        </div>
      </FilterCard>

      {/* Results Info */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-muted">
          Showing {tasks.length} of {total} tasks
        </span>
        {hasActiveFilters && (
          <div className="flex items-center gap-2 flex-wrap">
            {priority && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Priority: {priority}
              </span>
            )}
            {status && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Status: {status}
              </span>
            )}
            {projectId && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Project: {projects.find((p: any) => p.id === Number(projectId))?.project_name || projectId}
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
          onRowClick={(item) => router.push(`/projects/tasks/${(item as any).id}`)}
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
