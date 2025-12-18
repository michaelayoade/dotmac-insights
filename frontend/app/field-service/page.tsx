'use client';

import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
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
  RefreshCw,
} from 'lucide-react';
import { fieldServiceApi } from '@/lib/api';
import { cn } from '@/lib/utils';

// KPI Card Component
function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass = 'text-teal-electric',
  trend,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  trend?: { value: number; label: string };
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
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
    </div>
  );
}

// Status Badge
function StatusBadge({ status, count }: { status: string; count: number }) {
  const config: Record<string, { color: string; label: string }> = {
    draft: { color: 'bg-slate-500', label: 'Draft' },
    scheduled: { color: 'bg-blue-500', label: 'Scheduled' },
    dispatched: { color: 'bg-purple-500', label: 'Dispatched' },
    en_route: { color: 'bg-amber-500', label: 'En Route' },
    on_site: { color: 'bg-cyan-500', label: 'On Site' },
    in_progress: { color: 'bg-teal-500', label: 'In Progress' },
    completed: { color: 'bg-green-500', label: 'Completed' },
    cancelled: { color: 'bg-red-500', label: 'Cancelled' },
  };

  const { color, label } = config[status] || { color: 'bg-slate-500', label: status };

  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-slate-elevated">
      <div className="flex items-center gap-2">
        <div className={cn('w-2 h-2 rounded-full', color)} />
        <span className="text-sm text-slate-muted">{label}</span>
      </div>
      <span className="text-white font-semibold">{count}</span>
    </div>
  );
}

// Order Row
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
    scheduled: 'text-blue-400',
    dispatched: 'text-purple-400',
    en_route: 'text-amber-400',
    on_site: 'text-cyan-400',
    in_progress: 'text-teal-400',
    completed: 'text-green-400',
    cancelled: 'text-red-400',
  };

  return (
    <Link
      href={`/field-service/orders/${order.id}`}
      className="flex items-center gap-4 p-3 rounded-lg border border-slate-border hover:border-slate-border/70 hover:bg-slate-elevated/50 transition-colors"
    >
      <div className={cn('px-2 py-1 rounded text-xs font-medium', priorityColors[order.priority])}>
        {order.priority}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium truncate">{order.title}</p>
        <div className="flex items-center gap-3 text-xs text-slate-muted mt-1">
          <span>{order.order_number}</span>
          <span className="flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {order.city || 'Unknown'}
          </span>
          {order.customer_name && (
            <span>{order.customer_name}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {order.technician_name && (
          <span className="text-xs text-slate-muted">{order.technician_name}</span>
        )}
        <span className={cn('text-xs font-medium capitalize', statusColors[order.status])}>
          {order.status.replace('_', ' ')}
        </span>
        <span className="text-xs text-slate-muted">
          {order.scheduled_start_time || 'TBD'}
        </span>
      </div>
    </Link>
  );
}

export default function FieldServiceDashboard() {
  const { data: dashboard, isLoading, mutate } = useSWR(
    'field-service-dashboard',
    () => fieldServiceApi.getDashboard()
  );

  const { data: todayOrders } = useSWR(
    'field-service-today-orders',
    () => fieldServiceApi.getOrders({
      scheduled_date: new Date().toISOString().split('T')[0],
      limit: 10,
    }).then((r: any) => r.data || r)
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="h-64 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
      </div>
    );
  }

  const summary = dashboard?.summary || {};
  const byStatus = dashboard?.by_status || {};
  const byType = dashboard?.by_type || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Today's Overview</h2>
          <p className="text-sm text-slate-muted">
            {new Date().toLocaleDateString('en-NG', { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <button
          onClick={() => mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Today's Orders"
          value={summary.today_orders || 0}
          subtitle={`${summary.today_completed || 0} completed`}
          icon={ClipboardList}
          colorClass="text-blue-400"
        />
        <KPICard
          title="Unassigned"
          value={summary.unassigned || 0}
          subtitle="Need dispatch"
          icon={AlertTriangle}
          colorClass={summary.unassigned > 0 ? 'text-amber-400' : 'text-green-400'}
        />
        <KPICard
          title="Overdue"
          value={summary.overdue || 0}
          subtitle="Require attention"
          icon={Clock}
          colorClass={summary.overdue > 0 ? 'text-red-400' : 'text-green-400'}
        />
        <KPICard
          title="Completion Rate"
          value={`${summary.week_completion_rate || 0}%`}
          subtitle="This week"
          icon={TrendingUp}
          colorClass="text-teal-electric"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Today's Orders */}
        <div className="lg:col-span-2 bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <Calendar className="w-4 h-4 text-teal-electric" />
              Today's Schedule
            </h3>
            <Link
              href="/field-service/schedule"
              className="text-teal-electric text-sm flex items-center gap-1 hover:underline"
            >
              View calendar <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {todayOrders?.data?.length > 0 ? (
            <div className="space-y-2">
              {todayOrders.data.map((order: any) => (
                <OrderRow key={order.id} order={order} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-muted">
              <Calendar className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-lg mb-2">No orders scheduled for today</p>
              <Link
                href="/field-service/orders/new"
                className="text-teal-electric hover:underline"
              >
                Create a new order
              </Link>
            </div>
          )}
        </div>

        {/* Status Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-teal-electric" />
            Order Status
          </h3>
          <div className="space-y-2">
            {Object.entries(byStatus).map(([status, count]) => (
              <StatusBadge key={status} status={status} count={count as number} />
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions & Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link
          href="/field-service/schedule?view=dispatch"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-teal-electric/30 transition-colors group"
        >
          <Truck className="w-8 h-8 text-teal-electric mb-3" />
          <h4 className="text-white font-semibold mb-1">Dispatch Board</h4>
          <p className="text-sm text-slate-muted">Assign and manage technician workload</p>
        </Link>

        <Link
          href="/field-service/schedule"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-teal-electric/30 transition-colors group"
        >
          <Calendar className="w-8 h-8 text-blue-400 mb-3" />
          <h4 className="text-white font-semibold mb-1">Calendar View</h4>
          <p className="text-sm text-slate-muted">View and manage schedules</p>
        </Link>

        <Link
          href="/field-service/teams"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-teal-electric/30 transition-colors group"
        >
          <Users className="w-8 h-8 text-purple-400 mb-3" />
          <h4 className="text-white font-semibold mb-1">Field Teams</h4>
          <p className="text-sm text-slate-muted">Manage teams and technicians</p>
        </Link>

        <Link
          href="/field-service/analytics"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-teal-electric/30 transition-colors group"
        >
          <TrendingUp className="w-8 h-8 text-green-400 mb-3" />
          <h4 className="text-white font-semibold mb-1">Performance</h4>
          <p className="text-sm text-slate-muted">Analytics and reports</p>
        </Link>
      </div>

      {/* Customer Satisfaction */}
      {summary.avg_customer_rating > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Star className="w-4 h-4 text-amber-400" />
            Customer Satisfaction
          </h3>
          <div className="flex items-center gap-4">
            <div className="text-4xl font-bold text-amber-400">
              {summary.avg_customer_rating.toFixed(1)}
            </div>
            <div className="flex items-center">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  className={cn(
                    'w-6 h-6',
                    star <= Math.round(summary.avg_customer_rating)
                      ? 'text-amber-400 fill-amber-400'
                      : 'text-slate-600'
                  )}
                />
              ))}
            </div>
            <span className="text-slate-muted text-sm">Average rating</span>
          </div>
        </div>
      )}
    </div>
  );
}
