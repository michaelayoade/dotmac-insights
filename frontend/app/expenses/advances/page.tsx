'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Plus, Wallet2 } from 'lucide-react';
import { useCashAdvances } from '@/hooks/useExpenses';
import { formatDate, cn } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { LoadingState, PageHeader, ErrorState, EmptyState, SearchInput, Button, StatGrid, StatusPill } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const STATUS_TONES: Record<string, StatusTone> = {
  draft: 'default',
  pending_approval: 'warning',
  approved: 'success',
  rejected: 'danger',
  disbursed: 'info',
  settled: 'success',
  partially_settled: 'info',
};

export default function CashAdvancesPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const [search, setSearch] = useState('');
  const canFetch = !authLoading && !missingScope;

  const { data, error, isLoading, mutate } = useCashAdvances({ limit: 50 }, { isPaused: () => !canFetch });

  const advances = data || [];
  const filteredAdvances = search
    ? advances.filter(
        (a) =>
          a.advance_number?.toLowerCase().includes(search.toLowerCase()) ||
          a.purpose?.toLowerCase().includes(search.toLowerCase())
      )
    : advances;

  // Stats
  const totalAdvances = advances.length;
  const pendingCount = advances.filter((a) => a.status === 'pending_approval').length;
  const outstandingAmount = advances.reduce((sum, a) => sum + (a.outstanding_amount || 0), 0);
  const disbursedAmount = advances.reduce((sum, a) => sum + (a.disbursed_amount || 0), 0);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view cash advances."
        backHref="/expenses"
        backLabel="Back to Expenses"
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cash Advances"
        subtitle="Request and track cash advance disbursements"
        icon={Wallet2}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
        actions={
          <Link href="/expenses/advances/new">
            <Button icon={Plus}>New Advance</Button>
          </Link>
        }
      />

      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search advances..."
        className="max-w-md"
      />

      <StatGrid columns={4}>
        <StatCard title="Total Advances" value={totalAdvances} loading={isLoading} icon={Wallet2} />
        <StatCard title="Pending Approval" value={pendingCount} loading={isLoading} variant="warning" />
        <StatCard title="Total Disbursed" value={`₦${disbursedAmount.toLocaleString()}`} loading={isLoading} variant="success" />
        <StatCard title="Outstanding" value={`₦${outstandingAmount.toLocaleString()}`} loading={isLoading} variant="danger" />
      </StatGrid>

      {error ? (
        <ErrorState message="Failed to load cash advances" onRetry={() => mutate()} />
      ) : isLoading ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-8">
          <div className="flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      ) : filteredAdvances.length === 0 ? (
        <EmptyState
          icon={Wallet2}
          title="No advances found"
          description={search ? 'Try a different search term' : 'Request your first cash advance'}
          action={!search ? { label: 'New Advance', icon: Plus, href: '/expenses/advances/new' } : undefined}
        />
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border">
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Advance</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Request Date</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Status</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-slate-muted">Requested</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-slate-muted hidden lg:table-cell">Disbursed</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-slate-muted hidden xl:table-cell">Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {filteredAdvances.map((advance) => (
                <tr key={advance.id} className="border-b border-slate-border/50 hover:bg-slate-elevated/30 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/expenses/advances/${advance.id}`} className="block">
                      <p className="text-foreground font-medium hover:text-teal-400 transition-colors">
                        {advance.advance_number || `Draft #${advance.id}`}
                      </p>
                      <p className="text-sm text-slate-muted">{advance.purpose}</p>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-muted text-sm hidden md:table-cell">
                    {formatDate(advance.request_date)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill
                      label={formatStatusLabel(advance.status)}
                      tone={STATUS_TONES[advance.status] || 'default'}
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-foreground font-medium">
                      {advance.requested_amount.toLocaleString()}
                    </span>
                    <span className="text-slate-muted text-sm ml-1">{advance.currency}</span>
                  </td>
                  <td className="px-4 py-3 text-right hidden lg:table-cell">
                    <span className="text-slate-200">
                      {advance.disbursed_amount.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right hidden xl:table-cell">
                    <span className={cn(
                      'font-medium',
                      advance.outstanding_amount > 0 ? 'text-amber-400' : 'text-emerald-400'
                    )}>
                      {advance.outstanding_amount.toLocaleString()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}