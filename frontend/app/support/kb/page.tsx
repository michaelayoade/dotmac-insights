'use client';

import { useState } from 'react';
import { AlertTriangle, BookOpen, Filter, Layers } from 'lucide-react';
import { useSupportKbArticles, useSupportKbCategories } from '@/hooks/useApi';

export default function SupportKnowledgeBasePage() {
  const [categoryId, setCategoryId] = useState('');
  const categories = useSupportKbCategories();
  const articles = useSupportKbArticles(categoryId ? { category_id: Number(categoryId) } : undefined);

  const cats = categories.data || [];
  const articlesList = articles.data?.data || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">Knowledge Base</h1>
          <p className="text-slate-muted text-sm">Categories and articles</p>
        </div>
      </div>

      {(categories.error || articles.error) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load knowledge base</span>
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filter by category</span>
        </div>
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All categories</option>
          {cats.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Categories</span>
          </div>
          {cats.length === 0 ? (
            <p className="text-slate-muted text-sm">No categories.</p>
          ) : (
            <div className="space-y-2">
              {cats.map((cat) => (
                <div key={cat.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <p className="text-white font-semibold">{cat.name}</p>
                  <p className="text-slate-muted text-xs">{cat.description || 'No description'}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Articles</span>
          </div>
          {!articles.data ? (
            <p className="text-slate-muted text-sm">Loading articles…</p>
          ) : articlesList.length === 0 ? (
            <p className="text-slate-muted text-sm">No articles found.</p>
          ) : (
            <div className="space-y-2">
              {articlesList.map((article) => (
                <div key={article.id} className="border border-slate-border rounded-lg px-3 py-2">
                  <p className="text-white font-semibold">{article.title}</p>
                  <p className="text-slate-muted text-xs line-clamp-2">{article.excerpt || article.content || ''}</p>
                  <p className="text-[10px] text-slate-muted mt-1">Status: {article.status || '-'} • Visibility: {article.visibility || '-'}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
