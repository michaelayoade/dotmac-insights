'use client';

import { useState } from 'react';
import { BarChart3, Network, Users, Activity, Target } from 'lucide-react';
import { useSupportRoutingQueueHealth, useSupportRoutingRules, useSupportRoutingWorkload, useSupportTeams } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { FilterCard, FilterSelect, PageHeader, Select } from '@/components/ui';

function ProgressBar({ value, max, color = 'bg-teal-electric' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function SupportRoutingPage() {
  const [teamId, setTeamId] = useState<string>('');
  const rules = useSupportRoutingRules(teamId ? { team_id: Number(teamId) } : undefined);
  const queue = useSupportRoutingQueueHealth();
  const workload = useSupportRoutingWorkload(teamId ? Number(teamId) : undefined);
  const { data: teamsData } = useSupportTeams();
  const queueData = (queue.data || {}) as any;

  const teams = teamsData?.teams || [];
  const teamMap = new Map(teams.map((t: any) => [t.id, t.team_name]));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Routing"
        subtitle="Rules, workload, and queue health"
        icon={Network}
        iconClassName="bg-cyan-500/10 border border-cyan-500/30"
      />

      {/* Filter */}
      <FilterCard title="Filter by Team" contentClassName="flex flex-wrap gap-3">
        <FilterSelect
          value={teamId}
          onChange={(e) => setTeamId(e.target.value)}
          className="min-w-[200px]"
        >
          <option value="">All teams</option>
          {teams.map((team: any) => (
            <option key={team.id} value={team.id}>
              {team.team_name}
            </option>
          ))}
        </FilterSelect>
      </FilterCard>

      {/* Queue Health */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-amber-400" />
          <h3 className="text-foreground font-semibold">Queue Health</h3>
        </div>
        {!queue.data ? (
          <p className="text-slate-muted text-sm">Loading queue health…</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="text-center">
              <p className={cn(
                'text-2xl font-bold',
                queueData.unassigned_tickets > 10 ? 'text-rose-400' :
                queueData.unassigned_tickets > 5 ? 'text-amber-400' : 'text-foreground'
              )}>
                {queueData.unassigned_tickets ?? 0}
              </p>
              <p className="text-xs text-slate-muted">Unassigned</p>
            </div>
            <div className="text-center">
              <p className={cn(
                'text-2xl font-bold',
                (queueData.avg_wait_hours ?? 0) > 4 ? 'text-rose-400' :
                (queueData.avg_wait_hours ?? 0) > 2 ? 'text-amber-400' : 'text-emerald-400'
              )}>
                {(queueData.avg_wait_hours ?? 0).toFixed(1)}h
              </p>
              <p className="text-xs text-slate-muted">Avg Wait</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-400">{queueData.total_agents ?? 0}</p>
              <p className="text-xs text-slate-muted">Agents</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-400">{queueData.total_capacity ?? 0}</p>
              <p className="text-xs text-slate-muted">Capacity</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet-400">{queueData.total_load ?? 0}</p>
              <p className="text-xs text-slate-muted">Current Load</p>
            </div>
            <div className="text-center">
              <p className={cn(
                'text-2xl font-bold',
                (queueData.overall_utilization_pct ?? 0) > 90 ? 'text-rose-400' :
                (queueData.overall_utilization_pct ?? 0) > 70 ? 'text-amber-400' : 'text-teal-electric'
              )}>
                {(queueData.overall_utilization_pct ?? 0).toFixed(0)}%
              </p>
              <p className="text-xs text-slate-muted">Utilization</p>
            </div>
          </div>
        )}
      </div>

      {/* Rules & Workload Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Rules */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Routing Rules</h3>
            </div>
            <span className="text-xs text-slate-muted">{rules.data?.length ?? 0} rules</span>
          </div>
          {!rules.data ? (
            <p className="text-slate-muted text-sm">Loading rules…</p>
          ) : rules.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No routing rules configured.</p>
          ) : (
            <div className="space-y-3">
              {rules.data.map((rule: any) => (
                <div key={rule.id} className="border border-slate-border rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-foreground font-semibold">{rule.name}</p>
                      <p className="text-slate-muted text-xs">{rule.description || 'No description'}</p>
                    </div>
                    <span className="px-2 py-1 rounded-full border border-slate-border text-slate-muted text-xs">
                      {rule.strategy}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-muted">
                    <span className="flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      Team: {rule.team_id ? String(teamMap.get(rule.team_id) || `#${rule.team_id}`) : 'Any'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Target className="w-3 h-3" />
                      Priority: {rule.priority ?? 100}
                    </span>
                    <span className={cn(
                      'px-2 py-0.5 rounded',
                      rule.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-elevated text-slate-muted'
                    )}>
                      {rule.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Agent Workload */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-cyan-400" />
              <h3 className="text-foreground font-semibold">Agent Workload</h3>
            </div>
            <span className="text-xs text-slate-muted">{workload.data?.length ?? 0} agents</span>
          </div>
          {!workload.data ? (
            <p className="text-slate-muted text-sm">Loading workload…</p>
          ) : workload.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No workload data available.</p>
          ) : (
            <div className="space-y-3">
              {workload.data.map((agent: any) => (
                <div key={agent.agent_id} className="border border-slate-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-foreground font-semibold">{agent.agent_name || agent.email || `Agent #${agent.agent_id}`}</p>
                      <p className="text-slate-muted text-xs">
                        Load {agent.current_load}/{agent.capacity} • Weight {agent.routing_weight}
                      </p>
                    </div>
                    <span className={cn(
                      'text-lg font-bold',
                      (agent.utilization_pct ?? 0) > 90 ? 'text-rose-400' :
                      (agent.utilization_pct ?? 0) > 70 ? 'text-amber-400' : 'text-emerald-400'
                    )}>
                      {(agent.utilization_pct ?? 0).toFixed(0)}%
                    </span>
                  </div>
                  <ProgressBar
                    value={agent.current_load ?? 0}
                    max={agent.capacity ?? 0}
                    color={(agent.utilization_pct ?? 0) > 90 ? 'bg-rose-500' :
                           (agent.utilization_pct ?? 0) > 70 ? 'bg-amber-500' : 'bg-emerald-500'}
                  />
                  <div className="flex items-center justify-between mt-2 text-xs text-slate-muted">
                    <span className={cn(
                      'px-2 py-0.5 rounded',
                      agent.is_available ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-elevated text-slate-muted'
                    )}>
                      {agent.is_available ? 'Available' : 'Unavailable'}
                    </span>
                    {agent.team_name && (
                      <span>Team: {agent.team_name}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
