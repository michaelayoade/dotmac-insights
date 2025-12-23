'use client';

import { useState, useMemo } from 'react';
import {
  MessageCircle,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  Copy,
  Check,
  Globe,
  Users,
  User,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useSupportCannedResponses, useSupportCannedCategories } from '@/hooks/useApi';
import { Button, FilterCard, FilterInput, PageHeader, Select } from '@/components/ui';

type ScopeFilter = 'all' | 'global' | 'team' | 'personal';

const SCOPE_ICONS: Record<string, React.ElementType> = {
  global: Globe,
  team: Users,
  personal: User,
};

const SCOPE_COLORS: Record<string, string> = {
  global: 'text-blue-400 bg-blue-500/10',
  team: 'text-violet-400 bg-violet-500/10',
  personal: 'text-emerald-400 bg-emerald-500/10',
};

export default function InboxCannedResponsesPage() {
  const [search, setSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const scopeOptions = [
    { value: 'all', label: 'All Scopes' },
    { value: 'global', label: 'Global' },
    { value: 'team', label: 'Team' },
    { value: 'personal', label: 'Personal' },
  ];

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useSupportCannedResponses({
    scope: scopeFilter !== 'all' ? scopeFilter : undefined,
    category: categoryFilter !== 'all' ? categoryFilter : undefined,
    search: search || undefined,
  });

  const { data: categoriesData } = useSupportCannedCategories();

  const responses = useMemo(() => data?.items ?? data?.data ?? [], [data?.items, data?.data]);
  const categories = categoriesData || [];

  // Filter locally for search if not already filtered by API
  const filteredResponses = useMemo(() => {
    if (!search) return responses;
    const searchLower = search.toLowerCase();
    return responses.filter(
      (r: any) =>
        r.title?.toLowerCase().includes(searchLower) ||
        r.content?.toLowerCase().includes(searchLower)
    );
  }, [responses, search]);
  const categoryOptions = [
    { value: 'all', label: 'All Categories' },
    ...categories.map((cat: string) => ({ value: cat, label: cat })),
  ];

  const copyToClipboard = async (content: string, id: number) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load canned responses</p>
        <Button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/inbox/settings"
        className="inline-flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to Settings
      </Link>

      {/* Header */}
      <PageHeader
        title="Canned Responses"
        subtitle="Quick reply templates for faster responses"
        icon={MessageCircle}
      />

      {/* Filters */}
      <FilterCard contentClassName="flex flex-wrap items-center gap-4">
        <FilterInput
          type="text"
          placeholder="Search responses..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] max-w-md"
        />
        <Select
          value={scopeFilter}
          onChange={(value) => setScopeFilter(value as ScopeFilter)}
          className="w-32"
          options={scopeOptions}
        />
        {categories.length > 0 && (
          <Select
            value={categoryFilter}
            onChange={(value) => setCategoryFilter(value)}
            className="w-40"
            options={categoryOptions}
          />
        )}
      </FilterCard>

      {/* Responses Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
        </div>
      ) : filteredResponses.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-muted bg-slate-card border border-slate-border rounded-xl">
          <MessageCircle className="w-12 h-12 mb-4 opacity-50" />
          <p>{search || scopeFilter !== 'all' || categoryFilter !== 'all'
            ? 'No responses match your filters'
            : 'No canned responses available'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredResponses.map((response: any) => {
            const ScopeIcon = SCOPE_ICONS[response.scope || 'global'] || Globe;
            const scopeColors = SCOPE_COLORS[response.scope || 'global'] || SCOPE_COLORS.global;

            return (
              <div
                key={response.id}
                className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-muted transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className={cn('p-1.5 rounded-lg', scopeColors)}>
                      <ScopeIcon className="w-3.5 h-3.5" />
                    </div>
                    <h3 className="font-medium text-foreground">{response.title}</h3>
                  </div>
                  <Button
                    onClick={() => copyToClipboard(response.content || '', response.id)}
                    className="p-1.5 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                    title="Copy to clipboard"
                  >
                    {copiedId === response.id ? (
                      <Check className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>

                {response.category && (
                  <span className="inline-block px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted mb-2">
                    {response.category}
                  </span>
                )}

                <p className="text-sm text-slate-muted line-clamp-3">
                  {response.content || 'No content'}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Count */}
      {!isLoading && filteredResponses.length > 0 && (
        <p className="text-sm text-slate-muted text-center">
          Showing {filteredResponses.length} response{filteredResponses.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}
