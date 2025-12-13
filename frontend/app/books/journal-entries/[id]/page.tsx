'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, BookMarked, FileText } from 'lucide-react';
import { useAccountingJournalEntryDetail } from '@/hooks/useApi';

function formatCurrency(value: number | undefined | null, currency = 'NGN') {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function JournalEntryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useAccountingJournalEntryDetail(Number.isFinite(id) ? id : null);

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="h-6 w-28 bg-slate-elevated rounded mb-3 animate-pulse" />
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load journal entry</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const accounts = (data as any).accounts || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/journal-entries"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to journal entries
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Journal Entry</p>
            <h1 className="text-xl font-semibold text-white">{(data as any).erpnext_id || data.voucher_no || `JE #${id}`}</h1>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <p className="text-xs uppercase text-slate-muted tracking-[0.1em]">Posting Date</p>
          <p className="text-white font-semibold">{formatDate(data.posting_date)}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-muted tracking-[0.1em]">Total Debit / Credit</p>
          <p className="text-white font-semibold">
            {formatCurrency(data.total_debit)} / {formatCurrency(data.total_credit)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-muted tracking-[0.1em]">Status</p>
          <p className="text-white font-semibold">{(data as any).is_balanced ? 'Balanced' : 'Unbalanced'}</p>
        </div>
      </div>

      {accounts.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Accounts</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Account</th>
                  <th className="text-left px-2 py-2">Party</th>
                  <th className="text-right px-2 py-2">Debit</th>
                  <th className="text-right px-2 py-2">Credit</th>
                  <th className="text-left px-2 py-2">Cost Center</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acc: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-white font-mono">{acc.account}</td>
                    <td className="px-2 py-2 text-slate-200">{acc.party || acc.party_type || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatCurrency(acc.debit)}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatCurrency(acc.credit)}</td>
                    <td className="px-2 py-2 text-slate-200">{acc.cost_center || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
