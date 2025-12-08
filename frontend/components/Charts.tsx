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
  data: Array<{ period: string; churned_count: number }>;
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
          dataKey="churned_count"
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
