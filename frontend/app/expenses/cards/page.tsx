'use client';

import Link from 'next/link';
import { useState } from 'react';
import { CreditCard, Plus, Search, Filter, MoreVertical, Pause, Play, XCircle } from 'lucide-react';
import { useCorporateCards, useCorporateCardMutations } from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';
import type { CorporateCard, CorporateCardStatus } from '@/lib/expenses.types';

const STATUS_COLORS: Record<CorporateCardStatus, { bg: string; text: string; label: string }> = {
  active: { bg: 'bg-emerald-500/15', text: 'text-emerald-300', label: 'Active' },
  suspended: { bg: 'bg-amber-500/15', text: 'text-amber-300', label: 'Suspended' },
  cancelled: { bg: 'bg-red-500/15', text: 'text-red-300', label: 'Cancelled' },
};

function StatusBadge({ status }: { status: CorporateCardStatus }) {
  const style = STATUS_COLORS[status] || STATUS_COLORS.active;
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', style.bg, style.text)}>
      {style.label}
    </span>
  );
}

function CardRow({ card, onAction }: { card: CorporateCard; onAction: (action: string, card: CorporateCard) => void }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex items-center justify-between p-4 bg-slate-elevated rounded-xl border border-slate-border/60 hover:border-slate-border transition-colors">
      <Link href={`/expenses/cards/${card.id}`} className="flex items-center gap-4 flex-1">
        <div className="p-3 rounded-xl bg-violet-500/15 text-violet-300">
          <CreditCard className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-white font-semibold truncate">{card.card_name}</p>
            <StatusBadge status={card.status} />
          </div>
          <p className="text-slate-muted text-sm">
            ****{card.card_number_last4} &middot; {card.bank_name || card.card_provider || 'Card'}
          </p>
        </div>
      </Link>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-white font-semibold">{card.credit_limit.toLocaleString()} {card.currency}</p>
          <p className="text-slate-muted text-xs">Credit limit</p>
        </div>
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 bg-slate-card border border-slate-border rounded-lg shadow-xl py-1 min-w-[160px]">
                {card.status === 'active' && (
                  <button
                    onClick={() => { onAction('suspend', card); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
                  >
                    <Pause className="w-4 h-4" />
                    Suspend card
                  </button>
                )}
                {card.status === 'suspended' && (
                  <button
                    onClick={() => { onAction('activate', card); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
                  >
                    <Play className="w-4 h-4" />
                    Activate card
                  </button>
                )}
                {card.status !== 'cancelled' && (
                  <button
                    onClick={() => { onAction('cancel', card); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-slate-elevated transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                    Cancel card
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CorporateCardsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [includeInactive, setIncludeInactive] = useState(false);
  const { data: cards, isLoading } = useCorporateCards({ status: statusFilter || undefined, include_inactive: includeInactive });
  const { suspendCard, activateCard, cancelCard } = useCorporateCardMutations();

  const handleAction = async (action: string, card: CorporateCard) => {
    try {
      if (action === 'suspend') await suspendCard(card.id);
      else if (action === 'activate') await activateCard(card.id);
      else if (action === 'cancel') {
        if (confirm('Are you sure you want to cancel this card? This action cannot be undone.')) {
          await cancelCard(card.id);
        }
      }
    } catch (error) {
      console.error('Action failed:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Corporate Cards</h1>
            <p className="text-slate-muted text-sm mt-1">Manage company card assignments and limits</p>
          </div>
          <Link
            href="/expenses/cards/new"
            className="inline-flex items-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-white font-semibold shadow hover:bg-violet-400 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add card
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:outline-none focus:border-violet-500"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <label className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-sm text-slate-muted cursor-pointer hover:text-white transition-colors">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500"
          />
          Include inactive
        </label>
      </div>

      {/* Cards list */}
      <div className="space-y-3">
        {isLoading && (
          <div className="text-center py-8 text-slate-muted">Loading cards...</div>
        )}
        {!isLoading && (!cards || cards.length === 0) && (
          <div className="text-center py-12 bg-slate-card border border-slate-border rounded-2xl">
            <CreditCard className="w-12 h-12 mx-auto text-slate-muted mb-3" />
            <p className="text-white font-semibold">No corporate cards</p>
            <p className="text-slate-muted text-sm mt-1">Add a card to get started</p>
            <Link
              href="/expenses/cards/new"
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-violet-500 text-white font-semibold hover:bg-violet-400 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add card
            </Link>
          </div>
        )}
        {cards?.map((card) => (
          <CardRow key={card.id} card={card} onAction={handleAction} />
        ))}
      </div>
    </div>
  );
}
