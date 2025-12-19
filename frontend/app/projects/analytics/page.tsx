'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from 'recharts';
import {
  useProjectsDashboard,
  useProjectsStatusTrend,
  useProjectsTaskDistribution,
  useProjectsPerformance,
  useProjectsDepartmentSummary,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Users,
  Loader2,
  Target,
  Calendar,
  Building2,
  ListTodo,
  PieChart as PieChartIcon,
  Activity,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { CHART_COLORS } from '@/lib/design-tokens';

const CHART_PALETTE = CHART_COLORS.palette;
const STATUS_COLORS: Record<string, string> = {
  open: CHART_COLORS.info,
  completed: CHART_COLORS.success,
  on_hold: CHART_COLORS.warning,
  cancelled: CHART_COLORS.danger,
};
const PRIORITY_COLORS: Record<string, string> = {
  high: CHART_COLORS.danger,
  medium: CHART_COLORS.warning,
  low: CHART_COLORS.axis,
};

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

function formatCurrency(value: number | undefined | null): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency: 'NGN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatPercent(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0%';
  return `${value.toFixed(1)}%`;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  trend?: { value: number; label: string };
  loading?: boolean;
}

function MetricCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', trend, loading }: MetricCardProps) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-slate-muted text-sm">{title}</p>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <p className={cn('text-2xl font-bold', colorClass)}>{value}</p>
          )}
          {subtitle && <p className="text-slate-muted text-xs">{subtitle}</p>}
          {trend && (
            <div className={cn('flex items-center gap-1 text-xs', trend.value >= 0 ? 'text-green-400' : 'text-red-400')}>
              {trend.value >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}</span>
            </div>
          )}
        </div>
        <div className={cn('p-2 rounded-lg bg-slate-elevated')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, icon: Icon, children, className }: {
  title: string;
  subtitle?: string;
  icon?: React.ElementType;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl p-5', className)}>
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-5 h-5 text-teal-electric" />}
        <div>
          <h3 className="text-white font-semibold">{title}</h3>
          {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function RatioCard({ title, value, description, status }: {
  title: string;
  value: string;
  description: string;
  status: 'good' | 'warning' | 'bad';
}) {
  const statusColors = {
    good: 'border-green-500/30 bg-green-500/10',
    warning: 'border-yellow-500/30 bg-yellow-500/10',
    bad: 'border-red-500/30 bg-red-500/10',
  };
  const valueColors = {
    good: 'text-green-400',
    warning: 'text-yellow-400',
    bad: 'text-red-400',
  };

  return (
    <div className={cn('rounded-xl p-4 border', statusColors[status])}>
      <p className="text-slate-muted text-sm mb-1">{title}</p>
      <p className={cn('text-xl font-bold', valueColors[status])}>{value}</p>
      <p className="text-slate-muted text-xs mt-1">{description}</p>
    </div>
  );
}

export default function ProjectsAnalyticsPage() {
  // Fetch all analytics data
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError } = useProjectsDashboard();
  const { data: statusTrend, isLoading: trendLoading, error: trendError } = useProjectsStatusTrend(12);
  const { data: taskDistribution, isLoading: taskLoading, error: taskError } = useProjectsTaskDistribution();
  const { data: performance, isLoading: perfLoading, error: perfError } = useProjectsPerformance();
  const { data: departmentSummary, isLoading: deptLoading, error: deptError } = useProjectsDepartmentSummary();

  const loading = dashboardLoading || trendLoading || taskLoading || perfLoading || deptLoading;
  const error = dashboardError || trendError || taskError || perfError || deptError;

  // Process status distribution for pie chart
  const statusData = useMemo(() => {
    if (!dashboard?.projects) return [];
    const { active, completed, on_hold, cancelled } = dashboard.projects;
    return [
      { name: 'Active', value: active || 0, color: STATUS_COLORS.open },
      { name: 'Completed', value: completed || 0, color: STATUS_COLORS.completed },
      { name: 'On Hold', value: on_hold || 0, color: STATUS_COLORS.on_hold },
      { name: 'Cancelled', value: cancelled || 0, color: STATUS_COLORS.cancelled },
    ].filter(d => d.value > 0);
  }, [dashboard]);

  // Process priority distribution
  const priorityData = useMemo(() => {
    if (!dashboard?.by_priority) return [];
    return Object.entries(dashboard.by_priority).map(([key, value]) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value: value as number,
      color: PRIORITY_COLORS[key] || CHART_PALETTE[0],
    })).filter(d => d.value > 0);
  }, [dashboard]);

  // Process task status for bar chart
  const taskStatusData = useMemo(() => {
    if (!taskDistribution?.by_status) return [];
    return taskDistribution.by_status.map((item: any) => ({
      name: item.status?.charAt(0).toUpperCase() + item.status?.slice(1) || 'Unknown',
      count: item.count || 0,
      fill: STATUS_COLORS[item.status] || CHART_PALETTE[0],
    }));
  }, [taskDistribution]);

  // Process task priority for bar chart
  const taskPriorityData = useMemo(() => {
    if (!taskDistribution?.by_priority) return [];
    return taskDistribution.by_priority.map((item: any) => ({
      name: item.priority?.charAt(0).toUpperCase() + item.priority?.slice(1) || 'Unknown',
      count: item.count || 0,
      fill: PRIORITY_COLORS[item.priority] || CHART_PALETTE[0],
    }));
  }, [taskDistribution]);

  // Process top assignees
  const assigneeData = useMemo(() => {
    if (!taskDistribution?.by_assignee) return [];
    return taskDistribution.by_assignee.slice(0, 8).map((item: any) => ({
      name: (item.assignee || 'Unassigned').split('@')[0].substring(0, 12),
      total: item.total || 0,
      completed: item.completed || 0,
      rate: item.completion_rate || 0,
    }));
  }, [taskDistribution]);

  // Process department summary
  const deptData = useMemo(() => {
    if (!departmentSummary) return [];
    return (departmentSummary as any[]).slice(0, 8).map((item: any) => ({
      name: (item.department || 'Unknown').substring(0, 15),
      projects: item.project_count || 0,
      tasks: item.task_count || 0,
      completion: item.avg_completion || 0,
    }));
  }, [departmentSummary]);

  // Process trend data for area chart
  const trendData = useMemo(() => {
    if (!statusTrend) return [];
    return (statusTrend as any[]).map((item: any) => ({
      period: item.period,
      created: item.created || 0,
      completed: item.completed || 0,
    }));
  }, [statusTrend]);

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load project analytics"
        error={error as Error}
      />
    );
  }

  // Calculate metrics
  const totalProjects = dashboard?.projects?.total || 0;
  const activeProjects = dashboard?.projects?.active || 0;
  const completedProjects = dashboard?.projects?.completed || 0;
  const totalTasks = dashboard?.tasks?.total || 0;
  const openTasks = dashboard?.tasks?.open || 0;
  const overdueTasks = dashboard?.tasks?.overdue || 0;
  const avgCompletion = dashboard?.metrics?.avg_completion_percent || 0;
  const dueThisWeek = dashboard?.metrics?.due_this_week || 0;

  // Financial metrics (dashboard financials shape varies per API response)
  const financials: any = dashboard?.financials || {};
  const totalEstimated = financials.total_estimated ?? 0;
  const totalActual = financials.total_actual_cost ?? 0;
  const totalBilled = financials.total_billed ?? 0;
  const variance = financials.variance ?? 0;

  // Performance metrics
  const budgetAdherence = performance?.budget?.adherence_rate || 0;
  const onTimeRate = performance?.timeline?.on_time_rate || 0;
  const avgMargin = performance?.profitability?.avg_margin_percent || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
          <BarChart3 className="w-5 h-5 text-teal-electric" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Project Analytics</h1>
          <p className="text-slate-muted text-sm">Performance metrics, trends, and insights</p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Projects"
          value={formatNumber(totalProjects)}
          subtitle={`${activeProjects} active`}
          icon={Building2}
          colorClass="text-blue-400"
        />
        <MetricCard
          title="Total Tasks"
          value={formatNumber(totalTasks)}
          subtitle={`${openTasks} open, ${overdueTasks} overdue`}
          icon={ListTodo}
          colorClass="text-purple-400"
        />
        <MetricCard
          title="Avg Completion"
          value={formatPercent(avgCompletion)}
          subtitle="Active projects"
          icon={Target}
          colorClass="text-teal-electric"
        />
        <MetricCard
          title="Due This Week"
          value={formatNumber(dueThisWeek)}
          subtitle="Projects ending soon"
          icon={Calendar}
          colorClass={dueThisWeek > 5 ? 'text-amber-400' : 'text-green-400'}
        />
      </div>

      {/* Performance Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RatioCard
          title="Budget Adherence"
          value={formatPercent(budgetAdherence)}
          description="Projects under budget"
          status={budgetAdherence >= 70 ? 'good' : budgetAdherence >= 50 ? 'warning' : 'bad'}
        />
        <RatioCard
          title="On-Time Delivery"
          value={formatPercent(onTimeRate)}
          description="Completed on schedule"
          status={onTimeRate >= 70 ? 'good' : onTimeRate >= 50 ? 'warning' : 'bad'}
        />
        <RatioCard
          title="Avg Profit Margin"
          value={formatPercent(avgMargin)}
          description="Across billed projects"
          status={avgMargin >= 20 ? 'good' : avgMargin >= 10 ? 'warning' : 'bad'}
        />
      </div>

      {/* Charts Row 1: Status & Priority Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Project Status Distribution */}
        <ChartCard title="Project Status" subtitle="Distribution by status" icon={PieChartIcon}>
          {statusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No project data available
            </div>
          )}
        </ChartCard>

        {/* Priority Distribution */}
        <ChartCard title="Active Projects by Priority" subtitle="High, medium, low" icon={AlertTriangle}>
          {priorityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={priorityData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} width={70} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="value" name="Projects" radius={[0, 4, 4, 0]}>
                  {priorityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No priority data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Charts Row 2: Trend & Task Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Project Trend */}
        <ChartCard title="Project Trend" subtitle="Created vs completed over time" icon={TrendingUp}>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="period" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Area
                  type="monotone"
                  dataKey="created"
                  name="Created"
                  stroke={CHART_COLORS.info}
                  fill={CHART_COLORS.info}
                  fillOpacity={0.3}
                />
                <Area
                  type="monotone"
                  dataKey="completed"
                  name="Completed"
                  stroke={CHART_COLORS.success}
                  fill={CHART_COLORS.success}
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No trend data available
            </div>
          )}
        </ChartCard>

        {/* Task Status Distribution */}
        <ChartCard title="Task Status" subtitle="Distribution by status" icon={ListTodo}>
          {taskStatusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={taskStatusData}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" name="Tasks" radius={[4, 4, 0, 0]}>
                  {taskStatusData.map((entry: { fill: string }, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No task data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Charts Row 3: Assignees & Department */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Assignees */}
        <ChartCard title="Top Task Assignees" subtitle="Task count and completion rate" icon={Users}>
          {assigneeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={assigneeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} width={80} />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(value: any, name: string) => [
                    name === 'rate' ? `${value}%` : value,
                    name === 'total' ? 'Total' : name === 'completed' ? 'Completed' : 'Rate'
                  ]}
                />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Bar dataKey="total" name="Total" fill={CHART_COLORS.info} radius={[0, 4, 4, 0]} />
                <Bar dataKey="completed" name="Completed" fill={CHART_COLORS.success} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-slate-muted text-sm">
              No assignee data available
            </div>
          )}
        </ChartCard>

        {/* Department Summary */}
        <ChartCard title="Department Summary" subtitle="Projects and tasks by department" icon={Building2}>
          {deptData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={deptData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} width={100} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Bar dataKey="projects" name="Projects" fill={CHART_COLORS.palette[2]} radius={[0, 4, 4, 0]} />
                <Bar dataKey="tasks" name="Tasks" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-slate-muted text-sm">
              No department data available
            </div>
          )}
        </ChartCard>
      </div>

      {/* Financial Summary */}
      <ChartCard title="Financial Overview" subtitle="Budget, costs, and billing" icon={Activity}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-elevated rounded-lg p-4">
            <p className="text-slate-muted text-sm">Total Estimated</p>
            <p className="text-xl font-bold text-blue-400">{formatCurrency(totalEstimated)}</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-4">
            <p className="text-slate-muted text-sm">Actual Cost</p>
            <p className="text-xl font-bold text-amber-400">{formatCurrency(totalActual)}</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-4">
            <p className="text-slate-muted text-sm">Total Billed</p>
            <p className="text-xl font-bold text-green-400">{formatCurrency(totalBilled)}</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-4">
            <p className="text-slate-muted text-sm">Budget Variance</p>
            <p className={cn('text-xl font-bold', variance >= 0 ? 'text-green-400' : 'text-red-400')}>
              {formatCurrency(Math.abs(variance))}
              <span className="text-sm ml-1">{variance >= 0 ? 'under' : 'over'}</span>
            </p>
          </div>
        </div>
      </ChartCard>

      {/* Top Profitable Projects */}
      {performance?.profitability?.top_projects && performance.profitability.top_projects.length > 0 && (
        <ChartCard title="Top Profitable Projects" subtitle="Highest margin projects" icon={TrendingUp}>
          <div className="space-y-3">
            {performance.profitability.top_projects.map((project: any, index: number) => (
              <div key={project.id || index} className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-slate-muted text-sm">#{index + 1}</span>
                  <div>
                    <p className="text-white font-medium">{project.project_name}</p>
                    <p className="text-slate-muted text-xs">Margin: {formatPercent(project.margin_percent)}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-green-400 font-bold">{formatCurrency(project.gross_margin)}</p>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      )}

      {/* Overdue Tasks Warning */}
      {overdueTasks > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <div>
            <p className="text-red-400 font-semibold">{overdueTasks} Overdue Tasks</p>
            <p className="text-slate-muted text-sm">Tasks past their expected end date that need attention</p>
          </div>
        </div>
      )}
    </div>
  );
}
