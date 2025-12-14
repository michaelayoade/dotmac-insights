'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Landmark, FileText } from 'lucide-react';
import { useAccountingBankTransactionDetail } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';
import { ReconciliationPanel } from '@/components/bank/ReconciliationPanel';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function BankTransactionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const lookup = Number.isFinite(id) ? id : (params?.id as string);
  const { data, isLoading, error } = useAccountingBankTransactionDetail(lookup || null);

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
        <p className="text-red-400">Failed to load bank transaction</p>
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

  const currency = data.currency || 'NGN';

  const summary = [
    { label: 'Transaction', value: data.erpnext_id || `#${data.id}` },
    { label: 'Date', value: formatDate(data.transaction_date) },
    { label: 'Account', value: data.account },
    { label: 'Company', value: data.company || '—' },
    { label: 'Type', value: data.transaction_type || '—' },
    { label: 'Status', value: data.status },
    { label: 'Reference', value: data.reference_number || data.reference || '—' },
    { label: 'Transaction ID', value: data.transaction_id || '—' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/bank-transactions"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to bank transactions
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Bank Transaction</p>
            <h1 className="text-xl font-semibold text-white">{data.erpnext_id || `#${data.id}`}</h1>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-white font-semibold break-all">{row.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Deposit</p>
          <p className="text-white font-semibold">{formatCurrency(data.deposit ?? 0, currency)}</p>
        </div>
        <div>
          <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Withdrawal</p>
          <p className="text-white font-semibold">{formatCurrency(data.withdrawal ?? 0, currency)}</p>
        </div>
        <div>
          <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Allocated</p>
          <p className="text-white font-semibold">
            {formatCurrency(data.allocated_amount ?? 0, currency)} / {formatCurrency(data.amount ?? data.deposit ?? 0, currency)}
          </p>
          <p className="text-xs text-slate-muted">Unallocated: {formatCurrency(data.unallocated_amount ?? 0, currency)}</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
        <div className="flex items-center gap-2">
          <Landmark className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Party</h3>
        </div>
        <p className="text-slate-200 text-sm">
          {data.party_type || '—'} {data.party || ''}
        </p>
        <p className="text-slate-muted text-sm">
          {data.bank_party_name || 'Bank party: —'}
          {data.bank_party_account_number ? ` (${data.bank_party_account_number})` : ''}
        </p>
        <p className="text-slate-muted text-sm">{data.description || 'No description provided'}</p>
      </div>

      {data.payments?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Allocations</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Document</th>
                  <th className="text-left px-2 py-2">Entry</th>
                  <th className="text-right px-2 py-2">Allocated</th>
                </tr>
              </thead>
              <tbody>
                {data.payments.map((pay, idx) => (
                  <tr key={pay.id || pay.erpnext_id || idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-slate-200">{pay.payment_document || '-'}</td>
                    <td className="px-2 py-2 text-white font-mono">{pay.payment_entry || '-'}</td>
                    <td className="px-2 py-2 text-right text-white font-mono">
                      {formatCurrency(pay.allocated_amount ?? 0, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Reconciliation Panel */}
      <ReconciliationPanel
        transactionId={data.id}
        transactionAmount={data.amount ?? data.deposit ?? data.withdrawal ?? 0}
        currentAllocated={data.allocated_amount ?? 0}
        currency={currency}
      />
    </div>
  );
}
