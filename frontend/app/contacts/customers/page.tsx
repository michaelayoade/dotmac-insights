'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Building2,
  Search,
  Filter,
  ChevronRight,
  Phone,
  Mail,
  MapPin,
  DollarSign,
  AlertCircle,
  TrendingUp,
  Users,
  UserPlus,
} from 'lucide-react';
import { useUnifiedContactCustomers, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth-context';

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

const statusColors: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  inactive: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  suspended: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const categoryColors: Record<string, string> = {
  residential: 'bg-blue-500/20 text-blue-400',
  business: 'bg-violet-500/20 text-violet-400',
  enterprise: 'bg-amber-500/20 text-amber-400',
  government: 'bg-emerald-500/20 text-emerald-400',
};

export default function CustomersPage() {
  const router = useRouter();
  const { hasScope } = useAuth();
  const canWrite = hasScope('contacts:write');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [hasOutstanding, setHasOutstanding] = useState<boolean | undefined>();

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    status: statusFilter as any || undefined,
    category: categoryFilter as any || undefined,
    has_outstanding: hasOutstanding,
    sort_by: 'name',
    sort_order: 'asc',
  };

  const { data, isLoading, error, mutate } = useUnifiedContactCustomers(params);
  const customers = data?.items || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  // Calculate stats from current data
  const activeCount = customers.filter((c: UnifiedContact) => c.status === 'active').length;
  const totalMrr = customers.reduce((sum: number, c: UnifiedContact) => sum + (c.mrr || 0), 0);
  const withOutstanding = customers.filter((c: UnifiedContact) => (c.outstanding_balance || 0) > 0).length;

  const columns = [
    {
      key: 'name',
      header: 'Customer',
      render: (item: UnifiedContact) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-emerald-400" />
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
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (item: UnifiedContact) => {
        const categoryKey = item.category || 'unknown';
        return (
          <span className={cn(
            'px-2 py-1 rounded-full text-xs font-medium',
            categoryColors[categoryKey] || 'bg-slate-500/20 text-slate-400'
          )}>
            {item.category || 'Unknown'}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: UnifiedContact) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border',
          statusColors[item.status] || statusColors.active
        )}>
          {item.status}
        </span>
      ),
    },
    {
      key: 'location',
      header: 'Location',
      render: (item: UnifiedContact) => (
        item.city || item.state ? (
          <span className="flex items-center gap-1 text-sm text-foreground-secondary">
            <MapPin className="w-3 h-3 text-slate-muted" />
            {[item.city, item.state].filter(Boolean).join(', ')}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'mrr',
      header: 'MRR',
      align: 'right' as const,
      render: (item: UnifiedContact) => (
        <span className="font-mono text-foreground">{formatCurrency(item.mrr)}</span>
      ),
    },
    {
      key: 'outstanding',
      header: 'Outstanding',
      align: 'right' as const,
      render: (item: UnifiedContact) => (
        <span className={cn(
          'font-mono',
          (item.outstanding_balance || 0) > 0 ? 'text-red-400' : 'text-slate-muted'
        )}>
          {formatCurrency(item.outstanding_balance)}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Customer Since',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-slate-muted">{formatDate(item.conversion_date || item.created_at)}</span>
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
          message="Failed to load customers"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Customers"
        subtitle="Active customer accounts"
        icon={Building2}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
        actions={
          canWrite ? (
            <Link
              href="/contacts/new?type=customer"
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-foreground rounded-lg hover:bg-emerald-400 transition-colors"
            >
              <UserPlus className="w-4 h-4" />
              Add Customer
            </Link>
          ) : null
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Users className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{total}</p>
              <p className="text-xs text-slate-muted">Total Customers</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <TrendingUp className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{activeCount}</p>
              <p className="text-xs text-slate-muted">Active</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <DollarSign className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{formatCurrency(totalMrr)}</p>
              <p className="text-xs text-slate-muted">Total MRR</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{withOutstanding}</p>
              <p className="text-xs text-slate-muted">With Balance</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-emerald-400" />
          <span className="text-foreground text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search customers..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
          </form>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="">All Categories</option>
            <option value="residential">Residential</option>
            <option value="business">Business</option>
            <option value="enterprise">Enterprise</option>
            <option value="government">Government</option>
          </select>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={hasOutstanding === true}
              onChange={(e) => { setHasOutstanding(e.target.checked ? true : undefined); setPage(1); }}
              className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-emerald-500"
            />
            <span className="text-sm text-foreground-secondary">With Outstanding</span>
          </label>
          {(search || statusFilter || categoryFilter || hasOutstanding) && (
            <button
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setStatusFilter('');
                setCategoryFilter('');
                setHasOutstanding(undefined);
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Customers Table */}
      <DataTable
        columns={columns}
        data={customers}
        keyField="id"
        loading={isLoading}
        emptyMessage="No customers found"
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
