'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Target,
  Search,
  Mail,
  Phone,
  MapPin,
  Users,
  UserPlus,
  Flame,
  Snowflake,
  ThermometerSun,
  Star,
} from 'lucide-react';
import { useUnifiedContactLeads, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay } from '@/components/insights/shared';
import { LoadingState, Button, FilterCard, FilterInput, FilterSelect, PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { useAuth, useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const typeColors: Record<string, string> = {
  lead: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  prospect: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
};

const qualificationColors: Record<string, { bg: string; text: string; icon: typeof Flame }> = {
  cold: { bg: 'bg-blue-500/20', text: 'text-blue-400', icon: Snowflake },
  warm: { bg: 'bg-amber-500/20', text: 'text-amber-400', icon: ThermometerSun },
  hot: { bg: 'bg-orange-500/20', text: 'text-orange-400', icon: Flame },
  qualified: { bg: 'bg-green-500/20', text: 'text-green-400', icon: Star },
  unqualified: { bg: 'bg-gray-500/20', text: 'text-gray-400', icon: Target },
};

export default function LeadsPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const router = useRouter();
  const { hasScope } = useAuth();
  const canWrite = hasScope('crm:write');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [qualificationFilter, setQualificationFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    qualification: qualificationFilter as any || undefined,
    source: sourceFilter || undefined,
    sort_by: 'lead_score',
    sort_order: 'desc',
  };
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error, mutate } = useUnifiedContactLeads(params, { isPaused: () => !canFetch });
  const leads = data?.items || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const qualCounts = leads.reduce((acc: Record<string, number>, lead: UnifiedContact) => {
    const qual = lead.lead_qualification || 'unqualified';
    acc[qual] = (acc[qual] || 0) + 1;
    return acc;
  }, {});

  const columns = [
    {
      key: 'name',
      header: 'Lead',
      render: (item: UnifiedContact) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
            <Target className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <p className="text-foreground font-medium">{item.name}</p>
            {item.company_name && item.company_name !== item.name && (
              <p className="text-slate-muted text-xs">{item.company_name}</p>
            )}
            <div className="flex items-center gap-2 mt-0.5">
              {item.email && (
                <span className="flex items-center gap-1 text-xs text-slate-muted">
                  <Mail className="w-3 h-3" />
                  {item.email}
                </span>
              )}
              {item.phone && (
                <span className="flex items-center gap-1 text-xs text-slate-muted">
                  <Phone className="w-3 h-3" />
                  {item.phone}
                </span>
              )}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'contact_type',
      header: 'Type',
      render: (item: UnifiedContact) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border',
          typeColors[item.contact_type] || typeColors.lead
        )}>
          {item.contact_type}
        </span>
      ),
    },
    {
      key: 'lead_qualification',
      header: 'Qualification',
      render: (item: UnifiedContact) => {
        const qual = item.lead_qualification || 'unqualified';
        const config = qualificationColors[qual] || qualificationColors.unqualified;
        const Icon = config.icon;
        return (
          <div className={cn('flex items-center gap-2 px-2 py-1 rounded-lg w-fit', config.bg)}>
            <Icon className={cn('w-4 h-4', config.text)} />
            <span className={cn('text-xs font-medium capitalize', config.text)}>{qual}</span>
          </div>
        );
      },
    },
    {
      key: 'lead_score',
      header: 'Score',
      align: 'center' as const,
      render: (item: UnifiedContact) => (
        item.lead_score !== null && item.lead_score !== undefined ? (
          <div className="flex items-center justify-center">
            <div className="relative w-10 h-10">
              <svg className="w-10 h-10 transform -rotate-90">
                <circle cx="20" cy="20" r="16" fill="none" stroke="#334155" strokeWidth="3" />
                <circle
                  cx="20" cy="20" r="16" fill="none"
                  stroke={item.lead_score >= 70 ? '#22c55e' : item.lead_score >= 40 ? '#f59e0b' : '#6b7280'}
                  strokeWidth="3"
                  strokeDasharray={`${(item.lead_score / 100) * 100.5} 100.5`}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-foreground">
                {item.lead_score}
              </span>
            </div>
          </div>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-foreground-secondary">{item.source || '-'}</span>
      ),
    },
    {
      key: 'territory',
      header: 'Territory',
      render: (item: UnifiedContact) => (
        item.territory ? (
          <span className="flex items-center gap-1 text-sm text-foreground-secondary">
            <MapPin className="w-3 h-3 text-slate-muted" />
            {item.territory}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-slate-muted">{formatDate(item.created_at)}</span>
      ),
    },
  ];

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view leads."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load leads"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Leads & Prospects"
        subtitle="Track and qualify sales opportunities"
        icon={Target}
        iconClassName="bg-violet-500/10 border border-violet-500/30"
        actions={
          canWrite ? (
            <Link
              href="/crm/contacts/new?type=lead"
              className="flex items-center gap-2 px-4 py-2 bg-violet-500 text-foreground rounded-lg hover:bg-violet-400 transition-colors"
            >
              <UserPlus className="w-4 h-4" />
              Add Lead
            </Link>
          ) : null
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Users className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{total}</p>
              <p className="text-xs text-slate-muted">Total Leads</p>
            </div>
          </div>
        </div>
        {['hot', 'warm', 'cold', 'qualified'].map((qual) => {
          const config = qualificationColors[qual];
          const Icon = config.icon;
          return (
            <div key={qual} className="bg-slate-card rounded-xl border border-slate-border p-4">
              <div className="flex items-center gap-3">
                <div className={cn('p-2 rounded-lg', config.bg)}>
                  <Icon className={cn('w-5 h-5', config.text)} />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{qualCounts[qual] || 0}</p>
                  <p className="text-xs text-slate-muted capitalize">{qual}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filters */}
      <FilterCard
        actions={(search || qualificationFilter || sourceFilter) && (
          <Button
            onClick={() => {
              setSearch('');
              setSearchInput('');
              setQualificationFilter('');
              setSourceFilter('');
              setPage(1);
            }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        iconClassName="text-violet-400"
        contentClassName="flex flex-wrap items-center gap-4"
      >
        <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
          <FilterInput
            type="text"
            placeholder="Search leads..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-10 pr-4 placeholder:text-slate-muted focus:ring-2 focus:ring-violet-500/50"
          />
        </form>
        <FilterSelect
          value={qualificationFilter}
          onChange={(e) => { setQualificationFilter(e.target.value); setPage(1); }}
          className="focus:ring-2 focus:ring-violet-500/50"
        >
          <option value="">All Qualifications</option>
          <option value="cold">Cold</option>
          <option value="warm">Warm</option>
          <option value="hot">Hot</option>
          <option value="qualified">Qualified</option>
          <option value="unqualified">Unqualified</option>
        </FilterSelect>
        <FilterInput
          type="text"
          placeholder="Filter by source..."
          value={sourceFilter}
          onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
          className="w-40 placeholder:text-slate-muted focus:ring-2 focus:ring-violet-500/50"
        />
      </FilterCard>

      {/* Leads Table */}
      <DataTable
        columns={columns}
        data={leads}
        keyField="id"
        loading={isLoading}
        emptyMessage="No leads found"
        onRowClick={(item) => router.push(`/crm/contacts/${item.id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
