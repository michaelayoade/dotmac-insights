'use client';

import { useState } from 'react';
import {
  Target,
  Plus,
  ChevronRight,
  Search,
  Link2,
} from 'lucide-react';
import Link from 'next/link';
import { useKRAList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import type { KRADefinition } from '@/lib/performance.types';

const CATEGORY_COLORS: Record<string, string> = {
  'Operations': 'text-cyan-400 bg-cyan-400/10',
  'Customer': 'text-emerald-400 bg-emerald-400/10',
  'Behavior': 'text-violet-400 bg-violet-400/10',
  'Financial': 'text-amber-400 bg-amber-400/10',
  'Learning': 'text-pink-400 bg-pink-400/10',
};

function getCategoryColor(category: string | null): string {
  if (!category) return 'text-slate-400 bg-slate-400/10';
  return CATEGORY_COLORS[category] || 'text-slate-400 bg-slate-400/10';
}

export default function KRAsPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const { data, isLoading, error, mutate } = useKRAList({
    search: search || undefined,
    category: categoryFilter || undefined,
    limit,
    offset,
  });

  // Get unique categories from data
  const categories = data?.items
    ? Array.from(new Set(data.items.map(k => k.category).filter((c): c is string => Boolean(c))))
    : [];

  const columns = [
    {
      key: 'code',
      header: 'KRA',
      render: (item: KRADefinition) => (
        <div>
          <p className="text-violet-400 font-mono text-sm">{item.code}</p>
          <Link
            href={`/performance/kras/${item.id}`}
            className="text-foreground font-medium hover:text-violet-400"
          >
            {item.name}
          </Link>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (item: KRADefinition) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
          getCategoryColor(item.category)
        )}>
          {item.category || 'Uncategorized'}
        </span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item: KRADefinition) => (
        <p className="text-slate-400 text-sm max-w-md truncate">
          {item.description || '-'}
        </p>
      ),
    },
    {
      key: 'kpis',
      header: 'Linked KPIs',
      align: 'center' as const,
      render: (item: KRADefinition) => (
        <div className="flex items-center justify-center gap-1">
          <Link2 className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-foreground font-medium">{item.kpi_count}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: KRADefinition) => (
        item.is_active ? (
          <span className="px-2 py-1 rounded-full text-xs font-medium text-emerald-400 bg-emerald-400/10">
            Active
          </span>
        ) : (
          <span className="px-2 py-1 rounded-full text-xs font-medium text-slate-400 bg-slate-400/10">
            Inactive
          </span>
        )
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: KRADefinition) => (
        <Link
          href={`/performance/kras/${item.id}`}
          className="text-slate-400 hover:text-foreground p-1"
        >
          <ChevronRight className="w-4 h-4" />
        </Link>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load KRA definitions"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Key Result Areas</h1>
          <p className="text-sm text-slate-400 mt-1">
            KRAs group related KPIs for structured evaluation
          </p>
        </div>
        <Link
          href="/performance/kras/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-foreground rounded-lg hover:bg-violet-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New KRA
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search KRAs..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            className="w-full pl-9 pr-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-foreground placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Category Quick Filters */}
      <div className="flex gap-3 flex-wrap">
        {Object.keys(CATEGORY_COLORS).map((category) => {
          const count = data?.items.filter(k => k.category === category).length || 0;
          return (
            <button
              key={category}
              onClick={() => setCategoryFilter(category === categoryFilter ? '' : category)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                categoryFilter === category
                  ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                  : 'bg-slate-elevated text-slate-400 border border-slate-border hover:text-foreground'
              )}
            >
              <Target className="w-3.5 h-3.5" />
              {category}
              <span className="ml-1 text-xs opacity-70">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No KRA definitions found"
      />

      {/* Pagination */}
      {data && data.total > limit && (
        <Pagination
          total={data.total}
          limit={limit}
          offset={offset}
          onPageChange={setOffset}
          onLimitChange={(newLimit) => {
            setLimit(newLimit);
            setOffset(0);
          }}
        />
      )}
    </div>
  );
}
