'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  useUnifiedContacts,
  useUnifiedContactsDashboard,
  useUnifiedContactsFunnel,
  UnifiedContactsParams,
  type UnifiedContact,
  type UnifiedContactsDashboard,
  type UnifiedContactsFunnel,
  type UnifiedContactsResponse,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  Users,
  UserPlus,
  Building2,
  TrendingUp,
  TrendingDown,
  Search,
  Filter,
  ChevronRight,
  Phone,
  Mail,
  MapPin,
  Tag,
  Clock,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';

function formatCurrency(value: number, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatDate(value?: string | null): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  className?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, trend, trendValue, className }: StatCardProps) {
  return (
    <div className={cn('bg-slate-card rounded-xl border border-slate-border p-6', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-slate-muted text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
          {trend && trendValue && (
            <div className={cn(
              'flex items-center gap-1 mt-2 text-sm',
              trend === 'up' && 'text-green-400',
              trend === 'down' && 'text-red-400',
              trend === 'neutral' && 'text-slate-muted'
            )}>
              {trend === 'up' && <TrendingUp className="w-4 h-4" />}
              {trend === 'down' && <TrendingDown className="w-4 h-4" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        <div className="p-3 bg-slate-elevated rounded-lg">
          <Icon className="w-6 h-6 text-teal-electric" />
        </div>
      </div>
    </div>
  );
}

const contactTypeColors: Record<string, string> = {
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
  do_not_contact: 'bg-red-500/20 text-red-400',
};

const qualificationColors: Record<string, string> = {
  unqualified: 'bg-gray-500/20 text-gray-400',
  cold: 'bg-blue-500/20 text-blue-400',
  warm: 'bg-amber-500/20 text-amber-400',
  hot: 'bg-orange-500/20 text-orange-400',
  qualified: 'bg-green-500/20 text-green-400',
};

export default function ContactsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initializedFromQuery = useRef(false);
  const [params, setParams] = useState<UnifiedContactsParams>({
    page: 1,
    page_size: 20,
    sort_by: 'created_at',
    sort_order: 'desc',
  });
  const [searchInput, setSearchInput] = useState('');

  useEffect(() => {
    if (initializedFromQuery.current) return;
    initializedFromQuery.current = true;

    const nextParams: UnifiedContactsParams = {};
    const type = searchParams.get('type') as UnifiedContactsParams['contact_type'] | null;
    const status = searchParams.get('status') as UnifiedContactsParams['status'] | null;
    const category = searchParams.get('category') as UnifiedContactsParams['category'] | null;
    const qualification = searchParams.get('qualification') as UnifiedContactsParams['qualification'] | null;
    const territory = searchParams.get('territory');
    const tag = searchParams.get('tag');
    const org = searchParams.get('org');
    const search = searchParams.get('search');

    if (type) nextParams.contact_type = type;
    if (status) nextParams.status = status;
    if (category) nextParams.category = category;
    if (qualification) nextParams.qualification = qualification;
    if (territory) nextParams.territory = territory;
    if (tag) nextParams.tag = tag;
    if (org === '1') nextParams.is_organization = true;
    if (org === '0') nextParams.is_organization = false;

    if (search) {
      nextParams.search = search;
      setSearchInput(search);
    }

    if (Object.keys(nextParams).length > 0) {
      setParams((prev) => ({ ...prev, ...nextParams, page: 1 }));
    }
  }, [searchParams]);

  const { data: contacts, isLoading, error, mutate } = useUnifiedContacts(params) as {
    data?: UnifiedContactsResponse;
    isLoading: boolean;
    error?: unknown;
    mutate: () => Promise<any>;
  };
  const { data: dashboard, isLoading: dashboardLoading } = useUnifiedContactsDashboard(30) as {
    data?: UnifiedContactsDashboard;
    isLoading: boolean;
  };
  const { data: funnel } = useUnifiedContactsFunnel(30) as { data?: UnifiedContactsFunnel };
  const totalPages = contacts
    ? contacts.total_pages ?? Math.max(1, Math.ceil((contacts.total || 0) / (params.page_size || 20)))
    : 1;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setParams({ ...params, search: searchInput, page: 1 });
  };

  const handleFilterChange = (key: keyof UnifiedContactsParams, value: string | undefined) => {
    setParams({ ...params, [key]: value || undefined, page: 1 });
  };

  if (isLoading && !contacts) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {Boolean(error) && (
        <ErrorDisplay
          message="Failed to load contacts"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      <PageHeader
        title="Unified Contacts"
        subtitle="Manage leads, prospects, customers, and contacts in one place"
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

      {/* Dashboard Cards */}
      {!dashboardLoading && dashboard ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Contacts"
            value={formatNumber(dashboard.overview?.total_contacts || 0)}
            icon={Users}
          />
          <StatCard
            title="Leads"
            value={formatNumber(dashboard.overview?.leads || 0)}
            subtitle={`Prospects: ${dashboard.overview?.prospects || 0}`}
            icon={UserPlus}
          />
          <StatCard
            title="Customers"
            value={formatNumber(dashboard.overview?.customers || 0)}
            subtitle={`Active: ${dashboard.status_distribution?.active || 0}`}
            icon={Building2}
          />
          <StatCard
            title="Total MRR"
            value={formatCurrency(dashboard.financials?.total_mrr || 0)}
            subtitle={`Avg: ${formatCurrency(dashboard.financials?.avg_mrr || 0)}`}
            icon={TrendingUp}
          />
          <StatCard
            title="New This Month"
            value={formatNumber(dashboard.period_metrics?.new_contacts || 0)}
            trend={(dashboard.period_metrics?.new_contacts_change ?? 0) >= 0 ? 'up' : 'down'}
            trendValue={`${(dashboard.period_metrics?.new_contacts_change ?? 0) >= 0 ? '+' : ''}${dashboard.period_metrics?.new_contacts_change ?? 0}`}
            icon={Clock}
          />
        </div>
      ) : null}

      {/* Funnel */}
      {funnel ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Sales Funnel (30 days)</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-white">{funnel.funnel?.leads_created || 0}</p>
              <p className="text-sm text-slate-muted">Leads Created</p>
            </div>
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-white">{funnel.funnel?.prospects_qualified || 0}</p>
              <p className="text-sm text-slate-muted">Qualified</p>
              <p className="text-xs text-teal-electric mt-1">{funnel.conversion_rates?.lead_to_prospect}% rate</p>
            </div>
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-white">{funnel.funnel?.customers_converted || 0}</p>
              <p className="text-sm text-slate-muted">Converted</p>
              <p className="text-xs text-green-400 mt-1">{funnel.conversion_rates?.overall}% overall</p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
              <input
                type="text"
                placeholder="Search contacts..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder:text-slate-muted focus:outline-none focus:border-teal-electric"
              />
            </div>
          </form>

          <select
            value={params.contact_type || ''}
            onChange={(e) => handleFilterChange('contact_type', e.target.value as any)}
            className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:border-teal-electric"
          >
            <option value="">All Types</option>
            <option value="lead">Leads</option>
            <option value="prospect">Prospects</option>
            <option value="customer">Customers</option>
            <option value="churned">Churned</option>
          </select>

          <select
            value={params.status || ''}
            onChange={(e) => handleFilterChange('status', e.target.value as any)}
            className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:border-teal-electric"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
          </select>

          <select
            value={params.category || ''}
            onChange={(e) => handleFilterChange('category', e.target.value as any)}
            className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:border-teal-electric"
          >
            <option value="">All Categories</option>
            <option value="residential">Residential</option>
            <option value="business">Business</option>
            <option value="enterprise">Enterprise</option>
            <option value="government">Government</option>
          </select>

          <select
            value={params.sort_by || 'created_at'}
            onChange={(e) => handleFilterChange('sort_by', e.target.value as any)}
            className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:border-teal-electric"
          >
            <option value="created_at">Date Created</option>
            <option value="name">Name</option>
            <option value="last_contact_date">Last Contact</option>
            <option value="mrr">MRR</option>
            <option value="lead_score">Lead Score</option>
          </select>
        </div>
      </div>

      {/* Contact List */}
      <div className="bg-slate-card rounded-xl border border-slate-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-elevated">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Contact</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Type</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Location</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">MRR</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Tags</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Created</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border/50">
              {contacts?.items?.map((contact: UnifiedContact) => (
                <tr
                  key={contact.id}
                  className="hover:bg-slate-elevated/30 transition-colors cursor-pointer"
                  onClick={() => router.push(`/contacts/${contact.id}`)}
                >
                  <td className="px-4 py-4">
                    <div>
                      <p className="text-white font-medium">{contact.name}</p>
                      {contact.company_name && contact.company_name !== contact.name && (
                        <p className="text-sm text-slate-muted">{contact.company_name}</p>
                      )}
                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-muted">
                        {contact.email && (
                          <span className="flex items-center gap-1">
                            <Mail className="w-3 h-3" />
                            {contact.email}
                          </span>
                        )}
                        {contact.phone && (
                          <span className="flex items-center gap-1">
                            <Phone className="w-3 h-3" />
                            {contact.phone}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <span className={cn(
                      'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border',
                      contactTypeColors[contact.contact_type] || contactTypeColors.lead
                    )}>
                      {contact.contact_type}
                    </span>
                    {contact.lead_qualification && (
                      <span className={cn(
                        'ml-1 inline-flex items-center px-2 py-1 rounded-full text-xs',
                        qualificationColors[contact.lead_qualification] || qualificationColors.unqualified
                      )}>
                        {contact.lead_qualification}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <span className={cn(
                      'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                      statusColors[contact.status] || statusColors.active
                    )}>
                      {contact.status}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {(contact.city || contact.state) && (
                      <span className="flex items-center gap-1 text-sm text-slate-muted">
                        <MapPin className="w-3 h-3" />
                        {[contact.city, contact.state].filter(Boolean).join(', ')}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    {contact.mrr ? (
                      <span className="text-white font-mono text-sm">
                        {formatCurrency(contact.mrr)}
                      </span>
                    ) : (
                      <span className="text-slate-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    {contact.tags && contact.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {contact.tags.slice(0, 2).map((tag: string) => (
                          <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                            <Tag className="w-3 h-3" />
                            {tag}
                          </span>
                        ))}
                        {contact.tags.length > 2 && (
                          <span className="text-xs text-slate-muted">+{contact.tags.length - 2}</span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-muted">
                    {formatDate(contact.created_at)}
                  </td>
                  <td className="px-4 py-4">
                    <Link
                      href={`/contacts/${contact.id}`}
                      className="p-2 hover:bg-slate-elevated rounded-lg transition-colors inline-flex"
                    >
                      <ChevronRight className="w-4 h-4 text-slate-muted" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {contacts && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-border">
            <p className="text-sm text-slate-muted">
              Showing {((params.page || 1) - 1) * (params.page_size || 20) + 1} to{' '}
              {Math.min((params.page || 1) * (params.page_size || 20), contacts.total)} of {contacts.total} contacts
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setParams({ ...params, page: (params.page || 1) - 1 })}
                disabled={params.page === 1}
                className="px-3 py-1 text-sm bg-slate-elevated border border-slate-border rounded hover:bg-slate-border disabled:opacity-50 disabled:cursor-not-allowed text-white"
              >
                Previous
              </button>
              <span className="text-sm text-slate-muted">
                Page {params.page || 1} of {totalPages}
              </span>
              <button
                onClick={() => setParams({ ...params, page: (params.page || 1) + 1 })}
                disabled={(params.page || 1) >= totalPages}
                className="px-3 py-1 text-sm bg-slate-elevated border border-slate-border rounded hover:bg-slate-border disabled:opacity-50 disabled:cursor-not-allowed text-white"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
