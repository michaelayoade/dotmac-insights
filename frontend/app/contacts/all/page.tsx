'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Users,
  Search,
  Filter,
  Mail,
  Phone,
  MapPin,
  Tag,
  UserPlus,
  Building2,
  UserCircle,
  Target,
} from 'lucide-react';
import { useUnifiedContacts, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';

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
  person: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

const statusColors: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400',
  inactive: 'bg-gray-500/20 text-gray-400',
  suspended: 'bg-red-500/20 text-red-400',
};

export default function AllContactsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sortBy, setSortBy] = useState<string>('created_at');

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    contact_type: typeFilter as any || undefined,
    status: statusFilter as any || undefined,
    category: categoryFilter as any || undefined,
    sort_by: sortBy as any,
    sort_order: 'desc',
  };

  const { data, isLoading, error, mutate } = useUnifiedContacts(params);
  const contacts = data?.items || data?.data || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  // Count by type
  const typeCounts = contacts.reduce((acc: Record<string, number>, c: UnifiedContact) => {
    acc[c.contact_type] = (acc[c.contact_type] || 0) + 1;
    return acc;
  }, {});

  const columns = [
    {
      key: 'name',
      header: 'Contact',
      render: (item: UnifiedContact) => {
        const Icon = item.is_organization ? Building2 : item.contact_type === 'lead' || item.contact_type === 'prospect' ? Target : UserCircle;
        const iconColor = item.is_organization ? 'text-cyan-400' : item.contact_type === 'customer' ? 'text-emerald-400' : 'text-violet-400';
        const bgColor = item.is_organization ? 'bg-cyan-500/20 border-cyan-500/30' : item.contact_type === 'customer' ? 'bg-emerald-500/20 border-emerald-500/30' : 'bg-violet-500/20 border-violet-500/30';
        return (
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg border flex items-center justify-center', bgColor)}>
              <Icon className={cn('w-5 h-5', iconColor)} />
            </div>
            <div>
              <p className="text-white font-medium">{item.name}</p>
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
        );
      },
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
      key: 'status',
      header: 'Status',
      render: (item: UnifiedContact) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
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
          <span className="flex items-center gap-1 text-sm text-slate-300">
            <MapPin className="w-3 h-3 text-slate-muted" />
            {[item.city, item.state].filter(Boolean).join(', ')}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'tags',
      header: 'Tags',
      render: (item: UnifiedContact) => (
        item.tags && item.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.tags.slice(0, 2).map((tag: string) => (
              <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                <Tag className="w-3 h-3" />
                {tag}
              </span>
            ))}
            {item.tags.length > 2 && (
              <span className="text-xs text-slate-muted">+{item.tags.length - 2}</span>
            )}
          </div>
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

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load contacts"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="All Contacts"
        subtitle="Complete contact directory"
        icon={Users}
        iconClassName="bg-teal-500/10 border border-teal-500/30"
        actions={
          <Link
            href="/contacts/new"
            className="flex items-center gap-2 px-4 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-glow transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Add Contact
          </Link>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-teal-500/20 rounded-lg">
              <Users className="w-5 h-5 text-teal-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{total}</p>
              <p className="text-xs text-slate-muted">Total</p>
            </div>
          </div>
        </div>
        {['customer', 'lead', 'prospect', 'churned'].map((type) => (
          <div key={type} className="bg-slate-card rounded-xl border border-slate-border p-4">
            <div className="flex items-center gap-3">
              <div className={cn('p-2 rounded-lg', typeColors[type]?.split(' ')[0] || 'bg-slate-500/20')}>
                {type === 'customer' ? <Building2 className="w-5 h-5" /> : <Target className="w-5 h-5" />}
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{typeCounts[type] || 0}</p>
                <p className="text-xs text-slate-muted capitalize">{type}s</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-400" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search contacts..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            />
          </form>
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
          >
            <option value="">All Types</option>
            <option value="lead">Lead</option>
            <option value="prospect">Prospect</option>
            <option value="customer">Customer</option>
            <option value="churned">Churned</option>
            <option value="person">Person</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
          >
            <option value="">All Categories</option>
            <option value="residential">Residential</option>
            <option value="business">Business</option>
            <option value="enterprise">Enterprise</option>
            <option value="government">Government</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
          >
            <option value="created_at">Date Created</option>
            <option value="name">Name</option>
            <option value="last_contact_date">Last Contact</option>
            <option value="mrr">MRR</option>
          </select>
          {(search || typeFilter || statusFilter || categoryFilter) && (
            <button
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setTypeFilter('');
                setStatusFilter('');
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

      {/* Contacts Table */}
      <DataTable
        columns={columns}
        data={contacts}
        keyField="id"
        loading={isLoading}
        emptyMessage="No contacts found"
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
