'use client';

import { useState } from 'react';
import { AlertTriangle, BarChart3, Network } from 'lucide-react';
import { useSupportRoutingQueueHealth, useSupportRoutingRules, useSupportRoutingWorkload } from '@/hooks/useApi';

export default function SupportRoutingPage() {
  const [teamId, setTeamId] = useState<string>('');
  const rules = useSupportRoutingRules(teamId ? { team_id: Number(teamId) } : undefined);
  const queue = useSupportRoutingQueueHealth();
  const workload = useSupportRoutingWorkload(teamId ? Number(teamId) : undefined);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Network className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">Routing</h1>
          <p className="text-slate-muted text-sm">Rules, workload, and queue health</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <label className="text-sm text-slate-muted">Team ID (optional)</label>
        <input
          value={teamId}
          onChange={(e) => setTeamId(e.target.value)}
          placeholder="Filter by team"
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Rules</span>
          </div>
          {!rules.data ? (
            <p className="text-slate-muted text-sm">Loading rules…</p>
          ) : rules.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No routing rules.</p>
          ) : (
            <div className="space-y-2">
              {rules.data.map((rule) => (
                <div key={rule.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-white font-semibold">{rule.name}</p>
                      <p className="text-slate-muted text-xs">{rule.description || 'No description'}</p>
                    </div>
                    <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">
                      {rule.strategy}
                    </span>
                  </div>
                  <p className="text-xs text-slate-muted">Team: {rule.team_id || 'Any'} • Priority: {rule.priority ?? 100}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span className="text-white text-sm font-medium">Queue health</span>
          </div>
          {!queue.data ? (
            <p className="text-slate-muted text-sm">Loading queue health…</p>
          ) : (
            <div className="text-sm text-slate-muted space-y-1">
              <p>Unassigned: {queue.data.unassigned_tickets ?? 0}</p>
              <p>Avg wait: {(queue.data.avg_wait_hours ?? 0).toFixed?.(1) ?? 0}h</p>
              <p>Overall utilization: {(queue.data.overall_utilization_pct ?? 0).toFixed?.(1) ?? 0}%</p>
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Agent workload</span>
        </div>
        {!workload.data ? (
          <p className="text-slate-muted text-sm">Loading workload…</p>
        ) : workload.data.length === 0 ? (
          <p className="text-slate-muted text-sm">No workload data.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {workload.data.map((agent) => (
              <div key={agent.agent_id} className="border border-slate-border rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">{agent.agent_name || agent.email}</p>
                    <p className="text-slate-muted text-xs">Load {agent.current_load}/{agent.capacity} • Weight {agent.routing_weight}</p>
                  </div>
                  <span className="text-xs text-slate-muted">{(agent.utilization_pct ?? 0).toFixed?.(1) ?? 0}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
