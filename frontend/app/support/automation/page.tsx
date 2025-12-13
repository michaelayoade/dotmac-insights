'use client';

import { useState } from 'react';
import { AlertTriangle, Filter, PlayCircle, ShieldCheck } from 'lucide-react';
import { useSupportAutomationLogs, useSupportAutomationLogsSummary, useSupportAutomationRules } from '@/hooks/useApi';

export default function SupportAutomationPage() {
  const [trigger, setTrigger] = useState('');
  const rules = useSupportAutomationRules(trigger ? { trigger } : undefined);
  const logs = useSupportAutomationLogs(undefined, { dedupingInterval: 60000 });
  const summary = useSupportAutomationLogsSummary(undefined, { dedupingInterval: 60000 });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">Automation</h1>
          <p className="text-slate-muted text-sm">Rules, triggers, and execution logs</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filter by trigger</span>
        </div>
        <select
          value={trigger}
          onChange={(e) => setTrigger(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All triggers</option>
          {logs.data?.data?.map((l) => l.trigger).filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <PlayCircle className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Rules</span>
        </div>
        {rules.error && (
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Failed to load rules
          </div>
        )}
        {!rules.data ? (
          <p className="text-slate-muted text-sm">Loading rules…</p>
        ) : rules.data.length === 0 ? (
          <p className="text-slate-muted text-sm">No automation rules.</p>
        ) : (
          <div className="space-y-2">
            {rules.data.map((rule) => (
              <div key={rule.id} className="border border-slate-border rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">{rule.name}</p>
                    <p className="text-slate-muted text-xs">{rule.description || 'No description'}</p>
                  </div>
                  <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">{rule.trigger}</span>
                </div>
                <p className="text-xs text-slate-muted mt-1">
                  Actions: {(rule.actions || []).length} • Conditions: {(rule.conditions || []).length}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Execution summary (7d)</span>
          </div>
          {!summary.data ? (
            <p className="text-slate-muted text-sm">Loading summary…</p>
          ) : (
            <div className="text-sm text-slate-muted space-y-1">
              <p>Total executions: {summary.data.total_executions ?? 0}</p>
              <p>Successful: {summary.data.successful_executions ?? 0}</p>
              <p>Success rate: {(summary.data.success_rate ?? 0).toFixed?.(1) ?? '0'}%</p>
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ActivitySquare className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Recent logs</span>
          </div>
          {!logs.data ? (
            <p className="text-slate-muted text-sm">Loading logs…</p>
          ) : logs.data.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No logs found.</p>
          ) : (
            <div className="space-y-2">
              {logs.data.data.slice(0, 10).map((log) => (
                <div key={log.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white font-medium">{log.trigger}</span>
                    <span className={log.success ? 'text-emerald-400 text-xs' : 'text-red-400 text-xs'}>
                      {log.success ? 'Success' : 'Failed'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-muted">Rule: {log.rule_name || log.rule_id}</p>
                  <p className="text-xs text-slate-muted">Ticket: {log.ticket_id}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
