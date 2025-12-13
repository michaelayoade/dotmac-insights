'use client';

import React from 'react';
import { formatCurrency, formatPercent, cn } from '@/lib/utils';

type BasicChartProps = {
  data?: any;
  height?: number;
  currency?: string;
};

function ChartShell({ title, height = 240, children }: { title: string; height?: number; children?: React.ReactNode }) {
  return (
    <div
      className="border border-slate-border rounded-lg bg-slate-elevated text-slate-muted flex flex-col"
      style={{ minHeight: height }}
    >
      <div className="px-3 py-2 border-b border-slate-border text-xs uppercase tracking-[0.08em]">{title}</div>
      <div className="flex-1 px-4 py-3 flex items-center justify-center">{children || <span>Chart placeholder</span>}</div>
    </div>
  );
}

export function RevenueChart({ data, height = 240, currency = 'NGN' }: BasicChartProps) {
  const latest = data?.[data.length - 1];
  return (
    <ChartShell title="Revenue" height={height}>
      <div className="text-center space-y-1">
        <p className="text-xs text-slate-muted">Latest</p>
        <p className="text-2xl font-semibold text-white">{formatCurrency(latest?.total || 0, currency)}</p>
      </div>
    </ChartShell>
  );
}

export function ChurnChart({ data, height = 240 }: BasicChartProps) {
  const avg = data?.length ? data.reduce((s: number, m: any) => s + (m.churned || m.churned_count || 0), 0) / data.length : 0;
  return (
    <ChartShell title="Churn" height={height}>
      <div className="text-center space-y-1">
        <p className="text-xs text-slate-muted">Avg churn</p>
        <p className="text-2xl font-semibold text-white">{avg.toFixed(1)}</p>
      </div>
    </ChartShell>
  );
}

export function DSOChart({ data, height = 240 }: BasicChartProps) {
  const current = data?.current_dso;
  return (
    <ChartShell title="DSO" height={height}>
      <div className="text-center space-y-1">
        <p className="text-xs text-slate-muted">Days Sales Outstanding</p>
        <p className="text-2xl font-semibold text-white">{current ? `${current.toFixed(1)} days` : '—'}</p>
      </div>
    </ChartShell>
  );
}

export function SLAGauge({ data, height = 240 }: BasicChartProps) {
  const rate = data?.sla_attainment?.rate ? formatPercent(data.sla_attainment.rate) : '—';
  return (
    <ChartShell title="SLA Attainment" height={height}>
      <div className="text-center space-y-1">
        <p className="text-2xl font-semibold text-white">{rate}</p>
        <p className="text-xs text-slate-muted">Met: {data?.sla_attainment?.met ?? 0}</p>
      </div>
    </ChartShell>
  );
}

export function FunnelChart({ data, height = 240 }: BasicChartProps) {
  const steps = Array.isArray(data) ? data : [];
  return (
    <ChartShell title="Funnel" height={height}>
      <div className="flex flex-col gap-2 w-full">
        {steps.map((step: any) => (
          <div key={step.name} className="flex items-center justify-between rounded-md bg-slate-card px-3 py-2">
            <span className="text-sm text-white">{step.name}</span>
            <span className="font-mono text-teal-electric">{step.value ?? 0}</span>
          </div>
        ))}
        {!steps.length && <span className="text-slate-muted text-sm text-center w-full">No funnel data</span>}
      </div>
    </ChartShell>
  );
}

export function AgentBarChart({ data, height = 240 }: BasicChartProps) {
  const top = Array.isArray(data) ? data.slice(0, 5) : [];
  return (
    <ChartShell title="Agent Productivity" height={height}>
      <div className="flex flex-col gap-2 w-full">
        {top.map((agent: any) => (
          <div key={agent.name || agent.agent} className="flex items-center justify-between text-sm">
            <span className="text-white">{agent.name || agent.agent}</span>
            <span className="font-mono text-teal-electric">{agent.count || agent.closed || 0}</span>
          </div>
        ))}
        {!top.length && <span className="text-slate-muted text-sm text-center w-full">No agent data</span>}
      </div>
    </ChartShell>
  );
}

export function ExpenseTrendChart({ data, height = 240, currency = 'NGN' }: BasicChartProps) {
  const latest = data?.[data.length - 1];
  return (
    <ChartShell title="Expenses" height={height}>
      <div className="text-center space-y-1">
        <p className="text-xs text-slate-muted">Latest total</p>
        <p className="text-2xl font-semibold text-white">{formatCurrency(latest?.total || 0, currency)}</p>
      </div>
    </ChartShell>
  );
}

export function PopChart({ data, height = 240 }: BasicChartProps) {
  const top = Array.isArray(data) ? data.slice(0, 5) : [];
  return (
    <ChartShell title="POP Performance" height={height}>
      <div className="flex flex-col gap-2 w-full">
        {top.map((pop: any) => (
          <div key={pop.id || pop.name} className="flex items-center justify-between text-sm">
            <span className="text-white">{pop.name || pop.id}</span>
            <span className={cn('font-mono', (pop.churn_rate || 0) > 5 ? 'text-coral-alert' : 'text-teal-electric')}>
              {formatPercent(pop.churn_rate || 0)}
            </span>
          </div>
        ))}
        {!top.length && <span className="text-slate-muted text-sm text-center w-full">No POP data</span>}
      </div>
    </ChartShell>
  );
}
