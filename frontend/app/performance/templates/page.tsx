'use client';

import { useState } from 'react';
import {
  FileText,
  Plus,
  Copy,
  ChevronRight,
  Check,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useTemplateList } from '@/hooks/usePerformance';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import type { ScorecardTemplate } from '@/lib/performance.types';

export default function TemplatesPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [activeOnly, setActiveOnly] = useState(true);

  const { data, isLoading, error, mutate } = useTemplateList({
    active_only: activeOnly || undefined,
    limit,
    offset,
  });

  const columns = [
    {
      key: 'code',
      header: 'Template',
      render: (item: ScorecardTemplate) => (
        <div>
          <Link
            href={`/performance/templates/${item.id}`}
            className="text-violet-400 hover:text-violet-300 font-medium"
          >
            {item.code}
          </Link>
          <p className="text-sm text-slate-400">{item.name}</p>
        </div>
      ),
    },
    {
      key: 'applicability',
      header: 'Applies To',
      render: (item: ScorecardTemplate) => (
        <div className="text-sm">
          {item.applicable_departments && item.applicable_departments.length > 0 ? (
            <p className="text-slate-300">
              {item.applicable_departments.slice(0, 2).join(', ')}
              {item.applicable_departments.length > 2 && (
                <span className="text-slate-500"> +{item.applicable_departments.length - 2}</span>
              )}
            </p>
          ) : (
            <p className="text-emerald-400">All Departments</p>
          )}
          {item.applicable_designations && item.applicable_designations.length > 0 && (
            <p className="text-xs text-slate-500">
              {item.applicable_designations.length} designation(s)
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'kras',
      header: 'KRAs',
      align: 'center' as const,
      render: (item: ScorecardTemplate) => (
        <span className="text-white font-medium">{item.items?.length ?? 0}</span>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      render: (item: ScorecardTemplate) => (
        <span className="text-slate-400 font-mono text-sm">v{item.version}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: ScorecardTemplate) => (
        <div className="flex items-center gap-2">
          {item.is_active ? (
            <span className="px-2 py-1 rounded-full text-xs font-medium text-emerald-400 bg-emerald-400/10">
              Active
            </span>
          ) : (
            <span className="px-2 py-1 rounded-full text-xs font-medium text-slate-400 bg-slate-400/10">
              Inactive
            </span>
          )}
          {item.is_default && (
            <span className="px-2 py-1 rounded-full text-xs font-medium text-violet-400 bg-violet-400/10">
              Default
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right' as const,
      render: (item: ScorecardTemplate) => (
        <div className="flex items-center gap-2 justify-end">
          <button
            title="Clone template"
            className="p-1 text-slate-400 hover:text-white"
          >
            <Copy className="w-4 h-4" />
          </button>
          <Link
            href={`/performance/templates/${item.id}`}
            className="text-slate-400 hover:text-white p-1"
          >
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load scorecard templates"
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Scorecard Templates</h1>
          <p className="text-sm text-slate-400 mt-1">
            Define KRA structures for performance evaluation
          </p>
        </div>
        <Link
          href="/performance/templates/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Template
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <button
          onClick={() => setActiveOnly(!activeOnly)}
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
            activeOnly
              ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
              : 'bg-slate-elevated text-slate-400 border border-slate-border hover:text-white'
          )}
        >
          {activeOnly ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
          Active Only
        </button>
      </div>

      {/* Info Card */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-start gap-3">
          <FileText className="w-5 h-5 text-violet-400 mt-0.5" />
          <div>
            <h3 className="font-medium text-white">About Templates</h3>
            <p className="text-sm text-slate-400 mt-1">
              Templates define which KRAs are evaluated and their weightages. When generating
              scorecards for a period, the system matches employees to templates based on
              department and designation. The default template is used when no specific match is found.
            </p>
          </div>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No scorecard templates found"
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
