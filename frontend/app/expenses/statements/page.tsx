'use client';

import { useState } from 'react';
import Link from 'next/link';
import { FileSpreadsheet, Plus, MoreVertical, CheckCircle, Lock, Unlock, Trash2, Eye } from 'lucide-react';
import { useCorporateCardStatements, useStatementMutations, useCorporateCards } from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';
import type { CorporateCardStatement, StatementStatus } from '@/lib/expenses.types';

const STATUS_CONFIG: Record<StatementStatus, { bg: string; text: string; label: string }> = {
  open: { bg: 'bg-sky-500/15', text: 'text-sky-300', label: 'Open' },
  reconciled: { bg: 'bg-emerald-500/15', text: 'text-emerald-300', label: 'Reconciled' },
  closed: { bg: 'bg-slate-500/15', text: 'text-slate-400', label: 'Closed' },
};

function StatementRow({
  statement,
  cardName,
  onAction,
}: {
  statement: CorporateCardStatement;
  cardName?: string;
  onAction: (action: string, stmt: CorporateCardStatement) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const statusStyle = STATUS_CONFIG[statement.status] || STATUS_CONFIG.open;
  const matchRate = statement.transaction_count > 0
    ? Math.round((statement.matched_count / statement.transaction_count) * 100)
    : 0;

  return (
    <div className="flex items-center justify-between p-4 bg-slate-elevated rounded-xl border border-slate-border/60 hover:border-slate-border transition-colors">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        <div className="p-3 rounded-xl bg-sky-500/15 text-sky-300">
          <FileSpreadsheet className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-white font-semibold">
              {statement.period_start} to {statement.period_end}
            </p>
            <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', statusStyle.bg, statusStyle.text)}>
              {statusStyle.label}
            </span>
          </div>
          <p className="text-slate-muted text-sm truncate">
            {cardName || `Card #${statement.card_id}`} &middot; {statement.transaction_count} transactions
          </p>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="text-right hidden sm:block">
          <p className="text-white font-semibold">{statement.total_amount.toLocaleString()}</p>
          <p className="text-slate-muted text-xs">Total amount</p>
        </div>
        <div className="text-right hidden md:block">
          <p className={cn('font-semibold', matchRate >= 80 ? 'text-emerald-300' : matchRate >= 50 ? 'text-amber-300' : 'text-red-300')}>
            {matchRate}%
          </p>
          <p className="text-slate-muted text-xs">Matched</p>
        </div>
        <div className="text-right hidden lg:block">
          <p className="text-slate-muted text-sm">{statement.unmatched_count}</p>
          <p className="text-slate-muted text-xs">Unmatched</p>
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
              <div className="absolute right-0 top-full mt-1 z-20 bg-slate-card border border-slate-border rounded-lg shadow-xl py-1 min-w-[180px]">
                <Link
                  href={`/expenses/transactions?statement_id=${statement.id}`}
                  onClick={() => setMenuOpen(false)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
                >
                  <Eye className="w-4 h-4" />
                  View transactions
                </Link>
                {statement.status === 'open' && (
                  <button
                    onClick={() => { onAction('reconcile', statement); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-emerald-400 hover:text-emerald-300 hover:bg-slate-elevated transition-colors"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Mark reconciled
                  </button>
                )}
                {statement.status === 'reconciled' && (
                  <>
                    <button
                      onClick={() => { onAction('close', statement); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
                    >
                      <Lock className="w-4 h-4" />
                      Close statement
                    </button>
                    <button
                      onClick={() => { onAction('reopen', statement); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-400 hover:text-amber-300 hover:bg-slate-elevated transition-colors"
                    >
                      <Unlock className="w-4 h-4" />
                      Reopen
                    </button>
                  </>
                )}
                {statement.status === 'open' && (
                  <button
                    onClick={() => { onAction('delete', statement); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-slate-elevated transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
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

export default function StatementsPage() {
  const [cardFilter, setCardFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const { data: cards } = useCorporateCards({ include_inactive: true });
  const { data: statements, isLoading } = useCorporateCardStatements({
    card_id: cardFilter ? Number(cardFilter) : undefined,
    status: statusFilter || undefined,
    limit: 50,
  });
  const { reconcileStatement, closeStatement, reopenStatement, deleteStatement } = useStatementMutations();

  const cardMap = new Map(cards?.map((c) => [c.id, `${c.card_name} (****${c.card_number_last4})`]));

  const handleAction = async (action: string, stmt: CorporateCardStatement) => {
    try {
      if (action === 'reconcile') {
        await reconcileStatement(stmt.id);
      } else if (action === 'close') {
        await closeStatement(stmt.id);
      } else if (action === 'reopen') {
        await reopenStatement(stmt.id);
      } else if (action === 'delete') {
        if (confirm('Are you sure you want to delete this statement and all its transactions?')) {
          await deleteStatement(stmt.id);
        }
      }
    } catch (error) {
      console.error('Action failed:', error);
      alert('Action failed. Please try again.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Card Statements</h1>
            <p className="text-slate-muted text-sm mt-1">Import and reconcile corporate card statements</p>
          </div>
          <Link
            href="/expenses/statements/import"
            className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-white font-semibold shadow hover:bg-sky-400 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Import Statement
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={cardFilter}
          onChange={(e) => setCardFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:outline-none focus:border-sky-500"
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
          className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:outline-none focus:border-sky-500"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="reconciled">Reconciled</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* Stats summary */}
      {statements && statements.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-border bg-slate-card p-4">
            <p className="text-slate-muted text-sm">Open statements</p>
            <p className="text-2xl font-bold text-white mt-1">
              {statements.filter((s) => s.status === 'open').length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-border bg-slate-card p-4">
            <p className="text-slate-muted text-sm">Total unmatched</p>
            <p className="text-2xl font-bold text-amber-300 mt-1">
              {statements.reduce((sum, s) => sum + s.unmatched_count, 0)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-border bg-slate-card p-4">
            <p className="text-slate-muted text-sm">Total transactions</p>
            <p className="text-2xl font-bold text-white mt-1">
              {statements.reduce((sum, s) => sum + s.transaction_count, 0)}
            </p>
          </div>
        </div>
      )}

      {/* Statements list */}
      <div className="space-y-3">
        {isLoading && (
          <div className="text-center py-8 text-slate-muted">Loading statements...</div>
        )}
        {!isLoading && (!statements || statements.length === 0) && (
          <div className="text-center py-12 bg-slate-card border border-slate-border rounded-2xl">
            <FileSpreadsheet className="w-12 h-12 mx-auto text-slate-muted mb-3" />
            <p className="text-white font-semibold">No statements found</p>
            <p className="text-slate-muted text-sm mt-1">Import a statement to get started</p>
            <button
              onClick={() => alert('Statement import wizard coming soon')}
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-sky-500 text-white font-semibold hover:bg-sky-400 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Import statement
            </button>
          </div>
        )}
        {statements?.map((stmt) => (
          <StatementRow
            key={stmt.id}
            statement={stmt}
            cardName={cardMap.get(stmt.card_id)}
            onAction={handleAction}
          />
        ))}
      </div>
    </div>
  );
}
