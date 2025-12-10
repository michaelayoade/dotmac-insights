'use client';

import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import { formatCurrency, formatCompactNumber } from '@/lib/utils';

const COLORS = {
  teal: '#00d4aa',
  coral: '#ff6b6b',
  amber: '#fbbf24',
  blue: '#3b82f6',
  purple: '#a855f7',
  slate: '#64748b',
};

const PIE_COLORS = [COLORS.teal, COLORS.blue, COLORS.amber, COLORS.purple, COLORS.coral];

// Custom tooltip component
function CustomTooltip({
  active,
  payload,
  label,
  valuePrefix = '',
  valueSuffix = '',
  formatValue,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
  valuePrefix?: string;
  valueSuffix?: string;
  formatValue?: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 shadow-xl">
      <p className="text-slate-muted text-xs mb-2 font-medium">{label}</p>
      {payload.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-white font-mono text-sm">
            {valuePrefix}
            {formatValue ? formatValue(item.value) : item.value.toLocaleString()}
            {valueSuffix}
          </span>
        </div>
      ))}
    </div>
  );
}

// Revenue/Area Chart
interface RevenueChartProps {
  data: Array<{ period: string; revenue: number }>;
  height?: number;
  currency?: string;
}

export function RevenueChart({ data, height = 300, currency = 'NGN' }: RevenueChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={COLORS.teal} stopOpacity={0.3} />
            <stop offset="95%" stopColor={COLORS.teal} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" vertical={false} />
        <XAxis
          dataKey="period"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickFormatter={(value) => formatCompactNumber(value)}
          dx={-10}
        />
        <Tooltip
          content={
            <CustomTooltip
              valuePrefix="₦"
              formatValue={(v) => v.toLocaleString()}
            />
          }
        />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke={COLORS.teal}
          strokeWidth={2}
          fill="url(#revenueGradient)"
          animationDuration={1500}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Churn Chart
interface ChurnChartProps {
  data: Array<{ period: string; churned: number; churned_count?: number }>;
  height?: number;
}

export function ChurnChart({ data, height = 300 }: ChurnChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" vertical={false} />
        <XAxis
          dataKey="period"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dx={-10}
        />
        <Tooltip content={<CustomTooltip valueSuffix=" customers" />} />
        <Bar
          dataKey="churned"
          fill={COLORS.coral}
          radius={[4, 4, 0, 0]}
          animationDuration={1500}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Plan Distribution Pie Chart
interface PlanPieChartProps {
  data: Array<{ plan_name: string; customer_count: number; mrr: number }>;
  height?: number;
  dataKey?: 'customer_count' | 'mrr';
}

export function PlanPieChart({ data, height = 300, dataKey = 'customer_count' }: PlanPieChartProps) {
  const total = data.reduce((sum, item) => sum + item[dataKey], 0);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          dataKey={dataKey}
          nameKey="plan_name"
          animationDuration={1500}
        >
          {data.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={PIE_COLORS[index % PIE_COLORS.length]}
              stroke="transparent"
            />
          ))}
        </Pie>
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload;
            const percentage = ((item[dataKey] / total) * 100).toFixed(1);
            return (
              <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 shadow-xl">
                <p className="text-white font-medium text-sm mb-1">{item.plan_name}</p>
                <p className="text-slate-muted text-xs">
                  {dataKey === 'customer_count'
                    ? `${item.customer_count} customers`
                    : formatCurrency(item.mrr)}
                </p>
                <p className="text-teal-electric text-xs font-mono">{percentage}%</p>
              </div>
            );
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => (
            <span className="text-slate-muted text-xs">{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// POP Performance Horizontal Bar Chart
interface PopChartProps {
  data: Array<{ name: string; mrr: number; active_customers: number }>;
  height?: number;
}

export function PopChart({ data, height = 300 }: PopChartProps) {
  // Take top 8
  const chartData = data.slice(0, 8);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" horizontal={false} />
        <XAxis
          type="number"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickFormatter={(value) => formatCompactNumber(value)}
        />
        <YAxis
          type="category"
          dataKey="name"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          width={80}
        />
        <Tooltip
          content={
            <CustomTooltip valuePrefix="₦" formatValue={(v) => v.toLocaleString()} />
          }
        />
        <Bar
          dataKey="mrr"
          fill={COLORS.teal}
          radius={[0, 4, 4, 0]}
          animationDuration={1500}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Mini sparkline for inline display
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function Sparkline({
  data,
  width = 80,
  height = 24,
  color = COLORS.teal,
}: SparklineProps) {
  const chartData = data.map((value, index) => ({ value, index }));

  return (
    <ResponsiveContainer width={width} height={height}>
      <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <defs>
          <linearGradient id="sparklineGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          fill="url(#sparklineGradient)"
          animationDuration={1000}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// DSO (Days Sales Outstanding) Chart
interface DSOChartProps {
  data: Array<{ period: string; dso: number }>;
  height?: number;
  avgDSO?: number;
}

export function DSOChart({ data, height = 300, avgDSO }: DSOChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="dsoGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={COLORS.amber} stopOpacity={0.3} />
            <stop offset="95%" stopColor={COLORS.amber} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" vertical={false} />
        <XAxis
          dataKey="period"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dx={-10}
          domain={[0, 'auto']}
        />
        <Tooltip
          content={
            <CustomTooltip
              valueSuffix=" days"
              formatValue={(v) => v.toFixed(1)}
            />
          }
        />
        {avgDSO && (
          <ReferenceLine y={avgDSO} stroke={COLORS.slate} strokeDasharray="5 5" />
        )}
        <Area
          type="monotone"
          dataKey="dso"
          stroke={COLORS.amber}
          strokeWidth={2}
          fill="url(#dsoGradient)"
          animationDuration={1500}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// SLA Gauge Chart (using Pie as radial gauge)
interface SLAGaugeProps {
  value: number;
  size?: number;
}

export function SLAGauge({ value, size = 200 }: SLAGaugeProps) {
  const data = [
    { name: 'Met', value: value },
    { name: 'Missed', value: 100 - value },
  ];

  const color = value >= 90 ? COLORS.teal : value >= 70 ? COLORS.amber : COLORS.coral;

  return (
    <div className="relative" style={{ width: size, height: size / 2 + 20 }}>
      <ResponsiveContainer width="100%" height={size / 2 + 20}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="100%"
            startAngle={180}
            endAngle={0}
            innerRadius={size * 0.3}
            outerRadius={size * 0.45}
            paddingAngle={0}
            dataKey="value"
          >
            <Cell fill={color} />
            <Cell fill="#2d3a4f" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div
        className="absolute inset-0 flex flex-col items-center justify-end pb-2"
        style={{ height: size / 2 + 20 }}
      >
        <span className="font-mono text-2xl font-bold text-white">{value.toFixed(1)}%</span>
        <span className="text-slate-muted text-xs">SLA Attainment</span>
      </div>
    </div>
  );
}

// Sales Funnel Chart
interface FunnelStage {
  name: string;
  value: number;
  fill: string;
}

interface FunnelChartProps {
  data: FunnelStage[];
  height?: number;
}

export function FunnelChart({ data, height = 300 }: FunnelChartProps) {
  const maxValue = Math.max(...data.map(d => d.value));

  return (
    <div className="space-y-3" style={{ height }}>
      {data.map((stage, index) => {
        const width = maxValue > 0 ? (stage.value / maxValue) * 100 : 0;
        const conversionRate = index > 0 && data[index - 1].value > 0
          ? ((stage.value / data[index - 1].value) * 100).toFixed(1)
          : null;

        return (
          <div key={stage.name} className="relative">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-slate-muted">{stage.name}</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-white">{stage.value.toLocaleString()}</span>
                {conversionRate && (
                  <span className="text-xs text-slate-muted">({conversionRate}%)</span>
                )}
              </div>
            </div>
            <div className="h-8 bg-slate-elevated rounded overflow-hidden relative">
              <div
                className="h-full rounded transition-all duration-700 ease-out"
                style={{
                  width: `${width}%`,
                  backgroundColor: stage.fill,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Horizontal Bar Chart for Agent Productivity
interface AgentBarChartProps {
  data: Array<{ name: string; resolved: number; total_tickets: number }>;
  height?: number;
}

export function AgentBarChart({ data, height = 300 }: AgentBarChartProps) {
  const chartData = data.slice(0, 8);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" horizontal={false} />
        <XAxis
          type="number"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
        />
        <YAxis
          type="category"
          dataKey="name"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          width={100}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload;
            return (
              <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 shadow-xl">
                <p className="text-white font-medium text-sm mb-1">{item.name}</p>
                <p className="text-teal-electric text-sm">Resolved: {item.resolved}</p>
                <p className="text-slate-muted text-sm">Total: {item.total_tickets}</p>
              </div>
            );
          }}
        />
        <Bar dataKey="resolved" fill={COLORS.teal} radius={[0, 4, 4, 0]} animationDuration={1500} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Expense Trend Line Chart
interface ExpenseTrendChartProps {
  data: Array<{ period: string; total: number }>;
  height?: number;
}

export function ExpenseTrendChart({ data, height = 300 }: ExpenseTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="expenseGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={COLORS.purple} stopOpacity={0.3} />
            <stop offset="95%" stopColor={COLORS.purple} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" vertical={false} />
        <XAxis
          dataKey="period"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickFormatter={(value) => formatCompactNumber(value)}
          dx={-10}
        />
        <Tooltip
          content={
            <CustomTooltip
              valuePrefix="N"
              formatValue={(v) => v.toLocaleString()}
            />
          }
        />
        <Area
          type="monotone"
          dataKey="total"
          stroke={COLORS.purple}
          strokeWidth={2}
          fill="url(#expenseGradient)"
          animationDuration={1500}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
