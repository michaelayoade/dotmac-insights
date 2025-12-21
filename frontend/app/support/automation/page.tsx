'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Filter, PlayCircle, Zap, Activity, CheckCircle, XCircle, LifeBuoy } from 'lucide-react';
import { useSupportAutomationLogs, useSupportAutomationLogsSummary, useSupportAutomationRules } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { PageHeader, Select, StatGrid } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

function formatDate(value?: string | null) {
  if (!value) return '-';
  const dt = new Date(value);
  return dt.toLocaleString('en-NG', { dateStyle: 'short', timeStyle: 'short' });
}

export default function SupportAutomationPage() {
  const [trigger, setTrigger] = useState('');
  const rules = useSupportAutomationRules(trigger ? { trigger } : undefined);
  const logs = useSupportAutomationLogs(undefined, { dedupingInterval: 60000 });
  const summary = useSupportAutomationLogsSummary(undefined, { dedupingInterval: 60000 });

  // Get unique triggers from logs
  const triggers: string[] = Array.from(
    new Set(
      ((logs.data?.data as Array<{ trigger?: string | null }> | undefined) || [])
        .map((l) => l.trigger || '')
        .filter((t) => !!t)
    )
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automation"
        subtitle="Rules, triggers, and execution logs"
        icon={Zap}
        iconClassName="bg-purple-500/10 border border-purple-500/30"
      />

      {/* Summary Cards */}
      {summary.data && (
        <StatGrid columns={4}>
          <StatCard
            title="Total Executions (7d)"
            value={summary.data.total_executions ?? 0}
            icon={Activity}
          />
          <StatCard
            title="Successful"
            value={summary.data.successful_executions ?? 0}
            icon={CheckCircle}
            variant="success"
          />
          <StatCard
            title="Failed"
            value={(summary.data.total_executions ?? 0) - (summary.data.successful_executions ?? 0)}
            icon={XCircle}
            variant="danger"
          />
          <StatCard
            title="Success Rate"
            value={`${(summary.data.success_rate ?? 0).toFixed(1)}%`}
            variant={(summary.data.success_rate ?? 0) >= 90 ? 'success' : (summary.data.success_rate ?? 0) >= 70 ? 'warning' : 'danger'}
          />
        </StatGrid>
      )}

      {/* Filter */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-foreground text-sm font-medium">Filter by trigger</span>
        </div>
        <select
          value={trigger}
          onChange={(e) => setTrigger(e.target.value || '')}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50 min-w-[200px]"
        >
          <option value="">All triggers</option>
          {triggers.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Rules */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <PlayCircle className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Automation Rules</h3>
          </div>
          <span className="text-xs text-slate-muted">{Array.isArray(rules.data) ? rules.data.length : 0} rules</span>
        </div>
        {rules.error && (
          <div className="text-red-400 text-sm flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4" /> Failed to load rules
          </div>
        )}
        {!rules.data ? (
          <p className="text-slate-muted text-sm">Loading rules…</p>
        ) : !Array.isArray(rules.data) || rules.data.length === 0 ? (
          <p className="text-slate-muted text-sm">No automation rules configured.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {rules.data.map((rule) => (
              <div key={rule.id} className="border border-slate-border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-foreground font-semibold">{rule.name}</p>
                    <p className="text-slate-muted text-xs mt-0.5">{rule.description || 'No description'}</p>
                  </div>
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs',
                    rule.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-elevated text-slate-muted'
                  )}>
                    {rule.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs text-slate-muted">
                  <span className="px-2 py-1 rounded bg-slate-elevated">{rule.trigger}</span>
                  <span>Actions: {Array.isArray(rule.actions) ? rule.actions.length : 0}</span>
                  <span>Conditions: {Array.isArray(rule.conditions) ? rule.conditions.length : 0}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Logs */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h3 className="text-foreground font-semibold">Recent Execution Logs</h3>
          </div>
          <span className="text-xs text-slate-muted">{Array.isArray(logs.data?.data) ? logs.data?.data.length : 0} logs</span>
        </div>
        {!logs.data ? (
          <p className="text-slate-muted text-sm">Loading logs…</p>
        ) : !Array.isArray(logs.data.data) || logs.data.data.length === 0 ? (
          <p className="text-slate-muted text-sm">No execution logs found.</p>
        ) : (
          <div className="space-y-2">
            {logs.data.data.slice(0, 15).map((log: any) => (
              <div key={log.id} className="border border-slate-border rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {log.success ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400" />
                    )}
                    <div>
                      <p className="text-foreground font-medium">{log.rule_name || `Rule #${log.rule_id}`}</p>
                      <p className="text-slate-muted text-xs">Trigger: {log.trigger}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs',
                      log.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                    )}>
                      {log.success ? 'Success' : 'Failed'}
                    </span>
                    <p className="text-slate-muted text-xs mt-1">{formatDate(log.executed_at)}</p>
                  </div>
                </div>
                {log.ticket_id && (
                  <div className="mt-2 pt-2 border-t border-slate-border/50 flex items-center gap-2">
                    <LifeBuoy className="w-3 h-3 text-slate-muted" />
                    <Link
                      href={`/support/tickets/${log.ticket_id}`}
                      className="text-teal-electric text-xs hover:underline"
                    >
                      {log.ticket_number || `Ticket #${log.ticket_id}`}
                    </Link>
                  </div>
                )}
                {log.error_message && (
                  <div className="mt-2 pt-2 border-t border-slate-border/50">
                    <p className="text-rose-400 text-xs">{log.error_message}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
