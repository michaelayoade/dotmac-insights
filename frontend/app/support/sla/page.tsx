'use client';

import { useState } from 'react';
import { AlertTriangle, Calendar, Clock, ShieldCheck, Target, Filter } from 'lucide-react';
import { useSupportSlaBreachesSummary, useSupportSlaCalendars, useSupportSlaPolicies, useSupportAnalyticsSlaPerformance } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { PageHeader, Select } from '@/components/ui';

function ProgressBar({ value, max, color = 'bg-teal-electric' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SlaGauge({ attainment }: { attainment: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (attainment / 100) * circumference;
  const color = attainment >= 90 ? '#10B981' : attainment >= 70 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative w-28 h-28 mx-auto">
      <svg className="w-full h-full -rotate-90">
        <circle cx="56" cy="56" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{attainment.toFixed(0)}%</span>
        <span className="text-[10px] text-slate-muted">Attainment</span>
      </div>
    </div>
  );
}

export default function SupportSlaPage() {
  const [activeOnly, setActiveOnly] = useState(true);
  const [days, setDays] = useState(30);
  const calendars = useSupportSlaCalendars({ active_only: activeOnly });
  const policies = useSupportSlaPolicies({ active_only: activeOnly });
  const breaches = useSupportSlaBreachesSummary({ days });
  const slaPerformance = useSupportAnalyticsSlaPerformance({ months: 6 });
  const breachData = breaches.data || {};
  const breachTargets = Array.isArray((breachData as any).by_target_type) ? (breachData as any).by_target_type : [];
  const calendarsData = Array.isArray(calendars.data) ? calendars.data : [];
  const policiesData = Array.isArray(policies.data) ? policies.data : [];

  // Calculate overall attainment from latest month
  const latestPerf = slaPerformance.data?.[slaPerformance.data.length - 1];
  const overallAttainment = latestPerf?.attainment_rate ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="SLA Management"
        subtitle="Calendars, policies, and breach summary"
        icon={ShieldCheck}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
      />

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2 text-slate-muted text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="rounded"
            />
            Active only
          </label>
          <div>
            <label className="text-xs text-slate-muted mb-1 block">Breach window</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
        </div>
      </div>

      {/* SLA Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Overall Attainment Gauge */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-emerald-400" />
            <h3 className="text-white font-semibold">SLA Attainment</h3>
          </div>
          <SlaGauge attainment={overallAttainment} />
          {latestPerf && (
            <div className="mt-4 grid grid-cols-2 gap-3 text-center">
              <div>
                <p className="text-xs text-slate-muted">Met</p>
                <p className="text-lg font-bold text-emerald-400">{latestPerf.met}</p>
              </div>
              <div>
                <p className="text-xs text-slate-muted">Breached</p>
                <p className="text-lg font-bold text-rose-400">{latestPerf.breached}</p>
              </div>
            </div>
          )}
        </div>

        {/* Breach Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 md:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Breach Summary ({days}d)</h3>
          </div>
          {!breaches.data ? (
            <p className="text-slate-muted text-sm">Loading breach data…</p>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-rose-400">{breachData.total_breaches ?? 0}</p>
                  <p className="text-xs text-slate-muted">Total Breaches</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-400">{breachData.currently_overdue ?? 0}</p>
                  <p className="text-xs text-slate-muted">Currently Overdue</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-violet-400">
                    {breachTargets.reduce((s: number, t: any) => s + (t.avg_overrun_hours || 0), 0).toFixed(1)}h
                  </p>
                  <p className="text-xs text-slate-muted">Avg Overrun</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-blue-400">
                    {breachTargets.length}
                  </p>
                  <p className="text-xs text-slate-muted">Target Types</p>
                </div>
              </div>

              {breachTargets.length > 0 && (
                <div className="space-y-2 pt-3 border-t border-slate-border">
                  <p className="text-xs text-slate-muted">By Target Type</p>
                  {breachTargets.map((row: any, idx: number) => (
                    <div key={idx} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-white">{row.target_type || 'Unknown'}</span>
                        <span className="text-slate-muted">
                          {row.count} breaches • avg {row.avg_overrun_hours?.toFixed?.(1) ?? 0}h
                        </span>
                      </div>
                      <ProgressBar
                        value={row.count}
                        max={breachData.total_breaches || 1}
                        color="bg-rose-500"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* SLA Trend */}
      {slaPerformance.data?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">SLA Performance Trend (6 months)</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {slaPerformance.data.map((perf) => (
              <div key={perf.period} className="bg-slate-elevated rounded-lg p-3 text-center">
                <p className="text-xs text-slate-muted mb-1">{perf.period}</p>
                <p className={cn(
                  'text-lg font-bold',
                  perf.attainment_rate >= 90 ? 'text-emerald-400' :
                  perf.attainment_rate >= 70 ? 'text-amber-400' : 'text-rose-400'
                )}>
                  {perf.attainment_rate.toFixed(0)}%
                </p>
                <div className="flex items-center justify-center gap-2 mt-1 text-xs">
                  <span className="text-emerald-400">{perf.met}</span>
                  <span className="text-slate-muted">/</span>
                  <span className="text-rose-400">{perf.breached}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Calendars & Policies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Calendars */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-blue-400" />
                <h3 className="text-white font-semibold">Business Calendars</h3>
              </div>
              <span className="text-xs text-slate-muted">{calendarsData.length} calendars</span>
            </div>
          {!calendars.data ? (
            <p className="text-slate-muted text-sm">Loading calendars…</p>
          ) : calendarsData.length === 0 ? (
            <p className="text-slate-muted text-sm">No calendars configured.</p>
          ) : (
            <div className="space-y-3">
              {calendarsData.map((cal) => (
                <div key={cal.id} className="border border-slate-border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-white font-semibold">{cal.name}</p>
                      <p className="text-slate-muted text-xs mt-0.5">{cal.description || cal.calendar_type}</p>
                    </div>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs',
                      cal.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-elevated text-slate-muted'
                    )}>
                      {cal.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-xs text-slate-muted">
                    <span className="px-2 py-1 rounded bg-slate-elevated">{cal.timezone}</span>
                    {Array.isArray(cal.holidays) && cal.holidays.length > 0 && (
                      <span>{cal.holidays.length} holidays</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Policies */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-violet-400" />
              <h3 className="text-white font-semibold">SLA Policies</h3>
            </div>
            <span className="text-xs text-slate-muted">{policiesData.length} policies</span>
          </div>
          {!policies.data ? (
            <p className="text-slate-muted text-sm">Loading policies…</p>
          ) : policiesData.length === 0 ? (
            <p className="text-slate-muted text-sm">No policies configured.</p>
          ) : (
            <div className="space-y-3">
              {policiesData.map((policy) => {
                const targets = Array.isArray(policy.targets) ? policy.targets : [];
                const conditions = Array.isArray(policy.conditions) ? policy.conditions : [];
                return (
                <div key={policy.id} className="border border-slate-border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-white font-semibold">{policy.name}</p>
                      <p className="text-slate-muted text-xs mt-0.5">{policy.description || 'No description'}</p>
                    </div>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs',
                      policy.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-elevated text-slate-muted'
                    )}>
                      {policy.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-muted">
                    {conditions.length ? (
                      <span className="px-2 py-1 rounded bg-slate-elevated">
                        {conditions.length} conditions
                      </span>
                    ) : null}
                    {targets.length ? (
                      <span className="px-2 py-1 rounded bg-slate-elevated">
                        {targets.length} targets
                      </span>
                    ) : null}
                    {policy.priority !== undefined && (
                      <span className="px-2 py-1 rounded bg-slate-elevated">
                        Priority: {policy.priority}
                      </span>
                    )}
                  </div>
                  {targets.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-slate-border/50 space-y-1">
                      {targets.slice(0, 3).map((target: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="text-slate-muted">{target.target_type || 'Target'}</span>
                          <span className="text-white">{target.target_hours}h</span>
                        </div>
                      ))}
                      {targets.length > 3 && (
                        <p className="text-xs text-slate-muted">+{targets.length - 3} more targets</p>
                      )}
                    </div>
                  )}
                </div>
              );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
