'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertTriangle,
  ArrowLeft,
  ClipboardList,
  Calendar,
  Tag,
  Users,
  FileText,
  ListTodo,
  CheckCircle2,
  Clock,
  DollarSign,
  TrendingUp,
  Edit,
  Plus,
  ChevronRight,
  Target,
  Building2,
  User,
  Briefcase,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { useProjectDetail, useProjectTasks } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency: 'NGN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

// Progress ring component
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
        <span className="text-lg font-bold text-white">{percent}%</span>
      </div>
    </div>
  );
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    open: { icon: ClipboardList, color: 'text-blue-400 bg-blue-500/10 border-blue-500/30', label: 'Open' },
    completed: { icon: CheckCircle2, color: 'text-green-400 bg-green-500/10 border-green-500/30', label: 'Completed' },
    on_hold: { icon: Clock, color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', label: 'On Hold' },
    cancelled: { icon: AlertTriangle, color: 'text-red-400 bg-red-500/10 border-red-500/30', label: 'Cancelled' },
  };
  const { icon: Icon, color, label } = config[status] || config.open;
  return (
    <span className={cn('px-3 py-1.5 rounded-full text-sm font-medium border inline-flex items-center gap-2', color)}>
      <Icon className="w-4 h-4" />
      {label}
    </span>
  );
}

// Priority badge
function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    high: 'text-red-400 bg-red-500/10 border-red-500/30',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    low: 'text-slate-300 bg-slate-500/10 border-slate-500/30',
  };
  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', colors[priority] || colors.medium)}>
      <Tag className="w-3 h-3" />
      {priority}
    </span>
  );
}

// KPI Card
function KPICard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric' }: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
}) {
  return (
    <div className="bg-slate-elevated rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={cn('w-4 h-4', colorClass)} />
        <span className="text-slate-muted text-sm">{title}</span>
      </div>
      <p className={cn('text-xl font-bold', colorClass)}>{value}</p>
      {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
    </div>
  );
}

// Task row component
function TaskRow({ task }: { task: any }) {
  const statusColors: Record<string, string> = {
    open: 'bg-blue-500',
    working: 'bg-amber-500',
    completed: 'bg-green-500',
    cancelled: 'bg-red-500',
    pending_review: 'bg-purple-500',
  };
  const priorityColors: Record<string, string> = {
    high: 'text-red-400',
    medium: 'text-amber-400',
    low: 'text-slate-400',
  };

  const isOverdue = task.expected_end_date && new Date(task.expected_end_date) < new Date() && task.status !== 'completed';

  return (
    <div className={cn(
      'flex items-center gap-4 p-3 rounded-lg border transition-colors hover:bg-slate-elevated/50',
      isOverdue ? 'border-red-500/30 bg-red-500/5' : 'border-slate-border'
    )}>
      <div className={cn('w-2 h-2 rounded-full', statusColors[task.status] || 'bg-slate-500')} />
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium truncate">{task.subject}</p>
        <div className="flex items-center gap-3 text-xs text-slate-muted mt-1">
          {task.assigned_to && (
            <span className="flex items-center gap-1">
              <User className="w-3 h-3" />
              {task.assigned_to.split('@')[0]}
            </span>
          )}
          {task.expected_end_date && (
            <span className={cn('flex items-center gap-1', isOverdue && 'text-red-400')}>
              <Calendar className="w-3 h-3" />
              {formatDate(task.expected_end_date)}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={cn('text-xs font-medium capitalize', priorityColors[task.priority] || 'text-slate-400')}>
          {task.priority}
        </span>
        <span className="text-xs text-slate-muted capitalize px-2 py-0.5 bg-slate-elevated rounded">
          {task.status?.replace('_', ' ')}
        </span>
      </div>
    </div>
  );
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const isValidId = Number.isFinite(id);

  const { data, isLoading, error, mutate } = useProjectDetail(isValidId ? id : null);
  const { data: tasksData, isLoading: tasksLoading } = useProjectTasks(isValidId ? id : null);

  const [activeTab, setActiveTab] = useState<'overview' | 'tasks' | 'team' | 'financials'>('overview');

  if (!isValidId) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Invalid project ID.</p>
        <button
          onClick={() => router.push('/projects')}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to projects
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-24 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
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
        <p className="text-red-400">Failed to load project</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const tasks = tasksData?.data || [];
  const taskStats = {
    total: tasks.length,
    open: tasks.filter((t: any) => t.status === 'open').length,
    completed: tasks.filter((t: any) => t.status === 'completed').length,
    overdue: tasks.filter((t: any) => t.expected_end_date && new Date(t.expected_end_date) < new Date() && t.status !== 'completed').length,
  };

  const isOverdue = data.expected_end_date && new Date(data.expected_end_date) < new Date() && data.status === 'open';
  const daysRemaining = data.expected_end_date
    ? Math.ceil((new Date(data.expected_end_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link
            href="/projects"
            className="mt-1 inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-white">{data.project_name}</h1>
              <StatusBadge status={data.status} />
              <PriorityBadge priority={data.priority || 'medium'} />
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-muted">
              {data.erpnext_id && (
                <span className="font-mono">{data.erpnext_id}</span>
              )}
              {data.department && (
                <span className="flex items-center gap-1">
                  <Building2 className="w-3 h-3" />
                  {data.department}
                </span>
              )}
              {data.project_type && (
                <span className="flex items-center gap-1">
                  <Briefcase className="w-3 h-3" />
                  {data.project_type}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <Link
            href={`/projects/${id}/edit`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-white hover:border-teal-electric/50 transition-colors"
          >
            <Edit className="w-4 h-4" />
            Edit
          </Link>
        </div>
      </div>

      {/* Progress & Timeline Banner */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-8">
          <ProgressRing percent={data.percent_complete ?? 0} size={100} strokeWidth={10} />
          <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-slate-muted text-sm mb-1">Expected Start</p>
              <p className="text-white font-semibold">{formatDate(data.expected_start_date)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-1">Expected End</p>
              <p className={cn('font-semibold', isOverdue ? 'text-red-400' : 'text-white')}>
                {formatDate(data.expected_end_date)}
                {isOverdue && <span className="ml-2 text-xs">(Overdue)</span>}
              </p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-1">Days Remaining</p>
              <p className={cn('font-semibold', daysRemaining !== null && daysRemaining < 0 ? 'text-red-400' : daysRemaining !== null && daysRemaining < 7 ? 'text-amber-400' : 'text-white')}>
                {daysRemaining !== null ? (daysRemaining < 0 ? `${Math.abs(daysRemaining)} days overdue` : `${daysRemaining} days`) : '-'}
              </p>
            </div>
            <div>
              <p className="text-slate-muted text-sm mb-1">Project Manager</p>
              <p className="text-white font-semibold">{data.project_manager || '-'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Total Tasks"
          value={formatNumber(taskStats.total)}
          subtitle={`${taskStats.open} open, ${taskStats.completed} done`}
          icon={ListTodo}
          colorClass="text-purple-400"
        />
        <KPICard
          title="Estimated Cost"
          value={formatCurrency(data.estimated_costing)}
          icon={DollarSign}
          colorClass="text-blue-400"
        />
        <KPICard
          title="Total Billed"
          value={formatCurrency(data.total_billed_amount)}
          icon={TrendingUp}
          colorClass="text-green-400"
        />
        <KPICard
          title="Gross Margin"
          value={formatCurrency(data.gross_margin)}
          subtitle={data.per_gross_margin ? `${data.per_gross_margin}%` : undefined}
          icon={BarChart3}
          colorClass={(data.gross_margin ?? 0) > 0 ? 'text-green-400' : 'text-red-400'}
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-border">
        <div className="flex gap-1">
          {[
            { key: 'overview', label: 'Overview', icon: ClipboardList },
            { key: 'tasks', label: `Tasks (${taskStats.total})`, icon: ListTodo },
            { key: 'team', label: `Team (${data.users?.length || 0})`, icon: Users },
            { key: 'financials', label: 'Financials', icon: DollarSign },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
                activeTab === tab.key
                  ? 'border-teal-electric text-teal-electric'
                  : 'border-transparent text-slate-muted hover:text-white'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Details */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-teal-electric" />
              Project Details
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-muted">Type</p>
                <p className="text-white font-medium">{data.project_type || '-'}</p>
              </div>
              <div>
                <p className="text-slate-muted">Customer</p>
                <p className="text-white font-medium">{data.customer?.name || data.erpnext_customer || '-'}</p>
              </div>
              <div>
                <p className="text-slate-muted">Cost Center</p>
                <p className="text-white font-medium">{data.cost_center || '-'}</p>
              </div>
              <div>
                <p className="text-slate-muted">Company</p>
                <p className="text-white font-medium">{data.company || '-'}</p>
              </div>
              <div>
                <p className="text-slate-muted">Actual Start</p>
                <p className="text-white font-medium">{formatDate(data.actual_start_date)}</p>
              </div>
              <div>
                <p className="text-slate-muted">Actual End</p>
                <p className="text-white font-medium">{formatDate(data.actual_end_date)}</p>
              </div>
            </div>
            {data.notes && (
              <div className="pt-3 border-t border-slate-border">
                <p className="text-slate-muted text-sm mb-2">Notes</p>
                <p className="text-white text-sm whitespace-pre-wrap">{data.notes}</p>
              </div>
            )}
          </div>

          {/* Recent Tasks */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <ListTodo className="w-4 h-4 text-teal-electric" />
                Recent Tasks
              </h3>
              <button
                onClick={() => setActiveTab('tasks')}
                className="text-teal-electric text-sm flex items-center gap-1 hover:underline"
              >
                View all <ChevronRight className="w-3 h-3" />
              </button>
            </div>
            {tasksLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 bg-slate-elevated rounded-lg animate-pulse" />
                ))}
              </div>
            ) : tasks.length > 0 ? (
              <div className="space-y-2">
                {tasks.slice(0, 5).map((task: any) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-muted">
                <ListTodo className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No tasks yet</p>
              </div>
            )}
            {taskStats.overdue > 0 && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-2 text-red-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>{taskStats.overdue} overdue task{taskStats.overdue > 1 ? 's' : ''}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'tasks' && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-teal-electric" />
              All Tasks ({taskStats.total})
            </h3>
            <Link
              href={`/projects/${id}/tasks/new`}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              <Plus className="w-4 h-4" />
              Add Task
            </Link>
          </div>

          {/* Task Stats */}
          <div className="flex gap-4 text-sm">
            <span className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              Open: {taskStats.open}
            </span>
            <span className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              Completed: {taskStats.completed}
            </span>
            {taskStats.overdue > 0 && (
              <span className="flex items-center gap-2 text-red-400">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                Overdue: {taskStats.overdue}
              </span>
            )}
          </div>

          {tasksLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-16 bg-slate-elevated rounded-lg animate-pulse" />
              ))}
            </div>
          ) : tasks.length > 0 ? (
            <div className="space-y-2">
              {tasks.map((task: any) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-muted">
              <ListTodo className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-lg mb-2">No tasks yet</p>
              <p className="text-sm">Create your first task to start tracking progress</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'team' && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <Users className="w-4 h-4 text-teal-electric" />
              Project Team ({data.users?.length || 0})
            </h3>
            <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70">
              <Plus className="w-4 h-4" />
              Add Member
            </button>
          </div>
          {data.users?.length ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {data.users.map((user: any, idx: number) => (
                <div key={idx} className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg">
                  <div className="w-10 h-10 rounded-full bg-teal-electric/20 flex items-center justify-center text-teal-electric font-semibold">
                    {(user.full_name || user.user || '?')[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{user.full_name || user.user}</p>
                    <p className="text-slate-muted text-sm truncate">{user.email || '-'}</p>
                  </div>
                  {user.project_status && (
                    <span className="text-xs text-slate-muted bg-slate-card px-2 py-1 rounded">{user.project_status}</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-muted">
              <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-lg mb-2">No team members</p>
              <p className="text-sm">Add team members to collaborate on this project</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'financials' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <p className="text-slate-muted text-sm mb-2">Estimated Cost</p>
              <p className="text-2xl font-bold text-blue-400">{formatCurrency(data.estimated_costing)}</p>
            </div>
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <p className="text-slate-muted text-sm mb-2">Total Actual Cost</p>
              <p className="text-2xl font-bold text-amber-400">{formatCurrency(data.total_costing_amount)}</p>
            </div>
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <p className="text-slate-muted text-sm mb-2">Total Billed</p>
              <p className="text-2xl font-bold text-green-400">{formatCurrency(data.total_billed_amount)}</p>
            </div>
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <p className="text-slate-muted text-sm mb-2">Gross Margin</p>
              <p className={cn('text-2xl font-bold', (data.gross_margin || 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                {formatCurrency(data.gross_margin)}
              </p>
              {data.per_gross_margin !== null && data.per_gross_margin !== undefined && (
                <p className="text-slate-muted text-sm mt-1">{data.per_gross_margin}% margin</p>
              )}
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              Cost Breakdown
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-slate-muted">Expense Claims</p>
                <p className="text-white font-semibold text-lg">{formatCurrency(data.total_expense_claim)}</p>
              </div>
              <div>
                <p className="text-slate-muted">Purchase Cost</p>
                <p className="text-white font-semibold text-lg">{formatCurrency(data.total_purchase_cost)}</p>
              </div>
              <div>
                <p className="text-slate-muted">Material Cost</p>
                <p className="text-white font-semibold text-lg">{formatCurrency(data.total_consumed_material_cost)}</p>
              </div>
              <div>
                <p className="text-slate-muted">Billable Amount</p>
                <p className="text-white font-semibold text-lg">{formatCurrency(data.total_billable_amount)}</p>
              </div>
            </div>
          </div>

          {/* Budget Variance */}
          {(data.estimated_costing ?? 0) > 0 && (
            <div className={cn(
              'rounded-xl p-4 border',
              (data.total_costing_amount || 0) <= (data.estimated_costing ?? 0)
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-red-500/10 border-red-500/30'
            )}>
              <div className="flex items-center justify-between">
                <div>
                  <p className={cn(
                    'font-semibold',
                    (data.total_costing_amount || 0) <= (data.estimated_costing ?? 0) ? 'text-green-400' : 'text-red-400'
                  )}>
                    {(data.total_costing_amount || 0) <= (data.estimated_costing ?? 0) ? 'Under Budget' : 'Over Budget'}
                  </p>
                  <p className="text-slate-muted text-sm">
                    {formatCurrency(Math.abs((data.estimated_costing ?? 0) - (data.total_costing_amount || 0)))}
                    {' '}{(data.total_costing_amount || 0) <= (data.estimated_costing ?? 0) ? 'remaining' : 'overrun'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-slate-muted text-sm">Budget Utilization</p>
                  <p className="text-2xl font-bold text-white">
                    {(data.estimated_costing ?? 0) > 0
                      ? Math.round(((data.total_costing_amount || 0) / (data.estimated_costing ?? 1)) * 100)
                      : 0}%
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
