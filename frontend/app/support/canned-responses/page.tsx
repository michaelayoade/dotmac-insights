'use client';

import { useState, useMemo } from 'react';
import { AlertTriangle, Filter, MessageCircle, Search, Globe, Users, User, Hash, FileText, FolderOpen, Copy } from 'lucide-react';
import { useSupportCannedCategories, useSupportCannedResponses } from '@/hooks/useApi';
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

function getScopeIcon(scope: string) {
  switch (scope?.toLowerCase()) {
    case 'global':
      return Globe;
    case 'team':
      return Users;
    case 'personal':
      return User;
    default:
      return FileText;
  }
}

function getScopeColor(scope: string) {
  switch (scope?.toLowerCase()) {
    case 'global':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    case 'team':
      return 'bg-violet-500/10 text-violet-400 border-violet-500/30';
    case 'personal':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    default:
      return 'bg-slate-elevated text-slate-muted border-slate-border';
  }
}

export default function SupportCannedResponsesPage() {
  const [category, setCategory] = useState('');
  const [scope, setScope] = useState('');
  const [search, setSearch] = useState('');

  const responses = useSupportCannedResponses({
    category: category || undefined,
    scope: scope || undefined,
    search: search || undefined,
    limit: 50,
  });
  const categories = useSupportCannedCategories();

  const list = responses.data?.data;
  const categoryList = categories.data;

  // Calculate metrics
  const metrics = useMemo(() => {
    const responsesList = list ?? [];
    const catList = categoryList ?? [];
    const globalCount = responsesList.filter((r: any) => r.scope === 'global').length;
    const teamCount = responsesList.filter((r: any) => r.scope === 'team').length;
    const personalCount = responsesList.filter((r: any) => r.scope === 'personal').length;
    const withShortcode = responsesList.filter((r: any) => r.shortcode).length;
    return {
      total: responsesList.length,
      global: globalCount,
      team: teamCount,
      personal: personalCount,
      withShortcode,
      categories: catList.length,
    };
  }, [list, categoryList]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
          <MessageCircle className="w-5 h-5 text-violet-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Canned Responses</h1>
          <p className="text-slate-muted text-sm">Shortcodes, templates, and quick replies</p>
        </div>
      </div>

      {/* Error State */}
      {(responses.error || categories.error) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load canned responses</span>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard label="Total Responses" value={metrics.total} icon={FileText} colorClass="text-blue-400" />
        <MetricCard label="Global" value={metrics.global} icon={Globe} colorClass="text-emerald-400" />
        <MetricCard label="Team" value={metrics.team} icon={Users} colorClass="text-violet-400" />
        <MetricCard label="Personal" value={metrics.personal} icon={User} colorClass="text-amber-400" />
        <MetricCard label="With Shortcode" value={metrics.withShortcode} icon={Hash} colorClass="text-cyan-400" />
        <MetricCard label="Categories" value={metrics.categories} icon={FolderOpen} colorClass="text-rose-400" />
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-foreground text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search responses..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          {/* Scope */}
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All scopes</option>
            <option value="personal">Personal</option>
            <option value="team">Team</option>
            <option value="global">Global</option>
          </select>
          {/* Category */}
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All categories</option>
            {(categoryList ?? []).map((cat: any) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          {/* Clear filters button */}
          {(search || scope || category) && (
            <button
              onClick={() => {
                setSearch('');
                setScope('');
                setCategory('');
              }}
              className="px-3 py-2 text-sm text-slate-muted hover:text-foreground border border-slate-border rounded-lg hover:bg-slate-elevated transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Responses List */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Responses</h3>
          </div>
          <span className="text-xs text-slate-muted">{(list ?? []).length} responses</span>
        </div>

        {!responses.data ? (
          <p className="text-slate-muted text-sm">Loading responses…</p>
        ) : (list ?? []).length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted text-sm">No canned responses found.</p>
            <p className="text-slate-muted text-xs mt-1">Try adjusting your filters or create a new response.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {(list ?? []).map((resp: any) => {
              const ScopeIcon = getScopeIcon(resp.scope);
              return (
                <div key={resp.id} className="border border-slate-border rounded-lg p-4 hover:border-slate-border/80 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-foreground font-semibold">{resp.name}</p>
                        {resp.shortcode && (
                          <button
                            onClick={() => copyToClipboard(resp.shortcode)}
                            className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-elevated text-xs text-cyan-400 hover:bg-slate-border transition-colors"
                            title="Copy shortcode"
                          >
                            <Hash className="w-3 h-3" />
                            {resp.shortcode}
                            <Copy className="w-3 h-3 ml-1" />
                          </button>
                        )}
                      </div>
                      <p className="text-slate-muted text-sm line-clamp-3 mt-2">{resp.content}</p>
                    </div>
                    <span className={cn(
                      'flex items-center gap-1 px-2 py-1 rounded text-xs font-medium border',
                      getScopeColor(resp.scope)
                    )}>
                      <ScopeIcon className="w-3 h-3" />
                      {resp.scope}
                    </span>
                  </div>
                  {resp.category && (
                    <div className="mt-3 pt-3 border-t border-slate-border/50 flex items-center justify-between">
                      <span className="text-xs text-slate-muted flex items-center gap-1">
                        <FolderOpen className="w-3 h-3" />
                        {resp.category}
                      </span>
                      {resp.team_name && (
                        <span className="text-xs text-slate-muted flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          {resp.team_name}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
