'use client';

import { useState } from 'react';
import { Gauge, Plus, Database, ChevronRight, Search } from 'lucide-react';
import Link from 'next/link';
import { useKPIList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import type { KPIDefinition, DataSource } from '@/lib/performance.types';

function getDataSourceColor(source: DataSource): string {
  switch (source) {
    case 'ticketing': return 'text-cyan-400 bg-cyan-400/10';
    case 'field_service': return 'text-emerald-400 bg-emerald-400/10';
    case 'finance': return 'text-amber-400 bg-amber-400/10';
    case 'crm': return 'text-violet-400 bg-violet-400/10';
    case 'project': return 'text-blue-400 bg-blue-400/10';
    case 'manual': return 'text-slate-400 bg-slate-400/10';
    default: return 'text-slate-400 bg-slate-400/10';
  }
}

export default function KPIsPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState('');
  const [dataSourceFilter, setDataSourceFilter] = useState<DataSource | ''>('');

  const { data, isLoading, error, mutate } = useKPIList({
    search: search || undefined,
    data_source: dataSourceFilter || undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'code',
      header: 'KPI',
      render: (item: KPIDefinition) => (
        <div>
          <p className="text-violet-400 font-mono text-sm">{item.code}</p>
          <p className="text-foreground font-medium">{item.name}</p>
        </div>
      ),
    },
    {
      key: 'data_source',
      header: 'Data Source',
      render: (item: KPIDefinition) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium capitalize',
          getDataSourceColor(item.data_source)
        )}>
          {item.data_source.replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'scoring',
      header: 'Scoring',
      render: (item: KPIDefinition) => (
        <div className="text-sm">
          <p className="text-foreground-secondary capitalize">{item.scoring_method}</p>
          <p className="text-slate-500 text-xs">
            {item.higher_is_better ? 'Higher is better' : 'Lower is better'}
          </p>
        </div>
      ),
    },
    {
      key: 'target',
      header: 'Target',
      align: 'right' as const,
      render: (item: KPIDefinition) => (
        <span className="text-foreground font-mono">
          {item.target_value !== null ? item.target_value : '-'}
        </span>
      ),
    },
    {
      key: 'kra_count',
      header: 'KRAs',
      align: 'right' as const,
      render: (item: KPIDefinition) => (
        <span className="text-slate-400">{item.kra_count}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: KPIDefinition) => (
        <Link
          href={`/performance/kpis/${item.id}`}
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
          message="Failed to load KPI definitions"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">KPI Definitions</h1>
          <p className="text-sm text-slate-400 mt-1">
            Key Performance Indicators and scoring rules
          </p>
        </div>
        <Link
          href="/performance/kpis/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-foreground rounded-lg hover:bg-violet-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New KPI
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search KPIs..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            className="w-full pl-9 pr-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-foreground placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          />
        </div>
        <select
          value={dataSourceFilter}
          onChange={(e) => {
            setDataSourceFilter(e.target.value as DataSource | '');
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Sources</option>
          <option value="ticketing">Ticketing</option>
          <option value="field_service">Field Service</option>
          <option value="crm">CRM / Sales</option>
          <option value="project">Projects / Tasks</option>
          <option value="finance">Finance</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      {/* Data Source Stats */}
      <div className="flex gap-3 flex-wrap">
        {[
          { source: 'ticketing', icon: Database, label: 'Ticketing' },
          { source: 'field_service', icon: Database, label: 'Field Service' },
          { source: 'crm', icon: Database, label: 'CRM / Sales' },
          { source: 'project', icon: Database, label: 'Projects' },
          { source: 'manual', icon: Database, label: 'Manual' },
        ].map((item) => {
          const count = data?.items.filter(k => k.data_source === item.source).length || 0;
          return (
            <button
              key={item.source}
              onClick={() => setDataSourceFilter(item.source as DataSource)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                dataSourceFilter === item.source
                  ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                  : 'bg-slate-elevated text-slate-400 border border-slate-border hover:text-foreground'
              )}
            >
              <item.icon className="w-3.5 h-3.5" />
              {item.label}
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
        emptyMessage="No KPI definitions found"
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
