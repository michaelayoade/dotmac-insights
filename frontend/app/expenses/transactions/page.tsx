'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Receipt, Filter, MoreVertical, Link2, Unlink, AlertTriangle, XCircle, User, Check } from 'lucide-react';
import { useCorporateCardTransactions, useTransactionMutations, useCorporateCards } from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';
import { useErrorHandler } from '@/hooks/useErrorHandler';
import type { CorporateCardTransaction, CardTransactionStatus } from '@/lib/expenses.types';

const STATUS_CONFIG: Record<CardTransactionStatus, { bg: string; text: string; label: string }> = {
  imported: { bg: 'bg-slate-500/15', text: 'text-foreground-secondary', label: 'Imported' },
  matched: { bg: 'bg-emerald-500/15', text: 'text-emerald-300', label: 'Matched' },
  unmatched: { bg: 'bg-amber-500/15', text: 'text-amber-300', label: 'Unmatched' },
  disputed: { bg: 'bg-red-500/15', text: 'text-red-300', label: 'Disputed' },
  excluded: { bg: 'bg-slate-500/15', text: 'text-slate-400', label: 'Excluded' },
  personal: { bg: 'bg-violet-500/15', text: 'text-violet-300', label: 'Personal' },
};

function TransactionRow({
  transaction,
  onAction,
}: {
  transaction: CorporateCardTransaction;
  onAction: (action: string, txn: CorporateCardTransaction) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const statusStyle = STATUS_CONFIG[transaction.status] || STATUS_CONFIG.imported;

  return (
    <div className="flex items-center justify-between p-4 bg-slate-elevated rounded-xl border border-slate-border/60 hover:border-slate-border transition-colors">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        <div className="p-3 rounded-xl bg-slate-border/30 text-slate-muted">
          <Receipt className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-foreground font-semibold truncate">{transaction.merchant_name || 'Unknown merchant'}</p>
            <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', statusStyle.bg, statusStyle.text)}>
              {statusStyle.label}
            </span>
          </div>
          <p className="text-slate-muted text-sm truncate">
            {transaction.transaction_date} &middot; {transaction.description || 'No description'}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-foreground font-semibold">{transaction.amount.toLocaleString()} {transaction.currency}</p>
          {transaction.original_currency && transaction.original_currency !== transaction.currency && (
            <p className="text-slate-muted text-xs">
              {transaction.original_amount?.toLocaleString()} {transaction.original_currency}
            </p>
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 bg-slate-card border border-slate-border rounded-lg shadow-xl py-1 min-w-[180px]">
                {transaction.status !== 'matched' && transaction.status !== 'excluded' && transaction.status !== 'personal' && (
                  <button
                    onClick={() => { onAction('match', transaction); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
                  >
                    <Link2 className="w-4 h-4" />
                    Match to expense
                  </button>
                )}
                {transaction.status === 'matched' && (
                  <button
                    onClick={() => { onAction('unmatch', transaction); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
                  >
                    <Unlink className="w-4 h-4" />
                    Unmatch
                  </button>
                )}
                {transaction.status !== 'disputed' && transaction.status !== 'excluded' && (
                  <button
                    onClick={() => { onAction('dispute', transaction); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-400 hover:text-amber-300 hover:bg-slate-elevated transition-colors"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    Dispute
                  </button>
                )}
                {transaction.status === 'disputed' && (
                  <button
                    onClick={() => { onAction('resolve', transaction); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-emerald-400 hover:text-emerald-300 hover:bg-slate-elevated transition-colors"
                  >
                    <Check className="w-4 h-4" />
                    Resolve dispute
                  </button>
                )}
                {transaction.status !== 'excluded' && transaction.status !== 'personal' && (
                  <>
                    <button
                      onClick={() => { onAction('exclude', transaction); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
                    >
                      <XCircle className="w-4 h-4" />
                      Exclude
                    </button>
                    <button
                      onClick={() => { onAction('personal', transaction); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-violet-400 hover:text-violet-300 hover:bg-slate-elevated transition-colors"
                    >
                      <User className="w-4 h-4" />
                      Mark personal
                    </button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TransactionsPage() {
  const searchParams = useSearchParams();
  const initialCardId = searchParams.get('card_id');
  const { handleError } = useErrorHandler();

  const [cardFilter, setCardFilter] = useState<string>(initialCardId || '');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [unmatchedOnly, setUnmatchedOnly] = useState(false);

  const { data: cards } = useCorporateCards({ include_inactive: true });
  const { data: transactions, isLoading } = useCorporateCardTransactions({
    card_id: cardFilter ? Number(cardFilter) : undefined,
    status: statusFilter || undefined,
    unmatched_only: unmatchedOnly,
    limit: 100,
  });
  const { matchTransaction, unmatchTransaction, disputeTransaction, excludeTransaction, markPersonal, resolveDispute } = useTransactionMutations();

  const handleAction = async (action: string, txn: CorporateCardTransaction) => {
    try {
      if (action === 'unmatch') {
        await unmatchTransaction(txn.id);
      } else if (action === 'dispute') {
        const reason = prompt('Enter dispute reason:');
        if (reason) await disputeTransaction(txn.id, reason);
      } else if (action === 'resolve') {
        const notes = prompt('Enter resolution notes:');
        if (notes) await resolveDispute(txn.id, notes, 'unmatched');
      } else if (action === 'exclude') {
        await excludeTransaction(txn.id);
      } else if (action === 'personal') {
        await markPersonal(txn.id);
      } else if (action === 'match') {
        const lineId = prompt('Enter expense claim line ID to match:');
        if (lineId) {
          await matchTransaction(txn.id, Number(lineId));
        }
      }
    } catch (error) {
      handleError(error, 'Action failed');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-foreground">Card Transactions</h1>
            <p className="text-slate-muted text-sm mt-1">View and manage corporate card transactions</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={cardFilter}
          onChange={(e) => setCardFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-foreground text-sm focus:outline-none focus:border-violet-500"
        >
          <option value="">All cards</option>
          {cards?.map((card) => (
            <option key={card.id} value={card.id}>
              {card.card_name} (****{card.card_number_last4})
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-foreground text-sm focus:outline-none focus:border-violet-500"
        >
          <option value="">All statuses</option>
          <option value="imported">Imported</option>
          <option value="matched">Matched</option>
          <option value="unmatched">Unmatched</option>
          <option value="disputed">Disputed</option>
          <option value="excluded">Excluded</option>
          <option value="personal">Personal</option>
        </select>
        <label className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-sm text-slate-muted cursor-pointer hover:text-foreground transition-colors">
          <input
            type="checkbox"
            checked={unmatchedOnly}
            onChange={(e) => setUnmatchedOnly(e.target.checked)}
            className="rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500"
          />
          Unmatched only
        </label>
      </div>

      {/* Transactions list */}
      <div className="space-y-3">
        {isLoading && (
          <div className="text-center py-8 text-slate-muted">Loading transactions...</div>
        )}
        {!isLoading && (!transactions || transactions.length === 0) && (
          <div className="text-center py-12 bg-slate-card border border-slate-border rounded-2xl">
            <Receipt className="w-12 h-12 mx-auto text-slate-muted mb-3" />
            <p className="text-foreground font-semibold">No transactions found</p>
            <p className="text-slate-muted text-sm mt-1">Import a statement or adjust filters</p>
          </div>
        )}
        {transactions?.map((txn) => (
          <TransactionRow key={txn.id} transaction={txn} onAction={handleAction} />
        ))}
      </div>
    </div>
  );
}
