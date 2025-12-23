'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CreditCard, Calendar, Building2, User, Wallet, Pause, Play, XCircle, Edit2, Receipt } from 'lucide-react';
import { useCorporateCardDetail, useCorporateCardMutations, useCorporateCardTransactions } from '@/hooks/useExpenses';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import type { CorporateCardStatus, CardTransactionStatus } from '@/lib/expenses.types';
import { LoadingState, Button, StatusPill } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const STATUS_TONES: Record<CorporateCardStatus, StatusTone> = {
  active: 'success',
  suspended: 'warning',
  cancelled: 'danger',
};

const TXN_STATUS_TONES: Record<CardTransactionStatus, StatusTone> = {
  imported: 'default',
  matched: 'success',
  unmatched: 'warning',
  disputed: 'danger',
  excluded: 'default',
  personal: 'info',
};

function InfoItem({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-lg bg-slate-elevated text-slate-muted">
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-slate-muted text-xs">{label}</p>
        <p className="text-foreground font-medium">{value || '-'}</p>
      </div>
    </div>
  );
}

export default function CardDetailPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const params = useParams();
  const router = useRouter();
  const cardId = params.id ? Number(params.id) : undefined;

  const canFetch = !authLoading && !missingScope;
  const { data: card, isLoading } = useCorporateCardDetail(cardId, { isPaused: () => !canFetch });
  const { data: transactions } = useCorporateCardTransactions({ card_id: cardId, limit: 10 }, { isPaused: () => !canFetch });
  const { suspendCard, activateCard, cancelCard } = useCorporateCardMutations();

  const handleSuspend = async () => {
    if (!cardId) return;
    await suspendCard(cardId);
  };

  const handleActivate = async () => {
    if (!cardId) return;
    await activateCard(cardId);
  };

  const handleCancel = async () => {
    if (!cardId) return;
    if (confirm('Are you sure you want to cancel this card? This action cannot be undone.')) {
      await cancelCard(cardId);
    }
  };

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view corporate cards."
        backHref="/expenses/cards"
        backLabel="Back to Cards"
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-slate-muted">Loading card details...</div>
      </div>
    );
  }

  if (!card) {
    return (
      <div className="space-y-4">
        <Link href="/expenses/cards" className="inline-flex items-center gap-2 text-slate-muted hover:text-foreground transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Back to cards
        </Link>
        <div className="text-center py-12 bg-slate-card border border-slate-border rounded-2xl">
          <p className="text-foreground font-semibold">Card not found</p>
        </div>
      </div>
    );
  }

  const statusTone = STATUS_TONES[card.status] || STATUS_TONES.active;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/expenses/cards" className="inline-flex items-center gap-2 text-slate-muted hover:text-foreground transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to cards
      </Link>

      {/* Card header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <div className="p-4 rounded-2xl bg-violet-500/15 text-violet-300">
              <CreditCard className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-foreground">{card.card_name}</h1>
                <StatusPill
                  label={formatStatusLabel(card.status)}
                  tone={statusTone}
                  size="md"
                />
              </div>
              <p className="text-slate-muted mt-1">
                ****{card.card_number_last4} &middot; {card.bank_name || card.card_provider || 'Corporate Card'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {card.status === 'active' && (
              <Button
                onClick={handleSuspend}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 transition-colors"
              >
                <Pause className="w-4 h-4" />
                Suspend
              </Button>
            )}
            {card.status === 'suspended' && (
              <Button
                onClick={handleActivate}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors"
              >
                <Play className="w-4 h-4" />
                Activate
              </Button>
            )}
            {card.status !== 'cancelled' && (
              <Button
                onClick={handleCancel}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Cancel
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Card details grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Limits */}
        <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">Limits</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoItem icon={Wallet} label="Credit Limit" value={`${card.credit_limit.toLocaleString()} ${card.currency}`} />
            <InfoItem icon={Wallet} label="Single Transaction" value={card.single_transaction_limit ? `${card.single_transaction_limit.toLocaleString()} ${card.currency}` : 'No limit'} />
            <InfoItem icon={Wallet} label="Daily Limit" value={card.daily_limit ? `${card.daily_limit.toLocaleString()} ${card.currency}` : 'No limit'} />
            <InfoItem icon={Wallet} label="Monthly Limit" value={card.monthly_limit ? `${card.monthly_limit.toLocaleString()} ${card.currency}` : 'No limit'} />
          </div>
        </div>

        {/* Details */}
        <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">Details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoItem icon={CreditCard} label="Card Type" value={card.card_type} />
            <InfoItem icon={Building2} label="Bank / Provider" value={card.bank_name || card.card_provider} />
            <InfoItem icon={Calendar} label="Issue Date" value={card.issue_date} />
            <InfoItem icon={Calendar} label="Expiry Date" value={card.expiry_date} />
            <InfoItem icon={User} label="Employee ID" value={card.employee_id} />
            <InfoItem icon={Building2} label="Liability Account" value={card.liability_account} />
          </div>
        </div>
      </div>

      {/* Recent transactions */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Recent Transactions</h2>
          <Link
            href={`/expenses/transactions?card_id=${cardId}`}
            className="text-violet-300 text-sm hover:text-violet-200 transition-colors"
          >
            View all
          </Link>
        </div>
        {(!transactions || transactions.length === 0) ? (
          <div className="text-center py-8">
            <Receipt className="w-10 h-10 mx-auto text-slate-muted mb-2" />
            <p className="text-slate-muted">No transactions yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {transactions.map((txn) => {
              const statusTone = TXN_STATUS_TONES[txn.status] || TXN_STATUS_TONES.imported;
              return (
                <div
                  key={txn.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-elevated border border-slate-border/60"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-slate-border/30 text-slate-muted">
                      <Receipt className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-foreground text-sm font-medium">{txn.merchant_name || 'Unknown merchant'}</p>
                      <p className="text-slate-muted text-xs">{txn.transaction_date}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-foreground font-semibold">{txn.amount.toLocaleString()} {txn.currency}</p>
                    <StatusPill
                      label={formatStatusLabel(txn.status)}
                      tone={statusTone}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}