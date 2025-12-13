'use client';

import { useState } from 'react';
import { AlertTriangle, Calendar, Clock, ShieldCheck } from 'lucide-react';
import { useSupportSlaBreachesSummary, useSupportSlaCalendars, useSupportSlaPolicies } from '@/hooks/useApi';

export default function SupportSlaPage() {
  const [activeOnly, setActiveOnly] = useState(true);
  const calendars = useSupportSlaCalendars({ active_only: activeOnly });
  const policies = useSupportSlaPolicies({ active_only: activeOnly });
  const breaches = useSupportSlaBreachesSummary({ days: 30 });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">SLA</h1>
          <p className="text-slate-muted text-sm">Calendars, policies, and breach summary</p>
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm text-slate-muted">
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={activeOnly} onChange={(e) => policies.mutate && setActiveOnly(e.target.checked)} />
          Active only
        </label>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Business calendars</span>
          </div>
          {!calendars.data ? (
            <p className="text-slate-muted text-sm">Loading calendars…</p>
          ) : calendars.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No calendars found.</p>
          ) : (
            <div className="space-y-2">
              {calendars.data.map((cal) => (
                <div key={cal.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-white font-semibold">{cal.name}</p>
                      <p className="text-slate-muted text-xs">{cal.description || cal.calendar_type}</p>
                    </div>
                    <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">{cal.timezone}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Policies</span>
          </div>
          {!policies.data ? (
            <p className="text-slate-muted text-sm">Loading policies…</p>
          ) : policies.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No policies found.</p>
          ) : (
            <div className="space-y-2">
              {policies.data.map((policy) => (
                <div key={policy.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-white font-semibold">{policy.name}</p>
                      <p className="text-slate-muted text-xs">{policy.description || 'No description'}</p>
                    </div>
                    {policy.conditions?.length ? (
                      <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">
                        {policy.conditions.length} conditions
                      </span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span className="text-white text-sm font-medium">Breach summary (30d)</span>
        </div>
        {!breaches.data ? (
          <p className="text-slate-muted text-sm">Loading breaches…</p>
        ) : (
          <div className="text-sm text-slate-muted space-y-1">
            <p>Total breaches: {breaches.data.total_breaches ?? 0}</p>
            <div className="space-y-1">
              {(breaches.data.by_target_type || []).map((row, idx) => (
                <p key={idx}>{row.target_type}: {row.count} (avg overrun {row.avg_overrun_hours?.toFixed?.(1) ?? 0}h)</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
