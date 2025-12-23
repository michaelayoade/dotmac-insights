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
import { formatCurrency, formatNumber, formatDate } from '@/lib/formatters';
import { useAuth, useRequireScope } from '@/lib/auth-context';
import {
  Users,
  UserPlus,
  Building2,
  TrendingUp,
  Search,
  ChevronRight,
  Phone,
  Mail,
  MapPin,
  Tag,
  Clock,
  Target,
  Kanban,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { Button, FilterCard, FilterInput, FilterSelect, PageHeader } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { AccessDenied } from '@/components/AccessDenied';

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

export default function CRMDashboardPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const router = useRouter();
  const searchParams = useSearchParams();
  const { hasScope } = useAuth();
  const canWrite = hasScope('crm:write');
  const initializedFromQuery = useRef(false);
  const [params, setParams] = useState<UnifiedContactsParams>({
    page: 1,
    page_size: 10,
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
    const search = searchParams.get('search');

    if (type) nextParams.contact_type = type;
    if (status) nextParams.status = status;
    if (search) {
      nextParams.search = search;
      setSearchInput(search);
    }

    if (Object.keys(nextParams).length > 0) {
      setParams((prev) => ({ ...prev, ...nextParams, page: 1 }));
    }
  }, [searchParams]);

  const canFetch = !authLoading && !missingScope;

  const { data: contacts, isLoading, error, mutate } = useUnifiedContacts(
    params,
    { isPaused: () => !canFetch }
  ) as {
    data?: UnifiedContactsResponse;
    isLoading: boolean;
    error?: unknown;
    mutate: () => Promise<any>;
  };
  const { data: dashboard, isLoading: dashboardLoading } = useUnifiedContactsDashboard(
    30,
    { isPaused: () => !canFetch }
  ) as {
    data?: UnifiedContactsDashboard;
    isLoading: boolean;
  };
  const { data: funnel } = useUnifiedContactsFunnel(
    30,
    undefined,
    { isPaused: () => !canFetch }
  ) as { data?: UnifiedContactsFunnel };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setParams({ ...params, search: searchInput, page: 1 });
  };

  const handleFilterChange = (key: keyof UnifiedContactsParams, value: string | undefined) => {
    setParams({ ...params, [key]: value || undefined, page: 1 });
  };

  if (authLoading) {
    return <LoadingState />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view the CRM."
        backHref="/"
        backLabel="Back to Home"
      />
    );
  }

  if (isLoading && !contacts) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {Boolean(error) && (
        <ErrorDisplay
          message="Failed to load CRM data"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      <PageHeader
        title="CRM Dashboard"
        subtitle="Unified contact and pipeline management"
        icon={Users}
        iconClassName="bg-cyan-500/10 border border-cyan-500/30"
        actions={
          canWrite ? (
            <div className="flex items-center gap-2">
              <Link
                href="/crm/contacts/new"
                className="flex items-center gap-2 px-4 py-2 bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-lg hover:bg-cyan-500/30 transition-colors"
              >
                <UserPlus className="w-4 h-4" />
                Add Contact
              </Link>
              <Link
                href="/crm/pipeline/opportunities/new"
                className="flex items-center gap-2 px-4 py-2 bg-teal-electric text-foreground rounded-lg hover:bg-teal-glow transition-colors"
              >
                <Target className="w-4 h-4" />
                New Deal
              </Link>
            </div>
          ) : null
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
            trend={{ value: dashboard.period_metrics?.new_contacts_change ?? 0 }}
            icon={Clock}
          />
        </div>
      ) : null}

      {/* Quick Access Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/crm/contacts/all"
          className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-cyan-500/50 transition group"
        >
          <div>
            <p className="text-sm text-slate-muted">Contact Directory</p>
            <p className="text-foreground font-semibold">Browse all contacts</p>
          </div>
          <Users className="w-5 h-5 text-cyan-400 group-hover:scale-110 transition-transform" />
        </Link>
        <Link
          href="/crm/pipeline"
          className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-emerald-500/50 transition group"
        >
          <div>
            <p className="text-sm text-slate-muted">Sales Pipeline</p>
            <p className="text-foreground font-semibold">Manage opportunities</p>
          </div>
          <Kanban className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" />
        </Link>
        <Link
          href="/crm/lifecycle/funnel"
          className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between hover:border-violet-500/50 transition group"
        >
          <div>
            <p className="text-sm text-slate-muted">Sales Funnel</p>
            <p className="text-foreground font-semibold">Conversion metrics</p>
          </div>
          <Target className="w-5 h-5 text-violet-400 group-hover:scale-110 transition-transform" />
        </Link>
      </div>

      {/* Funnel */}
      {funnel ? (
        <div className="bg-slate-card rounded-xl border border-slate-border p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Sales Funnel (30 days)</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-foreground">{funnel.funnel?.leads_created || 0}</p>
              <p className="text-sm text-slate-muted">Leads Created</p>
            </div>
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-foreground">{funnel.funnel?.prospects_qualified || 0}</p>
              <p className="text-sm text-slate-muted">Qualified</p>
              <p className="text-xs text-cyan-400 mt-1">{funnel.conversion_rates?.lead_to_prospect}% rate</p>
            </div>
            <div className="text-center p-4 bg-slate-elevated rounded-lg">
              <p className="text-2xl font-bold text-foreground">{funnel.funnel?.customers_converted || 0}</p>
              <p className="text-sm text-slate-muted">Converted</p>
              <p className="text-xs text-green-400 mt-1">{funnel.conversion_rates?.overall}% overall</p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Recent Contacts */}
      <div className="bg-slate-card rounded-xl border border-slate-border overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Recent Contacts</h3>
          <Link
            href="/crm/contacts/all"
            className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            View all
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-elevated">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Contact</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Type</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">MRR</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Created</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border/50">
              {contacts?.items?.slice(0, 5).map((contact: UnifiedContact) => (
                <tr
                  key={contact.id}
                  className="hover:bg-slate-elevated/30 transition-colors cursor-pointer"
                  onClick={() => router.push(`/crm/contacts/${contact.id}`)}
                >
                  <td className="px-4 py-4">
                    <div>
                      <p className="text-foreground font-medium">{contact.name}</p>
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
                    {contact.mrr ? (
                      <span className="text-foreground font-mono text-sm">
                        {formatCurrency(contact.mrr)}
                      </span>
                    ) : (
                      <span className="text-slate-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-muted">
                    {formatDate(contact.created_at)}
                  </td>
                  <td className="px-4 py-4">
                    <Link
                      href={`/crm/contacts/${contact.id}`}
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
      </div>
    </div>
  );
}
