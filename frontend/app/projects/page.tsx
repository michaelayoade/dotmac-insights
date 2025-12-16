'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { DataTable, Pagination } from '@/components/DataTable';
import { useProjects, useProjectsDashboard } from '@/hooks/useApi';
import {
  Filter,
  Plus,
  ClipboardList,
  AlertTriangle,
  Tag,
  Clock,
  CheckCircle2,
  Pause,
  XCircle,
  TrendingUp,
  ListTodo,
  Target,
  Calendar,
  BarChart3,
  ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatCurrency(value: number | undefined | null): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency: 'NGN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// Mini progress ring component
function ProgressRing({ percent, size = 48, strokeWidth = 4 }: { percent: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percent / 100) * circumference;

  return (
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
        stroke="#2dd4bf"
        strokeWidth={strokeWidth}
        fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-500"
      />
    </svg>
  );
}

// Status bar mini chart
function StatusBar({ open, completed, onHold, cancelled }: { open: number; completed: number; onHold: number; cancelled: number }) {
  const total = open + completed + onHold + cancelled;
  if (total === 0) return null;

  const segments = [
    { value: open, color: 'bg-blue-500', label: 'Active' },
    { value: completed, color: 'bg-green-500', label: 'Completed' },
    { value: onHold, color: 'bg-amber-500', label: 'On Hold' },
    { value: cancelled, color: 'bg-red-500', label: 'Cancelled' },
  ].filter(s => s.value > 0);

  return (
    <div className="space-y-2">
      <div className="flex h-2 rounded-full overflow-hidden">
        {segments.map((seg, i) => (
          <div
            key={i}
            className={cn(seg.color, 'transition-all duration-300')}
            style={{ width: `${(seg.value / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex gap-3 text-xs">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={cn('w-2 h-2 rounded-full', seg.color)} />
            <span className="text-slate-muted">{seg.label}: {seg.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  trend?: { value: number; isPositive: boolean };
  children?: React.ReactNode;
}

function KPICard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', trend, children }: KPICardProps) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className={cn('p-2 rounded-lg bg-slate-elevated')}>
          <Icon className={cn('w-4 h-4', colorClass)} />
        </div>
        {trend && (
          <div className={cn('text-xs flex items-center gap-1', trend.isPositive ? 'text-green-400' : 'text-red-400')}>
            <TrendingUp className={cn('w-3 h-3', !trend.isPositive && 'rotate-180')} />
            {Math.abs(trend.value)}%
          </div>
        )}
      </div>
      <p className={cn('text-2xl font-bold mb-1', colorClass)}>{value}</p>
      <p className="text-slate-muted text-sm">{title}</p>
      {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

export default function ProjectsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [priority, setPriority] = useState<string>('');
  const [department, setDepartment] = useState<string>('');
  const [projectType, setProjectType] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const offset = (page - 1) * pageSize;

  const { data, isLoading, error } = useProjects({
    status: status || undefined,
    priority: (priority || undefined) as any,
    department: department || undefined,
    project_type: projectType || undefined,
    search: search || undefined,
    limit: pageSize,
    offset,
  });

  const { data: dashboard, isLoading: dashboardLoading } = useProjectsDashboard();

  const projects = data?.data || [];
  const total = data?.total || 0;

  // Extract dashboard metrics
  const metrics = useMemo(() => {
    if (!dashboard) return null;
    return {
      totalProjects: dashboard.projects?.total || 0,
      activeProjects: dashboard.projects?.active || 0,
      completedProjects: dashboard.projects?.completed || 0,
      onHoldProjects: dashboard.projects?.on_hold || 0,
      cancelledProjects: dashboard.projects?.cancelled || 0,
      totalTasks: dashboard.tasks?.total || 0,
      openTasks: dashboard.tasks?.open || 0,
      overdueTasks: dashboard.tasks?.overdue || 0,
      avgCompletion: dashboard.metrics?.avg_completion_percent || 0,
      dueThisWeek: dashboard.metrics?.due_this_week || 0,
      totalBilled: dashboard.financials?.total_billed || 0,
    };
  }, [dashboard]);

  const columns = [
    {
      key: 'name',
      header: 'Project',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-white font-semibold">{item.erpnext_id || item.project_name}</span>
          <span className="text-slate-muted text-sm line-clamp-1">{item.department || '-'}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const s = item.status || 'open';
        const config: Record<string, { icon: React.ElementType; color: string }> = {
          open: { icon: ClipboardList, color: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
          completed: { icon: CheckCircle2, color: 'text-green-400 bg-green-500/10 border-green-500/30' },
          on_hold: { icon: Pause, color: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
          cancelled: { icon: XCircle, color: 'text-red-400 bg-red-500/10 border-red-500/30' },
        };
        const { icon: StatusIcon, color } = config[s] || config.open;
        return (
          <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
            <StatusIcon className="w-3 h-3" />
            {s.replace('_', ' ')}
          </span>
        );
      },
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: any) => {
        const pri = item.priority || 'medium';
        const color =
          pri === 'high'
            ? 'bg-red-500/10 text-red-400 border-red-500/30'
            : pri === 'low'
            ? 'bg-slate-500/10 text-slate-300 border-slate-500/30'
            : 'bg-amber-500/10 text-amber-400 border-amber-500/30';
        return (
          <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
            <Tag className="w-3 h-3" />
            {pri}
          </span>
        );
      },
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (item: any) => {
        const pct = item.percent_complete ?? 0;
        return (
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 bg-slate-elevated rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  pct >= 100 ? 'bg-green-500' : pct >= 50 ? 'bg-teal-electric' : 'bg-blue-500'
                )}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <span className="text-sm text-slate-muted w-10">{pct}%</span>
          </div>
        );
      },
    },
    {
      key: 'dates',
      header: 'Timeline',
      render: (item: any) => {
        const isOverdue = item.expected_end_date && new Date(item.expected_end_date) < new Date() && item.status === 'open';
        return (
          <div className={cn('text-sm space-y-1', isOverdue ? 'text-red-400' : 'text-slate-muted')}>
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{formatDate(item.expected_start_date)} → {formatDate(item.expected_end_date)}</span>
            </div>
            {isOverdue && (
              <span className="text-xs text-red-400 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Overdue
              </span>
            )}
          </div>
        );
      },
    },
    {
      key: 'tasks',
      header: 'Tasks',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm text-slate-muted">
          <ListTodo className="w-3 h-3" />
          <span>{item.task_count ?? 0}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
            <ClipboardList className="w-5 h-5 text-teal-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Projects</h1>
            <p className="text-slate-muted text-sm">Plan, track, and deliver projects across teams</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/projects/analytics"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white hover:border-teal-electric/50 transition-colors"
          >
            <BarChart3 className="w-4 h-4" />
            Analytics
          </Link>
          <Link
            href="/projects/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
          >
            <Plus className="w-4 h-4" />
            New Project
          </Link>
        </div>
      </div>

      {/* Dashboard KPIs */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard
            title="Total Projects"
            value={formatNumber(metrics.totalProjects)}
            icon={ClipboardList}
            colorClass="text-blue-400"
          >
            <StatusBar
              open={metrics.activeProjects}
              completed={metrics.completedProjects}
              onHold={metrics.onHoldProjects}
              cancelled={metrics.cancelledProjects}
            />
          </KPICard>

          <KPICard
            title="Tasks"
            value={formatNumber(metrics.totalTasks)}
            subtitle={`${metrics.openTasks} open, ${metrics.overdueTasks} overdue`}
            icon={ListTodo}
            colorClass="text-purple-400"
          />

          <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center gap-4">
            <ProgressRing percent={metrics.avgCompletion} size={56} strokeWidth={5} />
            <div>
              <p className="text-2xl font-bold text-teal-electric">{metrics.avgCompletion.toFixed(0)}%</p>
              <p className="text-slate-muted text-sm">Avg Completion</p>
              <p className="text-slate-muted text-xs">Active projects</p>
            </div>
          </div>

          <KPICard
            title="Due This Week"
            value={formatNumber(metrics.dueThisWeek)}
            subtitle={metrics.totalBilled > 0 ? `${formatCurrency(metrics.totalBilled)} billed` : undefined}
            icon={Calendar}
            colorClass={metrics.dueThisWeek > 5 ? 'text-amber-400' : 'text-green-400'}
          />
        </div>
      )}

      {/* Quick Stats Row */}
      {metrics && (
        <div className="flex items-center gap-6 px-4 py-3 bg-slate-elevated rounded-xl border border-slate-border">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-slate-muted text-sm">Active:</span>
            <span className="text-white font-semibold">{metrics.activeProjects}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-slate-muted text-sm">Completed:</span>
            <span className="text-white font-semibold">{metrics.completedProjects}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-slate-muted text-sm">On Hold:</span>
            <span className="text-white font-semibold">{metrics.onHoldProjects}</span>
          </div>
          {metrics.overdueTasks > 0 && (
            <div className="flex items-center gap-2 ml-auto text-red-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm font-medium">{metrics.overdueTasks} overdue tasks</span>
            </div>
          )}
          <Link href="/projects/analytics" className="flex items-center gap-1 text-teal-electric text-sm hover:underline ml-auto">
            View Analytics <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search projects..."
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 col-span-2 lg:col-span-1"
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="on_hold">On Hold</option>
          </select>
          <select
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <input
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
            placeholder="Department"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={projectType}
            onChange={(e) => {
              setProjectType(e.target.value);
              setPage(1);
            }}
            placeholder="Project type"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          {(status || priority || department || projectType || search) && (
            <button
              onClick={() => {
                setStatus('');
                setPriority('');
                setDepartment('');
                setProjectType('');
                setSearch('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors flex items-center gap-1"
            >
              <XCircle className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Projects Table */}
      {error ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load projects. Please check your connection and try again.</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={projects}
          keyField="id"
          loading={isLoading}
          emptyMessage="No projects found matching your filters"
          onRowClick={(item) => router.push(`/projects/${(item as any).id}`)}
        />
      )}

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={offset}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
