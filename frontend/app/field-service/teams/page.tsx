'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  Users,
  Plus,
  Search,
  MapPin,
  Phone,
  Mail,
  Star,
  Clock,
  ClipboardList,
  ChevronRight,
  Edit2,
  User,
  Award,
  TrendingUp,
} from 'lucide-react';
import { fieldServiceApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

type ViewMode = 'teams' | 'technicians';

export default function TeamsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('teams');
  const [search, setSearch] = useState('');
  const [selectedTeam, setSelectedTeam] = useState<any>(null);

  const { data: teamsData, isLoading: teamsLoading } = useSWR('field-teams', () =>
    fieldServiceApi.getTeams()
  );

  const { data: techniciansData, isLoading: techniciansLoading } = useSWR(
    viewMode === 'technicians' ? ['field-technicians', search] : null,
    () => fieldServiceApi.getTechnicians({ search: search || undefined })
  );

  const teams = teamsData?.data || [];
  const technicians = techniciansData?.data || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Field Teams</h2>
          <p className="text-sm text-slate-muted">
            Manage teams and technicians
          </p>
        </div>
        <Button
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Team
        </Button>
      </div>

      {/* View Toggle */}
      <div className="flex items-center gap-4">
        <div className="flex items-center bg-slate-elevated border border-slate-border rounded-lg p-1">
          <Button
            onClick={() => setViewMode('teams')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded text-sm transition-colors',
              viewMode === 'teams'
                ? 'bg-teal-electric text-slate-950'
                : 'text-slate-muted hover:text-foreground'
            )}
          >
            <Users className="w-4 h-4" />
            Teams
          </Button>
          <Button
            onClick={() => setViewMode('technicians')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded text-sm transition-colors',
              viewMode === 'technicians'
                ? 'bg-teal-electric text-slate-950'
                : 'text-slate-muted hover:text-foreground'
            )}
          >
            <User className="w-4 h-4" />
            Technicians
          </Button>
        </div>

        {viewMode === 'technicians' && (
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search technicians..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
            />
          </div>
        )}
      </div>

      {/* Teams View */}
      {viewMode === 'teams' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Teams List */}
          <div className="lg:col-span-1">
            <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-border">
                <h3 className="font-semibold text-foreground">All Teams</h3>
              </div>
              <div className="divide-y divide-slate-border">
                {teamsLoading ? (
                  <div className="p-4 text-center text-slate-muted">Loading...</div>
                ) : teams.length > 0 ? (
                  teams.map((team: any) => (
                    <Button
                      key={team.id}
                      onClick={() => setSelectedTeam(team)}
                      className={cn(
                        'w-full flex items-center justify-between p-4 text-left hover:bg-slate-elevated/50 transition-colors',
                        selectedTeam?.id === team.id && 'bg-slate-elevated/50'
                      )}
                    >
                      <div>
                        <p className="text-foreground font-medium">{team.name}</p>
                        <p className="text-sm text-slate-muted">
                          {team.members?.length || 0} members
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-muted" />
                    </Button>
                  ))
                ) : (
                  <div className="p-4 text-center text-slate-muted">
                    No teams created yet
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Team Details */}
          <div className="lg:col-span-2">
            {selectedTeam ? (
              <div className="space-y-6">
                {/* Team Header */}
                <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-xl font-semibold text-foreground">{selectedTeam.name}</h3>
                      <p className="text-slate-muted">{selectedTeam.description || 'No description'}</p>
                    </div>
                    <Button className="p-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors">
                      <Edit2 className="w-4 h-4" />
                    </Button>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg bg-slate-elevated">
                      <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
                        <Users className="w-4 h-4" />
                        Members
                      </div>
                      <p className="text-2xl font-bold text-foreground">
                        {selectedTeam.members?.length || 0}
                      </p>
                    </div>
                    <div className="p-4 rounded-lg bg-slate-elevated">
                      <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
                        <ClipboardList className="w-4 h-4" />
                        Active Orders
                      </div>
                      <p className="text-2xl font-bold text-foreground">
                        {selectedTeam.active_orders || 0}
                      </p>
                    </div>
                    <div className="p-4 rounded-lg bg-slate-elevated">
                      <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
                        <Star className="w-4 h-4 text-amber-400" />
                        Avg Rating
                      </div>
                      <p className="text-2xl font-bold text-foreground">
                        {selectedTeam.avg_rating?.toFixed(1) || 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Service Zones */}
                {selectedTeam.zones?.length > 0 && (
                  <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                    <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-teal-electric" />
                      Service Zones
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedTeam.zones.map((zone: any) => (
                        <span
                          key={zone.id}
                          className="px-3 py-1.5 rounded-full bg-slate-elevated text-sm text-foreground"
                        >
                          {zone.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Team Members */}
                <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-foreground flex items-center gap-2">
                      <Users className="w-4 h-4 text-teal-electric" />
                      Team Members
                    </h4>
                    <Button className="inline-flex items-center gap-1 text-sm text-teal-electric hover:underline">
                      <Plus className="w-4 h-4" />
                      Add Member
                    </Button>
                  </div>

                  {selectedTeam.members?.length > 0 ? (
                    <div className="space-y-3">
                      {selectedTeam.members.map((member: any) => (
                        <div
                          key={member.id}
                          className="flex items-center justify-between p-3 rounded-lg bg-slate-elevated"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-slate-card flex items-center justify-center">
                              <User className="w-5 h-5 text-slate-muted" />
                            </div>
                            <div>
                              <p className="text-foreground font-medium">{member.employee_name}</p>
                              <p className="text-xs text-slate-muted capitalize">
                                {member.role?.replace('_', ' ') || 'Technician'}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4 text-sm">
                            {member.avg_rating && (
                              <div className="flex items-center gap-1 text-amber-400">
                                <Star className="w-4 h-4 fill-amber-400" />
                                {member.avg_rating.toFixed(1)}
                              </div>
                            )}
                            <span className={cn(
                              'px-2 py-1 rounded text-xs',
                              member.is_available
                                ? 'bg-green-500/10 text-green-400'
                                : 'bg-red-500/10 text-red-400'
                            )}>
                              {member.is_available ? 'Available' : 'Busy'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-slate-muted text-center py-4">No members in this team</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
                <Users className="w-12 h-12 mx-auto mb-3 text-slate-muted opacity-50" />
                <p className="text-lg text-slate-muted mb-2">Select a team</p>
                <p className="text-sm text-slate-muted">
                  Click on a team to view details and members
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Technicians View */}
      {viewMode === 'technicians' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {techniciansLoading ? (
            <div className="col-span-full text-center py-8 text-slate-muted">Loading...</div>
          ) : technicians.length > 0 ? (
            technicians.map((tech: any) => (
              <div
                key={tech.id}
                className="bg-slate-card border border-slate-border rounded-xl p-5"
              >
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-12 h-12 rounded-full bg-slate-elevated flex items-center justify-center">
                    <User className="w-6 h-6 text-slate-muted" />
                  </div>
                  <div className="flex-1">
                    <p className="text-foreground font-semibold">{tech.name}</p>
                    <p className="text-sm text-slate-muted">{tech.team_name || 'No team'}</p>
                  </div>
                  <span className={cn(
                    'px-2 py-1 rounded text-xs',
                    tech.is_available
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-red-500/10 text-red-400'
                  )}>
                    {tech.is_available ? 'Available' : 'Busy'}
                  </span>
                </div>

                {/* Contact */}
                <div className="space-y-2 mb-4 text-sm">
                  {tech.phone && (
                    <div className="flex items-center gap-2 text-slate-muted">
                      <Phone className="w-4 h-4" />
                      {tech.phone}
                    </div>
                  )}
                  {tech.email && (
                    <div className="flex items-center gap-2 text-slate-muted">
                      <Mail className="w-4 h-4" />
                      {tech.email}
                    </div>
                  )}
                </div>

                {/* Skills */}
                {tech.skills?.length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs text-slate-muted mb-2">Skills</p>
                    <div className="flex flex-wrap gap-1">
                      {tech.skills.slice(0, 4).map((skill: any, idx: number) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-slate-elevated text-xs text-slate-muted"
                        >
                          {skill.skill_name}
                        </span>
                      ))}
                      {tech.skills.length > 4 && (
                        <span className="px-2 py-0.5 text-xs text-slate-muted">
                          +{tech.skills.length - 4} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-3 gap-2 pt-4 border-t border-slate-border">
                  <div className="text-center">
                    <p className="text-lg font-bold text-foreground">{tech.completed_orders || 0}</p>
                    <p className="text-xs text-slate-muted">Completed</p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                      <span className="text-lg font-bold text-foreground">
                        {tech.avg_rating?.toFixed(1) || 'N/A'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-muted">Rating</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-foreground">
                      {tech.completion_rate ? `${tech.completion_rate}%` : 'N/A'}
                    </p>
                    <p className="text-xs text-slate-muted">Rate</p>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full text-center py-8">
              <User className="w-12 h-12 mx-auto mb-3 text-slate-muted opacity-50" />
              <p className="text-lg text-slate-muted mb-2">No technicians found</p>
              {search && (
                <p className="text-sm text-slate-muted">
                  Try adjusting your search
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
