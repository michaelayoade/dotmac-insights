'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, BookOpen, FileText } from 'lucide-react';
import { useAccountingAccountDetail } from '@/hooks/useApi';
import { cn, formatCurrency } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useAccountingAccountDetail(
    Number.isFinite(id) ? id : null,
    { include_ledger: true, limit: 50 }
  );

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
        <p className="text-red-400">Failed to load account</p>
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

  const summary = [
    { label: 'Account', value: data.name || `Account #${data.id}` },
    { label: 'Type', value: data.account_type || data.root_type || '—' },
    { label: 'Currency', value: data.currency || 'NGN' },
    { label: 'Balance', value: formatCurrency((data as any).balance ?? data.debit ?? 0, data.currency || 'NGN') },
    { label: 'Debit', value: formatCurrency((data as any).debit ?? 0, data.currency || 'NGN') },
    { label: 'Credit', value: formatCurrency((data as any).credit ?? 0, data.currency || 'NGN') },
    { label: 'Parent', value: data.parent_account || '—' },
    { label: 'Company', value: (data as any).company || '—' },
  ];

  const ledger = (data as any).ledger || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/chart-of-accounts"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to chart
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Account</p>
            <h1 className="text-xl font-semibold text-white">{data.name || `Account #${data.id}`}</h1>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className={cn('text-white font-semibold break-all', row.label === 'Type' && 'capitalize')}>
              {row.value}
            </p>
          </div>
        ))}
      </div>

      {ledger.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Recent Ledger Entries</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Date</th>
                  <th className="text-left px-2 py-2">Voucher</th>
                  <th className="text-left px-2 py-2">Party</th>
                  <th className="text-right px-2 py-2">Debit</th>
                  <th className="text-right px-2 py-2">Credit</th>
                  <th className="text-left px-2 py-2">Cost Center</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-slate-200">{formatDate(entry.posting_date)}</td>
                    <td className="px-2 py-2 text-white font-mono flex items-center gap-2">
                      {entry.voucher_type && <FileText className="w-3 h-3 text-slate-muted" />}
                      <span>{entry.voucher_type || ''} {entry.voucher_no || ''}</span>
                    </td>
                    <td className="px-2 py-2 text-slate-200">{entry.party || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatCurrency(entry.debit, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatCurrency(entry.credit, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-slate-200">{entry.cost_center || '-'}</td>
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
