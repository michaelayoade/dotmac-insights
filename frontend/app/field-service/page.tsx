'use client';

import Link from 'next/link';
import { useConsolidatedFieldServiceDashboard } from '@/hooks/useApi';
import {
  ClipboardList,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Users,
  Truck,
  MapPin,
  Star,
  TrendingUp,
  ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';

function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass = 'text-teal-electric',
  trend,
  href,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  trend?: { value: number; label: string };
  href?: string;
}) {
  const content = (
    <div className={cn(
      'bg-slate-card border border-slate-border rounded-xl p-5 transition-colors',
      href && 'hover:border-teal-electric/50 cursor-pointer'
    )}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Icon className={cn('w-5 h-5', colorClass)} />
            <span className="text-slate-muted text-sm">{title}</span>
          </div>
          <p className={cn('text-3xl font-bold', colorClass)}>{value}</p>
          {subtitle && <p className="text-slate-muted text-sm mt-1">{subtitle}</p>}
        </div>
        {trend && (
          <div className={cn(
            'text-xs font-medium px-2 py-1 rounded',
            trend.value >= 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          )}>
            {trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}
          </div>
        )}
      </div>
      {href && (
        <div className="mt-3 pt-3 border-t border-slate-border/50 flex items-center text-xs text-teal-electric">
          <span>View details</span>
          <ArrowRight className="w-3 h-3 ml-1" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

function StatusBadge({ status, count, href }: { status: string; count: number; href?: string }) {
  const config: Record<string, { color: string; label: string }> = {
    draft: { color: 'bg-slate-500', label: 'Draft' },
    pending: { color: 'bg-yellow-500', label: 'Pending' },
    scheduled: { color: 'bg-blue-500', label: 'Scheduled' },
    dispatched: { color: 'bg-purple-500', label: 'Dispatched' },
    en_route: { color: 'bg-amber-500', label: 'En Route' },
    on_site: { color: 'bg-cyan-500', label: 'On Site' },
    in_progress: { color: 'bg-teal-500', label: 'In Progress' },
    completed: { color: 'bg-green-500', label: 'Completed' },
    cancelled: { color: 'bg-red-500', label: 'Cancelled' },
  };

  const { color, label } = config[status] || { color: 'bg-slate-500', label: status.replace('_', ' ') };

  const content = (
    <div className={cn(
      'flex items-center justify-between py-2 px-3 rounded-lg bg-slate-elevated transition-colors',
      href && 'hover:bg-slate-elevated/80 cursor-pointer'
    )}>
      <div className="flex items-center gap-2">
        <div className={cn('w-2 h-2 rounded-full', color)} />
        <span className="text-sm text-slate-muted capitalize">{label}</span>
      </div>
      <span className="text-white font-semibold">{count}</span>
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

function OrderRow({ order }: { order: any }) {
  const priorityColors: Record<string, string> = {
    emergency: 'text-red-500 bg-red-500/10',
    urgent: 'text-orange-500 bg-orange-500/10',
    high: 'text-amber-500 bg-amber-500/10',
    medium: 'text-blue-500 bg-blue-500/10',
    low: 'text-slate-400 bg-slate-400/10',
  };

  const statusColors: Record<string, string> = {
    draft: 'text-slate-400',
    pending: 'text-yellow-400',
    scheduled: 'text-blue-400',
    dispatched: 'text-purple-400',
    en_route: 'text-amber-400',
    on_site: 'text-cyan-400',
    in_progress: 'text-teal-400',
    completed: 'text-green-400',
    cancelled: 'text-red-400',
  };

  const formatTime = (dateStr?: string | null) => {
    if (!dateStr) return 'TBD';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Link
      href={`/field-service/orders/${order.id}`}
      className="flex items-center gap-4 p-3 rounded-lg border border-slate-border hover:border-teal-electric/50 hover:bg-slate-elevated/50 transition-colors"
    >
      <div className={cn('px-2 py-1 rounded text-xs font-medium capitalize', priorityColors[order.priority] || priorityColors.medium)}>
        {order.priority || 'medium'}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium truncate">{order.order_type || 'Service Order'}</p>
        <div className="flex items-center gap-3 text-xs text-slate-muted mt-1">
          <span>{order.order_number || `#${order.id}`}</span>
          {order.customer_address && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {order.customer_address.substring(0, 30)}...
            </span>
          )}
          {order.customer_name && (
            <span>{order.customer_name}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {order.technician_name && (
          <span className="text-xs text-slate-muted">{order.technician_name}</span>
        )}
        <span className={cn('text-xs font-medium capitalize', statusColors[order.status] || 'text-slate-muted')}>
          {order.status?.replace('_', ' ') || 'pending'}
        </span>
        <span className="text-xs text-slate-muted">
          {formatTime(order.scheduled_date)}
        </span>
      </div>
    </Link>
  );
}

function QuickActionCard({
  title,
  description,
  href,
  icon: Icon,
  colorClass = 'text-teal-electric',
}: {
  title: string;
  description: string;
  href: string;
  icon: React.ElementType;
  colorClass?: string;
}) {
  return (
    <Link
      href={href}
      className="group bg-slate-card border border-slate-border rounded-xl p-4 hover:border-teal-electric/50 transition-colors"
    >
      <div className="flex items-center gap-3 mb-2">
        <div className={cn('p-2 rounded-lg bg-slate-elevated group-hover:bg-teal-electric/10 transition-colors')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
        <div>
          <p className="text-white font-semibold">{title}</p>
          <p className="text-slate-muted text-sm">{description}</p>
        </div>
      </div>
      <div className="flex items-center text-xs text-teal-electric mt-2">
        <span>Open</span>
        <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </Link>
  );
}

export default function FieldServiceDashboard() {
  const { data, isLoading, error, mutate } = useConsolidatedFieldServiceDashboard();

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load field service dashboard data."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) {
    return <LoadingState />;
  }

  const { summary, by_status, by_type, today_schedule } = data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Field Service Dashboard"
        subtitle="Service orders, dispatch board, and technician management"
        icon={Truck}
        iconClassName="bg-cyan-500/10 border border-cyan-500/30"
      />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Today's Orders"
          value={summary?.today_orders ?? 0}
          subtitle="Scheduled for today"
          icon={ClipboardList}
          colorClass="text-blue-400"
          href="/field-service/orders?date=today"
        />
        <KPICard
          title="Completed Today"
          value={summary?.completed_today ?? 0}
          subtitle="Successfully finished"
          icon={CheckCircle2}
          colorClass="text-emerald-400"
          href="/field-service/orders?status=completed&date=today"
        />
        <KPICard
          title="Unassigned"
          value={summary?.unassigned ?? 0}
          subtitle="Needs technician"
          icon={Users}
          colorClass={summary?.unassigned ? 'text-amber-400' : 'text-slate-muted'}
          href="/field-service/orders?unassigned=true"
        />
        <KPICard
          title="Overdue"
          value={summary?.overdue ?? 0}
          subtitle="Past scheduled time"
          icon={AlertTriangle}
          colorClass={summary?.overdue ? 'text-rose-400' : 'text-slate-muted'}
          href="/field-service/orders?overdue=true"
        />
      </div>

      {/* Status Overview & Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Status Breakdown */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-teal-electric" />
              <h3 className="text-white font-semibold">Orders by Status</h3>
            </div>
            <Link href="/field-service/orders" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-2">
            {by_status && Object.entries(by_status).length > 0 ? (
              Object.entries(by_status).map(([status, count]) => (
                <StatusBadge
                  key={status}
                  status={status}
                  count={count as number}
                  href={`/field-service/orders?status=${status}`}
                />
              ))
            ) : (
              <p className="text-slate-muted text-sm">No orders</p>
            )}
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-teal-electric" />
              <h3 className="text-white font-semibold">This Week</h3>
            </div>
            <Link href="/field-service/analytics" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              Analytics <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Completion Rate</span>
              <span className={cn(
                'font-bold',
                (summary?.week_completion_rate || 0) >= 80 ? 'text-emerald-400' :
                (summary?.week_completion_rate || 0) >= 50 ? 'text-amber-400' : 'text-rose-400'
              )}>
                {(summary?.week_completion_rate ?? 0).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Customer Satisfaction</span>
              <div className="flex items-center gap-1">
                <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                <span className="text-white font-bold">{(summary?.avg_customer_rating ?? 0).toFixed(1)}</span>
              </div>
            </div>
          </div>
          {by_type && Object.entries(by_type).length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-border">
              <p className="text-slate-muted text-xs mb-2">Orders by Type</p>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(by_type).slice(0, 4).map(([type, count]) => (
                  <Link
                    key={type}
                    href={`/field-service/orders?type=${type}`}
                    className="text-xs px-2 py-1 rounded-full bg-slate-elevated text-slate-muted hover:text-white transition-colors"
                  >
                    {type}: {count as number}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-teal-electric" />
            <h3 className="text-white font-semibold">Quick Actions</h3>
          </div>
          <div className="space-y-3">
            <QuickActionCard
              title="Dispatch Board"
              description="Assign orders to technicians"
              href="/field-service/dispatch"
              icon={Truck}
              colorClass="text-cyan-400"
            />
            <QuickActionCard
              title="Calendar View"
              description="Schedule overview"
              href="/field-service/calendar"
              icon={Calendar}
              colorClass="text-blue-400"
            />
            <QuickActionCard
              title="Technicians"
              description="Manage field team"
              href="/field-service/technicians"
              icon={Users}
              colorClass="text-emerald-400"
            />
          </div>
        </div>
      </div>

      {/* Today's Schedule */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-teal-electric" />
            <h3 className="text-white font-semibold">Today's Schedule</h3>
            <span className="text-slate-muted text-sm">({today_schedule?.length || 0} orders)</span>
          </div>
          <Link href="/field-service/orders?date=today" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
            View All <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        {today_schedule && today_schedule.length > 0 ? (
          <div className="space-y-2">
            {today_schedule.map((order) => (
              <OrderRow key={order.id} order={order} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-slate-muted">
            <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No orders scheduled for today</p>
            <Link href="/field-service/orders/new" className="text-teal-electric text-sm hover:text-teal-glow mt-2 inline-block">
              Create a new order
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
