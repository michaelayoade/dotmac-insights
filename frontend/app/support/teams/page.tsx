'use client';

import { useState, useMemo } from 'react';
import { AlertTriangle, Plus, Shield, Users, UserPlus, Trash2, User, Filter, Search, RefreshCw, Scale } from 'lucide-react';
import { useSupportTeams, useSupportTeamMutations, useSupportAgents } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function MetricCard({
  label,
  value,
  icon: Icon,
  colorClass = 'text-teal-electric',
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          <p className={cn('text-2xl font-bold mt-1', colorClass)}>{value}</p>
        </div>
        <div className="p-2 rounded-lg bg-slate-elevated">
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

export default function SupportTeamsPage() {
  const { data, error, isLoading } = useSupportTeams();
  const { createTeam, updateTeam, deleteTeam, addMember, deleteMember } = useSupportTeamMutations();
  const { data: agentsData } = useSupportAgents();

  const agents = agentsData?.agents ?? [];
  const teams = data?.teams;

  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [teamForm, setTeamForm] = useState({ team_name: '', description: '', assignment_rule: 'round_robin' });
  const [memberForms, setMemberForms] = useState<Record<number, { agent_id: string; role: string }>>({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Calculate metrics
  const metrics = useMemo(() => {
    const teamsList = teams ?? [];
    const totalMembers = teamsList.reduce((sum, t) => sum + ((t.members || []).length), 0);
    const roundRobinCount = teamsList.filter((t) => t.assignment_rule === 'round_robin').length;
    const loadBalancedCount = teamsList.filter((t) => t.assignment_rule === 'load_balanced').length;
    return {
      totalTeams: teamsList.length,
      totalMembers,
      roundRobin: roundRobinCount,
      loadBalanced: loadBalancedCount,
    };
  }, [teams]);

  // Filter teams
  const filteredTeams = useMemo(() => {
    const teamsList = teams ?? [];
    if (!search) return teamsList;
    return teamsList.filter((team) =>
      team.team_name?.toLowerCase().includes(search.toLowerCase()) ||
      team.description?.toLowerCase().includes(search.toLowerCase())
    );
  }, [teams, search]);

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

  // Get agents not already in a team
  const getAvailableAgents = (teamId: number) => {
    const team = (teams ?? []).find((t) => t.id === teamId);
    const memberAgentIds = (team?.members || []).map((m: any) => m.agent_id);
    return agents.filter((a) => a.is_active && !memberAgentIds.includes(a.id));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
            <Shield className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Teams</h1>
            <p className="text-slate-muted text-sm">Manage queues, routing rules, and membership</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          Create Team
        </button>
      </div>

      {/* Error State */}
      {(error || formError) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{formError || 'Failed to load teams'}</span>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Teams" value={metrics.totalTeams} icon={Shield} colorClass="text-violet-400" />
        <MetricCard label="Total Members" value={metrics.totalMembers} icon={Users} colorClass="text-blue-400" />
        <MetricCard label="Round Robin" value={metrics.roundRobin} icon={RefreshCw} colorClass="text-emerald-400" />
        <MetricCard label="Load Balanced" value={metrics.loadBalanced} icon={Scale} colorClass="text-amber-400" />
      </div>

      {/* Create Team Form */}
      {showForm && (
        <form onSubmit={handleCreateTeam} className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Plus className="w-4 h-4 text-teal-electric" />
            <span className="text-white font-semibold">Create New Team</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Team Name</label>
              <input
                value={teamForm.team_name}
                onChange={(e) => setTeamForm({ ...teamForm, team_name: e.target.value })}
                placeholder="e.g., Support Tier 1"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Description</label>
              <input
                value={teamForm.description}
                onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })}
                placeholder="Team description"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Assignment Rule</label>
              <select
                value={teamForm.assignment_rule}
                onChange={(e) => setTeamForm({ ...teamForm, assignment_rule: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="round_robin">Round robin</option>
                <option value="load_balanced">Load balanced</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-slate-border">
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
              {saving ? 'Creating…' : 'Create Team'}
            </button>
          </div>
        </form>
      )}

      {/* Filter */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filter</span>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
          <input
            type="text"
            placeholder="Search teams by name or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
      </div>

      {/* Teams List */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Teams</h3>
          </div>
          <span className="text-xs text-slate-muted">{filteredTeams.length} teams</span>
        </div>

        {isLoading ? (
          <p className="text-slate-muted text-sm">Loading teams…</p>
        ) : filteredTeams.length === 0 ? (
          <div className="text-center py-8">
            <Shield className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted text-sm">No teams found.</p>
            <p className="text-slate-muted text-xs mt-1">Try adjusting your search or create a new team.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredTeams.map((team) => {
              const availableAgents = getAvailableAgents(team.id);
              return (
                <div key={team.id} className="border border-slate-border rounded-lg p-4 space-y-3">
                  {/* Team Header */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-white font-semibold text-lg">{team.team_name}</p>
                      <p className="text-slate-muted text-sm">{team.description || 'No description'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 rounded-full border border-slate-border text-slate-muted text-xs">
                        {team.assignment_rule || 'round_robin'}
                      </span>
                      <button
                        onClick={() => deleteTeam(team.id)}
                        className="px-2 py-1 rounded border border-red-500/40 text-red-300 hover:text-white text-xs"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  {/* Team Members */}
                  <div className="space-y-2">
                    <p className="text-sm text-slate-muted">Members ({(team.members || []).length})</p>
                    {(team.members || []).length === 0 ? (
                      <p className="text-slate-muted text-xs">No members yet</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {(team.members || []).map((member: any) => (
                          <div
                            key={member.id}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated"
                          >
                            <div className="w-7 h-7 rounded-full bg-slate-card flex items-center justify-center">
                              <User className="w-3 h-3 text-emerald-400" />
                            </div>
                            <div>
                              <p className="text-white text-sm font-medium">
                                {member.user_name || member.agent_name || member.user || `Agent #${member.agent_id}`}
                              </p>
                              {member.role && (
                                <p className="text-slate-muted text-xs">{member.role}</p>
                              )}
                            </div>
                            <button
                              onClick={() => deleteMember(team.id, member.id)}
                              className="text-red-300 hover:text-white ml-2"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Add Member Form */}
                  <div className="pt-3 border-t border-slate-border/50">
                    <div className="flex items-center gap-2 mb-2">
                      <UserPlus className="w-4 h-4 text-emerald-400" />
                      <span className="text-sm text-white">Add member</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        value={memberForms[team.id]?.agent_id || ''}
                        onChange={(e) =>
                          setMemberForms((prev) => ({
                            ...prev,
                            [team.id]: { agent_id: e.target.value, role: memberForms[team.id]?.role || '' },
                          }))
                        }
                        className="flex-1 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      >
                        <option value="">-- Select an agent --</option>
                        {availableAgents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.display_name || agent.email} {agent.capacity ? `(${agent.capacity} capacity)` : ''}
                          </option>
                        ))}
                      </select>
                      <input
                        value={memberForms[team.id]?.role || ''}
                        onChange={(e) =>
                          setMemberForms((prev) => ({
                            ...prev,
                            [team.id]: { agent_id: prev[team.id]?.agent_id || '', role: e.target.value },
                          }))
                        }
                        placeholder="Role (optional)"
                        className="w-40 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                      <button
                        onClick={async () => {
                          const form = memberForms[team.id];
                          if (!form?.agent_id) return;
                          await addMember(team.id, { agent_id: Number(form.agent_id), role: form.role || undefined });
                          setMemberForms((prev) => ({ ...prev, [team.id]: { agent_id: '', role: '' } }));
                        }}
                        disabled={!memberForms[team.id]?.agent_id}
                        className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50"
                      >
                        Add
                      </button>
                    </div>
                    {availableAgents.length === 0 && agents.length > 0 && (
                      <p className="text-xs text-slate-muted mt-2">All active agents are already members of this team</p>
                    )}
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
