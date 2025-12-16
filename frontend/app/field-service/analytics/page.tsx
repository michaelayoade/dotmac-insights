'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle2,
  XCircle,
  Star,
  Users,
  Calendar,
  DollarSign,
  Target,
  Activity,
  MapPin,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

// Simple bar chart component
function BarChart({ data, height = 200 }: { data: { label: string; value: number; color?: string }[]; height?: number }) {
  const maxValue = Math.max(...data.map(d => d.value), 1);

  return (
    <div className="flex items-end gap-2" style={{ height }}>
      {data.map((item, idx) => (
        <div key={idx} className="flex-1 flex flex-col items-center gap-2">
          <div
            className={cn('w-full rounded-t transition-all', item.color || 'bg-teal-electric')}
            style={{ height: `${(item.value / maxValue) * 100}%`, minHeight: item.value > 0 ? '4px' : '0' }}
          />
          <span className="text-xs text-slate-muted truncate max-w-full">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// KPI Card
function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  colorClass = 'text-teal-electric',
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: { value: number; label: string };
  colorClass?: string;
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
            'text-xs font-medium px-2 py-1 rounded flex items-center gap-1',
            trend.value >= 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          )}>
            {trend.value >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {Math.abs(trend.value)}% {trend.label}
          </div>
        )}
      </div>
    </div>
  );
}

export default function FieldServiceAnalyticsPage() {
  const [period, setPeriod] = useState<'week' | 'month' | 'quarter' | 'year'>('month');

  const { data: metrics, isLoading } = useSWR(
    ['field-service-analytics', period],
    () => api.get('/field-service/analytics/dashboard', {
      params: { period }
    }).then(r => r.data)
  );

  const { data: techPerformance } = useSWR(
    ['field-service-tech-performance', period],
    () => api.get('/field-service/analytics/technician-performance', {
      params: { period }
    }).then(r => r.data)
  );

  const { data: typeBreakdown } = useSWR(
    ['field-service-type-breakdown', period],
    () => api.get('/field-service/analytics/order-type-breakdown', {
      params: { period }
    }).then(r => r.data)
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

  const stats = metrics?.summary || {};
  const dailyTrend = metrics?.daily_trend || [];
  const statusDistribution = metrics?.status_distribution || {};
  const topTechnicians = techPerformance?.data || [];
  const orderTypes = typeBreakdown?.data || [];

  // Prepare chart data
  const trendData = dailyTrend.slice(-7).map((day: any) => ({
    label: new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' }),
    value: day.completed || 0,
    color: 'bg-teal-electric',
  }));

  const typeData = orderTypes.slice(0, 6).map((type: any) => ({
    label: type.order_type?.replace('_', ' ') || 'Other',
    value: type.count || 0,
    color: 'bg-blue-500',
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Analytics</h2>
          <p className="text-sm text-slate-muted">Field service performance metrics</p>
        </div>
        <div className="flex items-center bg-slate-elevated border border-slate-border rounded-lg p-1">
          {(['week', 'month', 'quarter', 'year'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                'px-4 py-1.5 rounded text-sm capitalize transition-colors',
                period === p
                  ? 'bg-teal-electric text-slate-950'
                  : 'text-slate-muted hover:text-white'
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Total Orders"
          value={stats.total_orders || 0}
          subtitle={`${stats.completed_orders || 0} completed`}
          icon={BarChart3}
          colorClass="text-blue-400"
          trend={stats.orders_trend ? { value: stats.orders_trend, label: 'vs prev' } : undefined}
        />
        <KPICard
          title="Completion Rate"
          value={`${stats.completion_rate || 0}%`}
          subtitle="On-time completion"
          icon={Target}
          colorClass={stats.completion_rate >= 80 ? 'text-green-400' : 'text-amber-400'}
        />
        <KPICard
          title="Avg Response Time"
          value={stats.avg_response_time ? `${Math.round(stats.avg_response_time)}m` : 'N/A'}
          subtitle="First response"
          icon={Clock}
          colorClass="text-purple-400"
        />
        <KPICard
          title="Customer Rating"
          value={stats.avg_rating?.toFixed(1) || 'N/A'}
          subtitle={`${stats.total_ratings || 0} reviews`}
          icon={Star}
          colorClass="text-amber-400"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Completion Trend */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-6 flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-electric" />
            Completion Trend (Last 7 Days)
          </h3>
          {trendData.length > 0 ? (
            <BarChart data={trendData} height={180} />
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted">
              No data available
            </div>
          )}
        </div>

        {/* Order Types */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-6 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-teal-electric" />
            Orders by Type
          </h3>
          {typeData.length > 0 ? (
            <BarChart data={typeData} height={180} />
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-muted">
              No data available
            </div>
          )}
        </div>
      </div>

      {/* Status & Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-electric" />
            Status Distribution
          </h3>
          <div className="space-y-3">
            {Object.entries(statusDistribution).map(([status, count]) => {
              const total = Object.values(statusDistribution).reduce((a: any, b: any) => a + b, 0) as number;
              const percentage = total > 0 ? ((count as number) / total) * 100 : 0;

              const colors: Record<string, string> = {
                completed: 'bg-green-500',
                in_progress: 'bg-teal-500',
                scheduled: 'bg-blue-500',
                cancelled: 'bg-red-500',
                draft: 'bg-slate-500',
              };

              return (
                <div key={status}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-muted capitalize">{status.replace('_', ' ')}</span>
                    <span className="text-white">{count as number}</span>
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', colors[status] || 'bg-slate-400')}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top Technicians */}
        <div className="lg:col-span-2 bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            Top Performing Technicians
          </h3>
          {topTechnicians.length > 0 ? (
            <div className="space-y-3">
              {topTechnicians.slice(0, 5).map((tech: any, idx: number) => (
                <div
                  key={tech.id || idx}
                  className="flex items-center gap-4 p-3 rounded-lg bg-slate-elevated"
                >
                  <div className="w-8 h-8 rounded-full bg-slate-card flex items-center justify-center text-white font-bold text-sm">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <p className="text-white font-medium">{tech.name}</p>
                    <p className="text-xs text-slate-muted">{tech.team_name || 'No team'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-semibold">{tech.completed_orders || 0}</p>
                    <p className="text-xs text-slate-muted">orders</p>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-amber-400">
                      <Star className="w-4 h-4 fill-amber-400" />
                      <span className="font-semibold">{tech.avg_rating?.toFixed(1) || 'N/A'}</span>
                    </div>
                    <p className="text-xs text-slate-muted">rating</p>
                  </div>
                  <div className="text-right">
                    <p className={cn(
                      'font-semibold',
                      (tech.completion_rate || 0) >= 90 ? 'text-green-400' :
                      (tech.completion_rate || 0) >= 70 ? 'text-amber-400' : 'text-red-400'
                    )}>
                      {tech.completion_rate || 0}%
                    </p>
                    <p className="text-xs text-slate-muted">rate</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-center py-8">No data available</p>
          )}
        </div>
      </div>

      {/* Additional Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-2">
            <Clock className="w-4 h-4" />
            Avg Service Time
          </div>
          <p className="text-2xl font-bold text-white">
            {stats.avg_service_duration ? `${Math.round(stats.avg_service_duration)}m` : 'N/A'}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-2">
            <MapPin className="w-4 h-4" />
            Avg Travel Time
          </div>
          <p className="text-2xl font-bold text-white">
            {stats.avg_travel_time ? `${Math.round(stats.avg_travel_time)}m` : 'N/A'}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            Total Revenue
          </div>
          <p className="text-2xl font-bold text-white">
            ₦{(stats.total_revenue || 0).toLocaleString()}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-2">
            <XCircle className="w-4 h-4" />
            Cancellation Rate
          </div>
          <p className={cn(
            'text-2xl font-bold',
            (stats.cancellation_rate || 0) <= 5 ? 'text-green-400' :
            (stats.cancellation_rate || 0) <= 10 ? 'text-amber-400' : 'text-red-400'
          )}>
            {stats.cancellation_rate || 0}%
          </p>
        </div>
      </div>
    </div>
  );
}
