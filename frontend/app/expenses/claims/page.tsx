'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Plus, ClipboardList, Search } from 'lucide-react';
import { useExpenseClaims } from '@/hooks/useExpenses';
import { formatDate, cn } from '@/lib/utils';
import { PageHeader, ErrorState, EmptyState, SearchInput, Button, StatGrid } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-elevated text-slate-muted',
  pending_approval: 'bg-amber-500/20 text-amber-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  rejected: 'bg-rose-500/20 text-rose-400',
  returned: 'bg-orange-500/20 text-orange-400',
  recalled: 'bg-violet-500/20 text-violet-400',
  posted: 'bg-blue-500/20 text-blue-400',
};

export default function ExpenseClaimsPage() {
  const [search, setSearch] = useState('');
  const { data, error, isLoading, mutate } = useExpenseClaims({ limit: 50 });

  const claims = data || [];
  const filteredClaims = search
    ? claims.filter(
        (c) =>
          c.claim_number?.toLowerCase().includes(search.toLowerCase()) ||
          c.title?.toLowerCase().includes(search.toLowerCase())
      )
    : claims;

  // Stats
  const totalClaims = claims.length;
  const pendingCount = claims.filter((c) => c.status === 'pending_approval').length;
  const approvedCount = claims.filter((c) => c.status === 'approved').length;
  const totalAmount = claims.reduce((sum, c) => sum + (c.total_claimed_amount || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Expense Claims"
        subtitle="Submit, track and manage expense reimbursements"
        icon={ClipboardList}
        iconClassName="bg-sky-500/10 border border-sky-500/30"
        actions={
          <Link href="/expenses/claims/new">
            <Button icon={Plus}>New Claim</Button>
          </Link>
        }
      />

      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search claims..."
        className="max-w-md"
      />

      <StatGrid columns={4}>
        <StatCard title="Total Claims" value={totalClaims} loading={isLoading} icon={ClipboardList} />
        <StatCard title="Pending Approval" value={pendingCount} loading={isLoading} variant="warning" />
        <StatCard title="Approved" value={approvedCount} loading={isLoading} variant="success" />
        <StatCard title="Total Claimed" value={`₦${totalAmount.toLocaleString()}`} loading={isLoading} />
      </StatGrid>

      {error ? (
        <ErrorState message="Failed to load claims" onRetry={() => mutate()} />
      ) : isLoading ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-8">
          <div className="flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      ) : filteredClaims.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No claims found"
          description={search ? 'Try a different search term' : 'Create your first expense claim'}
          action={!search ? { label: 'New Claim', icon: Plus, href: '/expenses/claims/new' } : undefined}
        />
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border">
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Claim</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Date</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Status</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-slate-muted">Amount</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden lg:table-cell">Currency</th>
              </tr>
            </thead>
            <tbody>
              {filteredClaims.map((claim) => (
                <tr key={claim.id} className="border-b border-slate-border/50 hover:bg-slate-elevated/30 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/expenses/claims/${claim.id}`} className="block">
                      <p className="text-white font-medium hover:text-teal-400 transition-colors">
                        {claim.claim_number || `Draft #${claim.id}`}
                      </p>
                      <p className="text-sm text-slate-muted">{claim.title}</p>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-muted text-sm hidden md:table-cell">
                    {formatDate(claim.claim_date)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        'inline-flex px-2 py-1 rounded-full text-xs font-medium',
                        STATUS_COLORS[claim.status] || 'bg-slate-elevated text-slate-muted'
                      )}
                    >
                      {claim.status.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-white font-medium">
                      {claim.total_claimed_amount.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-muted text-sm hidden lg:table-cell">
                    {claim.currency}
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
