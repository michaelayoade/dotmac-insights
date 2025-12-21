'use client';

import { useState, useMemo } from 'react';
import {
  Users,
  User,
  Search,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  Settings,
  ArrowRight,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useSupportTeams } from '@/hooks/useApi';
import { PageHeader } from '@/components/ui';

function MetricCard({
  label,
  value,
  icon: Icon,
  colorClass = 'text-blue-400',
  isLoading = false,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
  isLoading?: boolean;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          {isLoading ? (
            <div className="h-9 w-20 bg-slate-elevated rounded mt-1 animate-pulse" />
          ) : (
            <p className={cn('text-3xl font-bold mt-1', colorClass)}>{value}</p>
          )}
        </div>
        <div className={cn('p-3 rounded-xl bg-slate-elevated')}>
          <Icon className={cn('w-6 h-6', colorClass)} />
        </div>
      </div>
    </div>
  );
}

const ASSIGNMENT_RULE_LABELS: Record<string, string> = {
  round_robin: 'Round Robin',
  load_balanced: 'Load Balanced',
  manual: 'Manual',
  auto: 'Auto-Assign',
};

export default function InboxRoutingTeamsPage() {
  const [search, setSearch] = useState('');

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useSupportTeams();

  const teams = useMemo(() => data?.teams ?? [], [data?.teams]);

  // Compute stats
  const totalTeams = teams.length;
  const totalMembers = teams.reduce((sum: number, t: any) => sum + (t.members?.length || 0), 0);

  // Filter teams
  const filteredTeams = useMemo(() => {
    if (!search) return teams;
    const searchLower = search.toLowerCase();
    return teams.filter(
      (t: any) =>
        t.name?.toLowerCase().includes(searchLower) ||
        t.description?.toLowerCase().includes(searchLower) ||
        t.domain?.toLowerCase().includes(searchLower)
    );
  }, [teams, search]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load teams</p>
        <button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/inbox/routing"
        className="inline-flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to Routing
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Routing Teams"
          subtitle="Teams available for conversation assignment"
          icon={Users}
        />
        <Link
          href="/support/teams"
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <Settings className="w-4 h-4" />
          Manage Teams
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricCard
          label="Total Teams"
          value={totalTeams}
          icon={Users}
          colorClass="text-blue-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Total Members"
          value={totalMembers}
          icon={User}
          colorClass="text-emerald-400"
          isLoading={isLoading}
        />
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
          <input
            type="text"
            placeholder="Search teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
          />
        </div>
      </div>

      {/* Teams Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
        </div>
      ) : filteredTeams.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-muted bg-slate-card border border-slate-border rounded-xl">
          <Users className="w-12 h-12 mb-4 opacity-50" />
          <p>{search ? 'No teams match your search' : 'No teams configured'}</p>
          <Link
            href="/support/teams"
            className="mt-4 text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            Create teams in Support settings
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTeams.map((team: any) => (
            <div
              key={team.id}
              className="bg-slate-card border border-slate-border rounded-xl overflow-hidden hover:border-slate-muted transition-colors"
            >
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-400">
                      <Users className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-medium text-foreground">{team.name}</h3>
                      {team.domain && (
                        <span className="text-xs text-slate-muted">{team.domain}</span>
                      )}
                    </div>
                  </div>
                  {team.is_active !== false && (
                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-xs">
                      Active
                    </span>
                  )}
                </div>

                {team.description && (
                  <p className="text-sm text-slate-muted mb-4 line-clamp-2">
                    {team.description}
                  </p>
                )}

                <div className="flex items-center justify-between pt-3 border-t border-slate-border">
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-slate-muted" />
                    <span className="text-sm text-slate-muted">
                      {team.members?.length || 0} member{(team.members?.length || 0) !== 1 ? 's' : ''}
                    </span>
                  </div>
                  {team.assignment_rule && (
                    <span className="px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                      {ASSIGNMENT_RULE_LABELS[team.assignment_rule] || team.assignment_rule}
                    </span>
                  )}
                </div>
              </div>

              {/* Member avatars */}
              {team.members && team.members.length > 0 && (
                <div className="px-5 py-3 bg-slate-elevated/50 border-t border-slate-border">
                  <div className="flex items-center gap-2">
                    <div className="flex -space-x-2">
                      {team.members.slice(0, 5).map((member: any, idx: number) => (
                        <div
                          key={member.id || idx}
                          className="w-7 h-7 rounded-full bg-slate-elevated border-2 border-slate-card flex items-center justify-center"
                          title={member.agent_name || member.agent?.display_name}
                        >
                          <User className="w-3.5 h-3.5 text-slate-muted" />
                        </div>
                      ))}
                      {team.members.length > 5 && (
                        <div className="w-7 h-7 rounded-full bg-slate-elevated border-2 border-slate-card flex items-center justify-center text-xs text-slate-muted">
                          +{team.members.length - 5}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Count */}
      {!isLoading && filteredTeams.length > 0 && (
        <p className="text-sm text-slate-muted text-center">
          Showing {filteredTeams.length} team{filteredTeams.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}
