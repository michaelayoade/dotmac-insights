'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  UserCircle,
  Search,
  Filter,
  Mail,
  Phone,
  Building2,
  UserPlus,
  Briefcase,
  Star,
  CheckCircle,
} from 'lucide-react';
import { useUnifiedContacts, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth-context';

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function PeoplePage() {
  const router = useRouter();
  const { hasScope } = useAuth();
  const canWrite = hasScope('contacts:write');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    is_organization: false,
    sort_by: 'name',
    sort_order: 'asc',
  };

  const { data, isLoading, error, mutate } = useUnifiedContacts(params);
  const people = data?.items || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  // Stats
  const primaryContacts = people.filter((p: UnifiedContact) => p.is_primary_contact).length;
  const decisionMakers = people.filter((p: UnifiedContact) => p.is_decision_maker).length;
  const billingContacts = people.filter((p: UnifiedContact) => p.is_billing_contact).length;

  const columns = [
    {
      key: 'name',
      header: 'Person',
      render: (item: UnifiedContact) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
            <UserCircle className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-foreground font-medium">{item.name}</p>
              {item.is_primary_contact && (
                <Star className="w-3 h-3 text-amber-400" fill="currentColor" />
              )}
              {item.is_decision_maker && (
                <CheckCircle className="w-3 h-3 text-emerald-400" />
              )}
            </div>
            {item.designation && (
              <p className="text-slate-muted text-xs flex items-center gap-1">
                <Briefcase className="w-3 h-3" />
                {item.designation}
              </p>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'company',
      header: 'Organization',
      render: (item: UnifiedContact) => (
        item.company_name ? (
          <span className="flex items-center gap-2 text-sm text-foreground-secondary">
            <Building2 className="w-4 h-4 text-slate-muted" />
            {item.company_name}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      render: (item: UnifiedContact) => (
        item.email ? (
          <a
            href={`mailto:${item.email}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300"
          >
            <Mail className="w-3 h-3" />
            {item.email}
          </a>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'phone',
      header: 'Phone',
      render: (item: UnifiedContact) => (
        item.phone || item.mobile ? (
          <a
            href={`tel:${item.phone || item.mobile}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-sm text-foreground-secondary hover:text-foreground"
          >
            <Phone className="w-3 h-3 text-slate-muted" />
            {item.phone || item.mobile}
          </a>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'department',
      header: 'Department',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-foreground-secondary">{item.department || '-'}</span>
      ),
    },
    {
      key: 'roles',
      header: 'Roles',
      render: (item: UnifiedContact) => (
        <div className="flex gap-1 flex-wrap">
          {item.is_primary_contact && (
            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-xs">Primary</span>
          )}
          {item.is_billing_contact && (
            <span className="px-2 py-0.5 bg-violet-500/20 text-violet-400 rounded text-xs">Billing</span>
          )}
          {item.is_decision_maker && (
            <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-xs">Decision Maker</span>
          )}
        </div>
      ),
    },
    {
      key: 'created_at',
      header: 'Added',
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
          message="Failed to load people"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="People"
        subtitle="Individual contacts and team members"
        icon={UserCircle}
        iconClassName="bg-purple-500/10 border border-purple-500/30"
        actions={
          canWrite ? (
            <Link
              href="/contacts/new?type=person"
              className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-foreground rounded-lg hover:bg-purple-400 transition-colors"
            >
              <UserPlus className="w-4 h-4" />
              Add Person
            </Link>
          ) : null
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <UserCircle className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{total}</p>
              <p className="text-xs text-slate-muted">Total People</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Star className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{primaryContacts}</p>
              <p className="text-xs text-slate-muted">Primary Contacts</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{decisionMakers}</p>
              <p className="text-xs text-slate-muted">Decision Makers</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Briefcase className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{billingContacts}</p>
              <p className="text-xs text-slate-muted">Billing Contacts</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-purple-400" />
          <span className="text-foreground text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search people..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-purple-500/50"
            />
          </form>
          {search && (
            <button
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* People Table */}
      <DataTable
        columns={columns}
        data={people}
        keyField="id"
        loading={isLoading}
        emptyMessage="No people found"
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
