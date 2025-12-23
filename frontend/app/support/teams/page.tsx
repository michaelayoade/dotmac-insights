'use client';

import { useState, useMemo } from 'react';
import { AlertTriangle, Plus, Shield, Users, UserPlus, Trash2, User, RefreshCw, Scale } from 'lucide-react';
import { useSupportTeams, useSupportTeamMutations, useSupportAgents } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { Button, FilterCard, FilterInput } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

export default function SupportTeamsPage() {
  const { hasAccess: canWrite, isLoading: authLoading } = useRequireScope('support:write');
  const canFetch = !authLoading;
  const { data, error, isLoading } = useSupportTeams({ isPaused: () => !canFetch });
  const { createTeam, updateTeam, deleteTeam, addMember, deleteMember } = useSupportTeamMutations();
  const { data: agentsData } = useSupportAgents(undefined, undefined, { isPaused: () => !canFetch });

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
    const totalMembers = teamsList.reduce((sum: number, t: any) => sum + ((t.members || []).length), 0);
    const roundRobinCount = teamsList.filter((t: any) => t.assignment_rule === 'round_robin').length;
    const loadBalancedCount = teamsList.filter((t: any) => t.assignment_rule === 'load_balanced').length;
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
    return teamsList.filter((team: any) =>
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
    if (!canWrite) {
      setFormError('Access denied');
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
    const team = (teams ?? []).find((t: any) => t.id === teamId);
    const memberAgentIds = (team?.members || []).map((m: any) => m.agent_id);
    return agents.filter((a: any) => a.is_active && !memberAgentIds.includes(a.id));
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
            <h1 className="text-2xl font-bold text-foreground">Teams</h1>
            <p className="text-slate-muted text-sm">Manage queues, routing rules, and membership</p>
          </div>
        </div>
        <Button
          onClick={() => setShowForm(!showForm)}
          disabled={!canWrite}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          Create Team
        </Button>
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
        <StatCard title="Total Teams" value={metrics.totalTeams} icon={Shield} colorClass="text-violet-400" />
        <StatCard title="Total Members" value={metrics.totalMembers} icon={Users} colorClass="text-blue-400" />
        <StatCard title="Round Robin" value={metrics.roundRobin} icon={RefreshCw} colorClass="text-emerald-400" />
        <StatCard title="Load Balanced" value={metrics.loadBalanced} icon={Scale} colorClass="text-amber-400" />
      </div>

      {/* Create Team Form */}
      {showForm && canWrite && (
        <form onSubmit={handleCreateTeam} className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Plus className="w-4 h-4 text-teal-electric" />
            <span className="text-foreground font-semibold">Create New Team</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Team Name</label>
              <input
                value={teamForm.team_name}
                onChange={(e) => setTeamForm({ ...teamForm, team_name: e.target.value })}
                placeholder="e.g., Support Tier 1"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Description</label>
              <input
                value={teamForm.description}
                onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })}
                placeholder="Team description"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-muted">Assignment Rule</label>
              <select
                value={teamForm.assignment_rule}
                onChange={(e) => setTeamForm({ ...teamForm, assignment_rule: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="round_robin">Round robin</option>
                <option value="load_balanced">Load balanced</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-slate-border">
            <Button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground text-sm"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving || !canWrite}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
            >
              {saving ? 'Creating…' : 'Create Team'}
            </Button>
          </div>
        </form>
      )}

      {/* Filter */}
      <FilterCard contentClassName="flex flex-wrap gap-3">
        <FilterInput
          type="text"
          placeholder="Search teams by name or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full"
        />
      </FilterCard>

      {/* Teams List */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Teams</h3>
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
            {filteredTeams.map((team: any) => {
              const availableAgents = getAvailableAgents(team.id);
              return (
                <div key={team.id} className="border border-slate-border rounded-lg p-4 space-y-3">
                  {/* Team Header */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-foreground font-semibold text-lg">{team.team_name}</p>
                      <p className="text-slate-muted text-sm">{team.description || 'No description'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 rounded-full border border-slate-border text-slate-muted text-xs">
                        {team.assignment_rule || 'round_robin'}
                      </span>
                      <Button
                        onClick={() => deleteTeam(team.id)}
                        disabled={!canWrite}
                        className="px-2 py-1 rounded border border-red-500/40 text-red-300 hover:text-foreground text-xs disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        Delete
                      </Button>
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
                              <p className="text-foreground text-sm font-medium">
                                {member.user_name || member.agent_name || member.user || `Agent #${member.agent_id}`}
                              </p>
                              {member.role && (
                                <p className="text-slate-muted text-xs">{member.role}</p>
                              )}
                            </div>
                            <Button
                              onClick={() => deleteMember(team.id, member.id)}
                              disabled={!canWrite}
                              className="text-red-300 hover:text-foreground ml-2 disabled:opacity-60 disabled:cursor-not-allowed"
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Add Member Form */}
                  <div className="pt-3 border-t border-slate-border/50">
                    <div className="flex items-center gap-2 mb-2">
                      <UserPlus className="w-4 h-4 text-emerald-400" />
                      <span className="text-sm text-foreground">Add member</span>
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
                        className="flex-1 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      >
                        <option value="">-- Select an agent --</option>
                        {availableAgents.map((agent: any) => (
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
                        className="w-40 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                      <Button
                        onClick={async () => {
                          if (!canWrite) return;
                          const form = memberForms[team.id];
                          if (!form?.agent_id) return;
                          await addMember(team.id, { agent_id: Number(form.agent_id), role: form.role || undefined });
                          setMemberForms((prev) => ({ ...prev, [team.id]: { agent_id: '', role: '' } }));
                        }}
                        disabled={!memberForms[team.id]?.agent_id || !canWrite}
                        className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Add
                      </Button>
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
