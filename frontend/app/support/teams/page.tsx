'use client';

import { useState } from 'react';
import { AlertTriangle, Plus, Shield, Users, UserPlus, Trash2 } from 'lucide-react';
import { useSupportTeams, useSupportTeamMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function SupportTeamsPage() {
  const { data, error, isLoading } = useSupportTeams();
  const { createTeam, updateTeam, deleteTeam, addMember, deleteMember } = useSupportTeamMutations();

  const [teamForm, setTeamForm] = useState({ team_name: '', description: '', assignment_rule: 'round_robin' });
  const [memberForms, setMemberForms] = useState<Record<number, { agent_id: string; role: string }>>({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!teamForm.team_name.trim()) {
      setFormError('Team name is required');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await createTeam({
        team_name: teamForm.team_name.trim(),
        description: teamForm.description || undefined,
        assignment_rule: teamForm.assignment_rule as any,
      });
      setTeamForm({ team_name: '', description: '', assignment_rule: 'round_robin' });
    } catch (err: any) {
      setFormError(err?.message || 'Failed to create team');
    } finally {
      setSaving(false);
    }
  };

  const teams = data?.teams || [];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
        <h1 className="text-2xl font-bold text-white">Teams</h1>
        <p className="text-slate-muted text-sm">Manage queues, routing rules, and membership</p>
      </div>

      {(error || formError) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{formError || 'Failed to load teams'}</span>
        </div>
      )}

      <form onSubmit={handleCreateTeam} className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Plus className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Create team</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={teamForm.team_name}
            onChange={(e) => setTeamForm({ ...teamForm, team_name: e.target.value })}
            placeholder="Team name"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={teamForm.description}
            onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })}
            placeholder="Description"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={teamForm.assignment_rule}
            onChange={(e) => setTeamForm({ ...teamForm, assignment_rule: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="round_robin">Round robin</option>
            <option value="load_balanced">Load balanced</option>
          </select>
          <div className="flex justify-end md:col-span-3">
            <button
              type="submit"
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60'
              )}
            >
              {saving ? 'Saving…' : 'Create team'}
            </button>
          </div>
        </div>
      </form>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Teams</span>
        </div>
        {isLoading ? (
          <p className="text-slate-muted text-sm">Loading teams…</p>
        ) : teams.length === 0 ? (
          <p className="text-slate-muted text-sm">No teams found.</p>
        ) : (
          <div className="space-y-3">
            {teams.map((team) => (
              <div key={team.id} className="border border-slate-border rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">{team.team_name}</p>
                    <p className="text-slate-muted text-xs">{team.description || 'No description'}</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="px-2 py-1 rounded-full border border-slate-border text-slate-muted">
                      {team.assignment_rule || 'round_robin'}
                    </span>
                    <button
                      onClick={() => deleteTeam(team.id)}
                      className="px-2 py-1 rounded border border-red-500/40 text-red-300 hover:text-white"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(team.members || []).map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center gap-2 px-2 py-1 rounded border border-slate-border text-xs text-slate-muted"
                    >
                      <Users className="w-3 h-3 text-emerald-400" />
                      <span>{member.user_name || member.user || `Member #${member.id}`}</span>
                      <button
                        onClick={() => deleteMember(team.id, member.id)}
                        className="text-red-300 hover:text-white"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <UserPlus className="w-4 h-4 text-emerald-400" />
                  <input
                    value={memberForms[team.id]?.agent_id || ''}
                    onChange={(e) =>
                      setMemberForms((prev) => ({
                        ...prev,
                        [team.id]: { agent_id: e.target.value, role: memberForms[team.id]?.role || '' },
                      }))
                    }
                    placeholder="Agent ID"
                    className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  />
                  <input
                    value={memberForms[team.id]?.role || ''}
                    onChange={(e) =>
                      setMemberForms((prev) => ({
                        ...prev,
                        [team.id]: { agent_id: prev[team.id]?.agent_id || '', role: e.target.value },
                      }))
                    }
                    placeholder="Role (optional)"
                    className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  />
                  <button
                    onClick={async () => {
                      const form = memberForms[team.id];
                      if (!form?.agent_id) return;
                      await addMember(team.id, { agent_id: Number(form.agent_id), role: form.role || undefined });
                      setMemberForms((prev) => ({ ...prev, [team.id]: { agent_id: '', role: '' } }));
                    }}
                    className="px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
                  >
                    Add member
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
