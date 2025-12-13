'use client';

import { useState } from 'react';
import { AlertTriangle, CheckCircle, Plus, User, Users } from 'lucide-react';
import { useSupportAgents, useSupportAgentMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function SupportAgentsPage() {
  const { data, error, isLoading } = useSupportAgents();
  const { createAgent, updateAgent, deleteAgent } = useSupportAgentMutations();

  const [form, setForm] = useState({
    email: '',
    display_name: '',
    employee_id: '',
    capacity: '',
    is_active: true,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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
    } catch (err: any) {
      setSaveError(err?.message || 'Failed to create agent');
    } finally {
      setSaving(false);
    }
  };

  const agents = data?.agents || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-2xl font-bold text-white">Agents</h1>
          <p className="text-slate-muted text-sm">Manage support agents, capacity, and status</p>
        </div>
      </div>

      {(error || saveError) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{saveError || 'Failed to load agents'}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Plus className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Add agent</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            placeholder="Display name"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={form.employee_id}
            onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
            placeholder="Employee ID"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={form.capacity}
            onChange={(e) => setForm({ ...form, capacity: e.target.value })}
            placeholder="Capacity"
            type="number"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <label className="inline-flex items-center gap-2 text-slate-muted text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active
          </label>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60'
              )}
            >
              {saving ? 'Saving…' : 'Create agent'}
            </button>
          </div>
        </div>
      </form>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Agents</span>
        </div>

        {isLoading ? (
          <p className="text-slate-muted text-sm">Loading agents…</p>
        ) : agents.length === 0 ? (
          <p className="text-slate-muted text-sm">No agents found.</p>
        ) : (
          <div className="space-y-2">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="flex items-center justify-between rounded-lg border border-slate-border px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-elevated flex items-center justify-center">
                    <User className="w-4 h-4 text-teal-electric" />
                  </div>
                  <div>
                    <p className="text-white font-medium">{agent.display_name || agent.email || 'Agent'}</p>
                    <p className="text-slate-muted text-xs">
                      {agent.email || 'No email'} • Capacity {agent.capacity ?? '-'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span
                    className={cn(
                      'px-2 py-1 rounded-full border font-medium',
                      agent.is_active
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : 'bg-slate-700 text-slate-200 border-slate-600'
                    )}
                  >
                    {agent.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <button
                    onClick={() => updateAgent(agent.id, { is_active: !agent.is_active })}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:text-white"
                  >
                    Toggle
                  </button>
                  <button
                    onClick={() => deleteAgent(agent.id)}
                    className="px-2 py-1 rounded border border-red-500/40 text-red-300 hover:text-white"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
