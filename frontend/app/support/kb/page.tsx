'use client';

import { useState, useMemo } from 'react';
import { AlertTriangle, BookOpen, Layers, FileText, Eye, EyeOff, CheckCircle2, Clock, FolderOpen } from 'lucide-react';
import { useSupportKbArticles, useSupportKbCategories } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button, FilterCard, FilterInput, FilterSelect } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

export default function SupportKnowledgeBasePage() {
  const [categoryId, setCategoryId] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState('');

  const categories = useSupportKbCategories();
  const articles = useSupportKbArticles({
    category_id: categoryId ? Number(categoryId) : undefined,
    search: search || undefined,
    status: statusFilter || undefined,
    visibility: visibilityFilter || undefined,
    limit: 50,
  });

  const cats = categories.data;
  const articlesList = articles.data?.data;

  // Calculate metrics
  const metrics = useMemo(() => {
    const allArticles = articlesList ?? [];
    const catsList = cats ?? [];
    const published = allArticles.filter((a: any) => a.status === 'published').length;
    const draft = allArticles.filter((a: any) => a.status === 'draft').length;
    const publicVisible = allArticles.filter((a: any) => a.visibility === 'public').length;
    const internalVisible = allArticles.filter((a: any) => a.visibility === 'internal').length;
    return {
      total: allArticles.length,
      published,
      draft,
      publicVisible,
      internalVisible,
      categories: catsList.length,
    };
  }, [articlesList, cats]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
          <BookOpen className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Knowledge Base</h1>
          <p className="text-slate-muted text-sm">Categories, articles, and documentation</p>
        </div>
      </div>

      {/* Error State */}
      {(categories.error || articles.error) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load knowledge base</span>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard title="Total Articles" value={metrics.total} icon={FileText} colorClass="text-blue-400" />
        <StatCard title="Published" value={metrics.published} icon={CheckCircle2} colorClass="text-emerald-400" />
        <StatCard title="Drafts" value={metrics.draft} icon={Clock} colorClass="text-amber-400" />
        <StatCard title="Public" value={metrics.publicVisible} icon={Eye} colorClass="text-violet-400" />
        <StatCard title="Internal" value={metrics.internalVisible} icon={EyeOff} colorClass="text-slate-muted" />
        <StatCard title="Categories" value={metrics.categories} icon={FolderOpen} colorClass="text-cyan-400" />
      </div>

      {/* Filters */}
      <FilterCard contentClassName="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <FilterInput
          type="text"
          placeholder="Search articles..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <FilterSelect
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="">All categories</option>
          {(cats ?? []).map((c: any) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </FilterSelect>
        <FilterSelect
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </FilterSelect>
        <FilterSelect
          value={visibilityFilter}
          onChange={(e) => setVisibilityFilter(e.target.value)}
        >
          <option value="">All visibility</option>
          <option value="public">Public</option>
          <option value="internal">Internal</option>
          <option value="private">Private</option>
        </FilterSelect>
      </FilterCard>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* Categories Sidebar */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <h3 className="text-foreground font-semibold">Categories</h3>
            </div>
            <span className="text-xs text-slate-muted">{(cats ?? []).length} categories</span>
          </div>
          {(cats ?? []).length === 0 ? (
            <p className="text-slate-muted text-sm">No categories configured.</p>
          ) : (
            <div className="space-y-2">
              {(cats ?? []).map((cat: any) => (
                <Button
                  key={cat.id}
                  onClick={() => setCategoryId(categoryId === String(cat.id) ? '' : String(cat.id))}
                  className={cn(
                    'w-full text-left border rounded-lg px-3 py-2.5 transition-colors',
                    categoryId === String(cat.id)
                      ? 'border-teal-electric/50 bg-teal-electric/10'
                      : 'border-slate-border hover:border-slate-border/80 hover:bg-slate-elevated/50'
                  )}
                >
                  <p className={cn('font-semibold', categoryId === String(cat.id) ? 'text-teal-electric' : 'text-foreground')}>
                    {cat.name}
                  </p>
                  <p className="text-slate-muted text-xs line-clamp-1">{cat.description || 'No description'}</p>
                </Button>
              ))}
            </div>
          )}
        </div>

        {/* Articles List */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-blue-400" />
              <h3 className="text-foreground font-semibold">Articles</h3>
            </div>
            <span className="text-xs text-slate-muted">{(articlesList ?? []).length} articles</span>
          </div>
          {!articles.data ? (
            <p className="text-slate-muted text-sm">Loading articles…</p>
          ) : (articlesList ?? []).length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-12 h-12 text-slate-muted mx-auto mb-3" />
              <p className="text-slate-muted text-sm">No articles found.</p>
              <p className="text-slate-muted text-xs mt-1">Try adjusting your filters or search query.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {(articlesList ?? []).map((article: any) => (
                <div key={article.id} className="border border-slate-border rounded-lg p-4 hover:border-slate-border/80 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-foreground font-semibold">{article.title}</p>
                      <p className="text-slate-muted text-sm line-clamp-2 mt-1">{article.excerpt || article.content || 'No content preview'}</p>
                    </div>
                    <div className="flex flex-col gap-1 items-end">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        article.status === 'published'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : article.status === 'draft'
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-slate-elevated text-slate-muted'
                      )}>
                        {article.status || 'draft'}
                      </span>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs',
                        article.visibility === 'public'
                          ? 'bg-violet-500/10 text-violet-400'
                          : 'bg-slate-elevated text-slate-muted'
                      )}>
                        {article.visibility || 'internal'}
                      </span>
                    </div>
                  </div>
                  {article.category_name && (
                    <div className="mt-2 pt-2 border-t border-slate-border/50">
                      <span className="text-xs text-slate-muted flex items-center gap-1">
                        <FolderOpen className="w-3 h-3" />
                        {article.category_name}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
