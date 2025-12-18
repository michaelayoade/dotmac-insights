'use client';

import { useState, useMemo } from 'react';
import { AlertTriangle, Plus, User, Users, CheckCircle2, XCircle, Activity, Briefcase, Search, Filter } from 'lucide-react';
import { useSupportAgents, useSupportAgentMutations, useSupportRoutingQueueHealth } from '@/hooks/useApi';
import type { SupportAgent } from '@/lib/api';
import { cn } from '@/lib/utils';

function MetricCard({
  label,
  value,
  icon: Icon,
  colorClass = 'text-teal-electric',
  subtitle,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
  subtitle?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          <p className={cn('text-2xl font-bold mt-1', colorClass)}>{value}</p>
          {subtitle && <p className="text-xs text-slate-muted mt-1">{subtitle}</p>}
        </div>
        <div className="p-2 rounded-lg bg-slate-elevated">
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ value, max, color = 'bg-teal-electric' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function SupportAgentsPage() {
  const { data, error, isLoading } = useSupportAgents();
  const { data: queueHealth } = useSupportRoutingQueueHealth();
  const { createAgent, updateAgent, deleteAgent } = useSupportAgentMutations();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    email: '',
    display_name: '',
    employee_id: '',
    capacity: '',
    is_active: true,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const agents = data?.agents;

  // Calculate metrics
  const metrics = useMemo(() => {
    const agentsList: SupportAgent[] = agents ?? [];
    const activeCount = agentsList.filter((a) => a.is_active).length;
    const inactiveCount = agentsList.filter((a) => !a.is_active).length;
    const totalCapacity = agentsList.reduce((sum, a) => sum + (a.capacity ?? 0), 0);
    return {
      total: agentsList.length,
      active: activeCount,
      inactive: inactiveCount,
      totalCapacity,
      currentLoad: queueHealth?.total_load ?? 0,
      utilization: queueHealth?.overall_utilization_pct ?? 0,
    };
  }, [agents, queueHealth]);

  // Filter agents
  const filteredAgents = useMemo(() => {
    const agentsList: SupportAgent[] = agents ?? [];
    return agentsList.filter((agent) => {
      const matchesSearch =
        !search ||
        (agent.display_name?.toLowerCase().includes(search.toLowerCase()) ||
          agent.email?.toLowerCase().includes(search.toLowerCase()));
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && agent.is_active) ||
        (statusFilter === 'inactive' && !agent.is_active);
      return matchesSearch && matchesStatus;
    });
  }, [agents, search, statusFilter]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      await createAgent({
        email: form.email || undefined,
        display_name: form.display_name || undefined,
        employee_id: form.employee_id ? Number(form.employee_id) : undefined,
        capacity: form.capacity ? Number(form.capacity) : undefined,
        is_active: form.is_active,
      });
      setForm({ email: '', display_name: '', employee_id: '', capacity: '', is_active: true });
      setShowForm(false);
    } catch (err: any) {
      setSaveError(err?.message || 'Failed to create agent');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <Users className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Agents</h1>
            <p className="text-slate-muted text-sm">Manage support agents, capacity, and status</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          Add Agent
        </button>
      </div>

      {/* Error State */}
      {(error || saveError) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{saveError || 'Failed to load agents'}</span>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard label="Total Agents" value={metrics.total} icon={Users} colorClass="text-blue-400" />
        <MetricCard label="Active" value={metrics.active} icon={CheckCircle2} colorClass="text-emerald-400" />
        <MetricCard label="Inactive" value={metrics.inactive} icon={XCircle} colorClass="text-slate-muted" />
        <MetricCard label="Total Capacity" value={metrics.totalCapacity} icon={Briefcase} colorClass="text-violet-400" />
        <MetricCard label="Current Load" value={metrics.currentLoad} icon={Activity} colorClass="text-amber-400" />
        <MetricCard
          label="Utilization"
          value={`${metrics.utilization.toFixed(0)}%`}
          icon={Activity}
          colorClass={metrics.utilization > 80 ? 'text-rose-400' : metrics.utilization > 60 ? 'text-amber-400' : 'text-emerald-400'}
        />
      </div>

      {/* Add Agent Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Plus className="w-4 h-4 text-teal-electric" />
            <span className="text-white font-semibold">Add New Agent</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Display Name</label>
              <input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                placeholder="John Doe"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Email</label>
              <input
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="john@example.com"
                type="email"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Employee ID</label>
              <input
                value={form.employee_id}
                onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
                placeholder="123"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Capacity</label>
              <input
                value={form.capacity}
                onChange={(e) => setForm({ ...form, capacity: e.target.value })}
                placeholder="10"
                type="number"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-border">
            <label className="inline-flex items-center gap-2 text-slate-muted text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
              />
              <span>Active</span>
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
              >
                {saving ? 'Creating…' : 'Create Agent'}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="all">All Status</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>
        </div>
      </div>

      {/* Agents List */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-cyan-400" />
            <h3 className="text-white font-semibold">Agents</h3>
          </div>
          <span className="text-xs text-slate-muted">{filteredAgents.length} agents</span>
        </div>

        {isLoading ? (
          <p className="text-slate-muted text-sm">Loading agents…</p>
        ) : filteredAgents.length === 0 ? (
          <div className="text-center py-8">
            <Users className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted text-sm">No agents found.</p>
            <p className="text-slate-muted text-xs mt-1">Try adjusting your filters or add a new agent.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredAgents.map((agent: SupportAgent) => {
              const agentAny = agent as any;
              const currentLoad = agentAny.current_load ?? 0;
              const utilization = agent.capacity ? (currentLoad / agent.capacity) * 100 : 0;
              return (
                <div
                  key={agent.id}
                  className="border border-slate-border rounded-lg p-4 hover:border-slate-border/80 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center">
                        <User className="w-5 h-5 text-cyan-400" />
                      </div>
                      <div>
                        <p className="text-white font-semibold">{agent.display_name || agent.email || 'Agent'}</p>
                        <p className="text-slate-muted text-xs">{agent.email || 'No email'}</p>
                      </div>
                    </div>
                    <span
                      className={cn(
                        'px-2 py-1 rounded-full border text-xs font-medium',
                        agent.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-slate-elevated text-slate-muted border-slate-border'
                      )}
                    >
                      {agent.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  {/* Capacity Progress */}
                  <div className="mt-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-muted">Capacity</span>
                      <span className="text-white font-mono">
                        {agent.capacity ?? '-'} tickets
                      </span>
                    </div>
                    {agent.capacity && (
                      <ProgressBar
                        value={currentLoad}
                        max={agent.capacity}
                        color={utilization > 90 ? 'bg-rose-500' : utilization > 70 ? 'bg-amber-500' : 'bg-emerald-500'}
                      />
                    )}
                  </div>

                  {/* Actions */}
                  <div className="mt-4 pt-3 border-t border-slate-border/50 flex items-center justify-end gap-2">
                    <button
                      onClick={() => updateAgent(agent.id, { is_active: !agent.is_active })}
                      className="px-3 py-1.5 rounded-lg border border-slate-border text-xs text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
                    >
                      {agent.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => deleteAgent(agent.id)}
                      className="px-3 py-1.5 rounded-lg border border-rose-500/40 text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
