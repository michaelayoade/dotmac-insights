'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Building2,
  Search,
  Filter,
  Mail,
  MapPin,
  Users,
  UserPlus,
  Globe,
  DollarSign,
} from 'lucide-react';
import { useUnifiedContacts, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';

function formatCurrency(value: number | null | undefined, currency = 'NGN'): string {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

const typeColors: Record<string, string> = {
  lead: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  prospect: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  customer: 'bg-green-500/20 text-green-400 border-green-500/30',
  churned: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const categoryColors: Record<string, string> = {
  residential: 'bg-blue-500/20 text-blue-400',
  business: 'bg-violet-500/20 text-violet-400',
  enterprise: 'bg-amber-500/20 text-amber-400',
  government: 'bg-emerald-500/20 text-emerald-400',
};

export default function OrganizationsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    contact_type: typeFilter as any || undefined,
    category: categoryFilter as any || undefined,
    is_organization: true,
    sort_by: 'name',
    sort_order: 'asc',
  };

  const { data, isLoading, error, mutate } = useUnifiedContacts(params);
  const organizations = data?.items || data?.data || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  // Stats
  const customerCount = organizations.filter((o: UnifiedContact) => o.contact_type === 'customer').length;
  const leadCount = organizations.filter((o: UnifiedContact) => o.contact_type === 'lead' || o.contact_type === 'prospect').length;
  const totalMrr = organizations.reduce((sum: number, o: UnifiedContact) => sum + (o.mrr || 0), 0);

  const columns = [
    {
      key: 'name',
      header: 'Organization',
      render: (item: UnifiedContact) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <p className="text-white font-medium">{item.company_name || item.name}</p>
            {item.email && (
              <span className="flex items-center gap-1 text-xs text-slate-muted mt-0.5">
                <Mail className="w-3 h-3" />
                {item.email}
              </span>
            )}
            {item.website && (
              <span className="flex items-center gap-1 text-xs text-slate-muted">
                <Globe className="w-3 h-3" />
                {item.website}
              </span>
            )}
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
      key: 'category',
      header: 'Category',
      render: (item: UnifiedContact) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
          categoryColors[item.category] || 'bg-slate-500/20 text-slate-400'
        )}>
          {item.category}
        </span>
      ),
    },
    {
      key: 'territory',
      header: 'Territory',
      render: (item: UnifiedContact) => (
        item.territory ? (
          <span className="flex items-center gap-1 text-sm text-slate-300">
            <MapPin className="w-3 h-3 text-slate-muted" />
            {item.territory}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'mrr',
      header: 'MRR',
      align: 'right' as const,
      render: (item: UnifiedContact) => (
        <span className="font-mono text-white">{formatCurrency(item.mrr)}</span>
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

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load organizations"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Organizations"
        subtitle="Companies and business entities"
        icon={Building2}
        iconClassName="bg-cyan-500/10 border border-cyan-500/30"
        actions={
          <Link
            href="/contacts/new?org=1"
            className="flex items-center gap-2 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-400 transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Add Organization
          </Link>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Building2 className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{total}</p>
              <p className="text-xs text-slate-muted">Total Organizations</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Users className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{customerCount}</p>
              <p className="text-xs text-slate-muted">Customers</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Users className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{leadCount}</p>
              <p className="text-xs text-slate-muted">Leads/Prospects</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <DollarSign className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{formatCurrency(totalMrr)}</p>
              <p className="text-xs text-slate-muted">Total MRR</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-cyan-400" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search organizations..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </form>
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            <option value="">All Types</option>
            <option value="lead">Lead</option>
            <option value="prospect">Prospect</option>
            <option value="customer">Customer</option>
            <option value="churned">Churned</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            <option value="">All Categories</option>
            <option value="residential">Residential</option>
            <option value="business">Business</option>
            <option value="enterprise">Enterprise</option>
            <option value="government">Government</option>
          </select>
          {(search || typeFilter || categoryFilter) && (
            <button
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setTypeFilter('');
                setCategoryFilter('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Organizations Table */}
      <DataTable
        columns={columns}
        data={organizations}
        keyField="id"
        loading={isLoading}
        emptyMessage="No organizations found"
        onRowClick={(item) => router.push(`/contacts/${item.id}`)}
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
