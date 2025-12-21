'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, FileText, Calendar, Building2 } from 'lucide-react';
import { usePurchasingDebitNoteDetail, usePurchasingDebitNoteMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

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

export default function PurchasingDebitNoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = usePurchasingDebitNoteDetail(Number.isFinite(id) ? id : null);
  const { updateDebitNote } = usePurchasingDebitNoteMutations();
  const [statusInput, setStatusInput] = useState('draft');
  const [outstandingInput, setOutstandingInput] = useState('');
  const [paidInput, setPaidInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setStatusInput(data.status || 'draft');
      setOutstandingInput(
        (data as any).outstanding_amount !== undefined && (data as any).outstanding_amount !== null
          ? String((data as any).outstanding_amount)
          : ''
      );
      setPaidInput(
        (data as any).paid_amount !== undefined && (data as any).paid_amount !== null
          ? String((data as any).paid_amount)
          : ''
      );
    }
  }, [data]);

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
        <p className="text-red-400">Failed to load debit note</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const summaryRows = [
    { label: 'Supplier', value: data.supplier || '-' },
    { label: 'Posting Date', value: formatDate(data.posting_date) },
    { label: 'Due Date', value: formatDate((data as any).due_date) },
    { label: 'Status', value: data.status || 'draft' },
    { label: 'Total', value: formatCurrency(data.grand_total, (data as any).currency || 'NGN') },
    { label: 'Outstanding', value: formatCurrency((data as any).outstanding_amount, (data as any).currency || 'NGN') },
  ];

  const writeBackClass = cn(
    'px-2 py-1 rounded-full text-xs font-semibold border',
    (data as any).write_back_status === 'pending' && 'border-yellow-500/40 text-yellow-400 bg-yellow-500/10',
    (data as any).write_back_status === 'failed' && 'border-red-500/40 text-red-400 bg-red-500/10',
    (data as any).write_back_status === 'synced' && 'border-green-500/40 text-green-400 bg-green-500/10'
  );

  const handleQuickUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!data) return;
    setSaving(true);
    setActionError(null);
    try {
      await updateDebitNote(id, {
        status: statusInput || null,
        outstanding_amount: outstandingInput ? Number(outstandingInput) : undefined,
        paid_amount: paidInput ? Number(paidInput) : undefined,
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to update debit note');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/debit-notes"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to debit notes
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Debit Note</p>
            <h1 className="text-xl font-semibold text-foreground">{data.erpnext_id || `DN #${id}`}</h1>
            {(data as any).write_back_status && (
              <span className={writeBackClass}>Write-back: {(data as any).write_back_status}</span>
            )}
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summaryRows.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-foreground font-semibold">{row.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <h3 className="text-foreground font-semibold">Quick update</h3>
        {actionError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-2 text-sm">{actionError}</div>
        )}
        <form onSubmit={handleQuickUpdate} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Status</label>
            <select
              value={statusInput}
              onChange={(e) => setStatusInput(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="unpaid">Unpaid</option>
              <option value="paid">Paid</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Outstanding</label>
            <input
              type="number"
              value={outstandingInput}
              onChange={(e) => setOutstandingInput(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Paid</label>
            <input
              type="number"
              value={paidInput}
              onChange={(e) => setPaidInput(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="md:col-span-4 flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
            >
              {saving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>

      {(data as any).items?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Items</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Item</th>
                  <th className="text-left px-2 py-2">Description</th>
                  <th className="text-right px-2 py-2">Qty</th>
                  <th className="text-right px-2 py-2">Rate</th>
                  <th className="text-right px-2 py-2">Amount</th>
                </tr>
              </thead>
              <tbody>
                {(data as any).items.map((item: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-foreground font-mono">{item.item_code || '-'}</td>
                    <td className="px-2 py-2 text-slate-200">{item.item_name || item.description || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.qty ?? item.quantity ?? 0}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.rate ?? item.unit_price ?? 0}</td>
                    <td className="px-2 py-2 text-right text-foreground font-mono">{item.amount ?? item.net_amount ?? 0}</td>
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
