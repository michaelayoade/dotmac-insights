'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import { ArrowRight, ClipboardList, Wallet2, CheckCircle2, AlertCircle, Sparkles, FilePlus, PlusCircle } from 'lucide-react';
import { useExpenseClaims, useCashAdvances } from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function ActionTile({
  href,
  title,
  desc,
  icon: Icon,
  accent,
}: {
  href: string;
  title: string;
  desc: string;
  icon: React.ElementType;
  accent: 'blue' | 'green';
}) {
  return (
    <Link
      href={href}
      className="group relative rounded-2xl border border-slate-border bg-slate-card p-4 overflow-hidden hover:border-slate-400 transition-colors"
    >
      <div
        className={cn(
          'absolute inset-x-0 top-0 h-1.5',
          accent === 'blue' ? 'bg-sky-400/60' : 'bg-emerald-400/60'
        )}
      />
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'p-3 rounded-xl',
            accent === 'blue' ? 'bg-sky-500/15 text-sky-300' : 'bg-emerald-500/15 text-emerald-300'
          )}
        >
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <p className="text-foreground font-semibold">{title}</p>
          <p className="text-slate-muted text-sm">{desc}</p>
        </div>
        <ArrowRight className="w-4 h-4 text-slate-muted group-hover:text-foreground transition" />
      </div>
    </Link>
  );
}

export default function ExpensesDashboard() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const canFetch = !authLoading && !missingScope;

  const { data: claims, error: claimsError, isLoading: claimsLoading, mutate: refetchClaims } = useExpenseClaims({ limit: 50 }, { isPaused: () => !canFetch });
  const { data: advances, error: advancesError, isLoading: advancesLoading, mutate: refetchAdvances } = useCashAdvances({ limit: 50 }, { isPaused: () => !canFetch });
  const isLoading = claimsLoading || advancesLoading;
  const firstError = (claimsError || advancesError) as Error | undefined;
  const retryAll = () => {
    void refetchClaims();
    void refetchAdvances();
  };

  const metrics = useMemo(() => {
    const allClaims = claims || [];
    const openClaims = allClaims.filter((c) => ['draft', 'pending_approval', 'returned', 'recalled'].includes(c.status));
    const approvedClaims = allClaims.filter((c) => c.status === 'approved');
    const totalClaimed = allClaims.reduce((sum, c) => sum + (c.total_claimed_amount || 0), 0);

    const allAdvances = advances || [];
    const outstandingAdvances = allAdvances.reduce((sum, a) => sum + (a.outstanding_amount || 0), 0);
    const pendingAdvances = allAdvances.filter((a) => ['pending_approval', 'approved', 'disbursed'].includes(a.status));

    return {
      openClaims: openClaims.length,
      approvedClaims: approvedClaims.length,
      totalClaimed,
      outstandingAdvances,
      pendingAdvances: pendingAdvances.length,
    };
  }, [claims, advances]);

  const recentClaims = (claims || []).slice(0, 4);
  const recentAdvances = (advances || []).slice(0, 4);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view expenses."
        backHref="/"
        backLabel="Back to Home"
      />
    );
  }

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {firstError && (
        <ErrorDisplay
          message="Failed to load expenses data."
          error={firstError}
          onRetry={retryAll}
        />
      )}
      <div className="rounded-3xl border border-slate-border bg-slate-card p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-sky-500/5 via-emerald-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-sky-500/10 px-3 py-1 text-sky-200 text-xs font-semibold">
              <Sparkles className="w-4 h-4" />
              Expenses Workspace
            </div>
            <h1 className="text-2xl font-bold text-foreground mt-3">Control spend without losing the audit trail</h1>
            <p className="text-slate-muted text-sm mt-2 max-w-2xl">
              Track employee claims and cash advances in one place. Submit, approve, and reconcile with clear statuses.
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/expenses/claims/new"
              className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-slate-950 font-semibold shadow hover:bg-sky-400"
            >
              <FilePlus className="w-4 h-4" />
              New claim
            </Link>
            <Link
              href="/expenses/advances/new"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-border px-4 py-2 text-foreground hover:border-sky-400"
            >
              <PlusCircle className="w-4 h-4" />
              Cash advance
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <StatCard title="Open claims" value={metrics.openClaims} subtitle="Awaiting submission/approval" />
        <StatCard title="Approved claims" value={metrics.approvedClaims} subtitle="Ready for posting" variant="success" />
        <StatCard title="Total claimed" value={metrics.totalClaimed.toLocaleString()} subtitle="All time" />
        <StatCard title="Outstanding advances" value={metrics.outstandingAdvances.toLocaleString()} variant="warning" subtitle="Needs settlement" />
        <StatCard title="Pending advances" value={metrics.pendingAdvances} subtitle="Awaiting disbursement/settlement" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ActionTile
          href="/expenses/claims"
          title="Manage claims"
          desc="Review submissions, approvals, and postings."
          icon={ClipboardList}
          accent="blue"
        />
        <ActionTile
          href="/expenses/advances"
          title="Manage advances"
          desc="Track disbursements and outstanding balances."
          icon={Wallet2}
          accent="green"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-border bg-slate-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-foreground font-semibold">Recent claims</p>
              <p className="text-slate-muted text-sm">Last 4 submissions</p>
            </div>
            <Link href="/expenses/claims" className="text-sky-300 text-sm inline-flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-2">
            {recentClaims.length === 0 && <p className="text-slate-muted text-sm">No claims yet.</p>}
            {recentClaims.map((claim) => (
              <div
                key={claim.id}
                className="flex items-center justify-between rounded-xl border border-slate-border/60 bg-slate-elevated p-3"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-sky-500/10 text-sky-300">
                    <ClipboardList className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-foreground text-sm font-semibold">
                      {claim.claim_number || `Claim #${claim.id}`}
                    </p>
                    <p className="text-slate-muted text-xs">{claim.title}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-foreground text-sm font-semibold">{claim.total_claimed_amount.toLocaleString()}</p>
                  <p className="text-slate-muted text-xs uppercase">{claim.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-border bg-slate-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-foreground font-semibold">Recent advances</p>
              <p className="text-slate-muted text-sm">Last 4 requests</p>
            </div>
            <Link href="/expenses/advances" className="text-emerald-300 text-sm inline-flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-2">
            {recentAdvances.length === 0 && <p className="text-slate-muted text-sm">No advances yet.</p>}
            {recentAdvances.map((advance) => (
              <div
                key={advance.id}
                className="flex items-center justify-between rounded-xl border border-slate-border/60 bg-slate-elevated p-3"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-300">
                    <Wallet2 className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-foreground text-sm font-semibold">
                      {advance.advance_number || `Advance #${advance.id}`}
                    </p>
                    <p className="text-slate-muted text-xs">{advance.purpose}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-foreground text-sm font-semibold">{advance.requested_amount.toLocaleString()}</p>
                  <p className="text-slate-muted text-xs uppercase">{advance.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
