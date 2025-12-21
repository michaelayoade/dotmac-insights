'use client';

import { useState, useMemo } from 'react';
import {
  Building2,
  Users,
  Search,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ArrowUpDown,
  ChevronLeft,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useInboxCompanies } from '@/hooks/useInbox';
import { PageHeader, SearchInput } from '@/components/ui';

type SortField = 'company' | 'contact_count';
type SortOrder = 'asc' | 'desc';

function MetricCard({
  label,
  value,
  icon: Icon,
  colorClass = 'text-blue-400',
  isLoading = false,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
  isLoading?: boolean;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          {isLoading ? (
            <div className="h-9 w-20 bg-slate-elevated rounded mt-1 animate-pulse" />
          ) : (
            <p className={cn('text-3xl font-bold mt-1', colorClass)}>{value}</p>
          )}
        </div>
        <div className={cn('p-3 rounded-xl bg-slate-elevated')}>
          <Icon className={cn('w-6 h-6', colorClass)} />
        </div>
      </div>
    </div>
  );
}

export default function InboxCompaniesPage() {
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('contact_count');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useInboxCompanies({ search: search || undefined });

  const companies = useMemo(() => data?.data ?? [], [data?.data]);
  const total = data?.total || 0;

  // Compute summary stats
  const totalCompanies = companies.length;
  const totalContacts = companies.reduce((sum, c) => sum + (c.contact_count || 0), 0);

  // Filter and sort
  const sortedCompanies = useMemo(() => {
    return [...companies].sort((a, b) => {
      let aVal: string | number = a[sortField] ?? '';
      let bVal: string | number = b[sortField] ?? '';

      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [companies, sortField, sortOrder]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <th
      className="text-left py-3 px-4 text-sm font-medium text-slate-muted cursor-pointer hover:text-foreground transition-colors"
      onClick={() => toggleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        <ArrowUpDown className={cn('w-3.5 h-3.5', sortField === field ? 'text-blue-400' : 'opacity-50')} />
      </div>
    </th>
  );

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load companies</p>
        <button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/inbox/contacts"
        className="inline-flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to Contacts
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Company Contacts"
          subtitle="Organization directory grouped by company"
          icon={Building2}
        />
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricCard
          label="Total Companies"
          value={total || totalCompanies}
          icon={Building2}
          colorClass="text-blue-400"
          isLoading={isLoading}
        />
        <MetricCard
          label="Total Contacts"
          value={totalContacts.toLocaleString()}
          icon={Users}
          colorClass="text-emerald-400"
          isLoading={isLoading}
        />
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
          <input
            type="text"
            placeholder="Search companies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
          />
        </div>
      </div>

      {/* Companies Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-border">
          <h2 className="text-lg font-semibold">Companies</h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
          </div>
        ) : companies.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-muted">
            <Building2 className="w-12 h-12 mb-4 opacity-50" />
            <p>{search ? 'No companies match your search' : 'No companies found'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-elevated border-b border-slate-border">
                <tr>
                  <SortHeader field="company">Company</SortHeader>
                  <SortHeader field="contact_count">Contacts</SortHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {sortedCompanies.map((company, index) => (
                  <tr key={company.company || index} className="hover:bg-slate-elevated/50 transition-colors">
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                          <Building2 className="w-4 h-4" />
                        </div>
                        <span className="font-medium">{company.company || 'Unknown'}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-slate-muted" />
                        <span className="text-emerald-400 font-medium">
                          {company.contact_count?.toLocaleString() || 0}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
