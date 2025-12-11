'use client';

import { useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, FileText, CreditCard } from 'lucide-react';
import { useFinanceInvoiceDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatCurrency(value: number | null | undefined, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    paid: 'bg-green-500/20 text-green-400 border-green-500/30',
    unpaid: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    partially_paid: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
    cancelled: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  };
  const color = colors[status?.toLowerCase()] || colors.unpaid;
  return <span className={cn('px-2 py-1 rounded-full text-xs font-medium border', color)}>{status || 'Unknown'}</span>;
}

export default function InvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = useMemo(() => Number(params?.id), [params?.id]);
  const currency = 'NGN';
  const { data, isLoading, error } = useFinanceInvoiceDetail(Number.isFinite(id) ? id : null, currency);

  if (isLoading) {
    return (
      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="h-6 w-24 bg-slate-elevated rounded mb-4 animate-pulse" />
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
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
        <p className="text-red-400">Failed to load invoice</p>
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

  const currentCurrency = data.currency || currency;
  const balance = (data.total_amount || 0) - (data.amount_paid || 0);

  return (
    <div className="space-y-6">
      <button
        onClick={() => router.back()}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>
      <Link
        href="/finance/invoices"
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
      >
        <FileText className="w-4 h-4" />
        Back to list
      </Link>
      <div className="flex items-center gap-2 text-sm text-slate-muted">
        <Link href="/finance" className="hover:text-white">Finance</Link>
        <span>/</span>
        <Link href="/finance/invoices" className="hover:text-white">Invoices</Link>
        <span>/</span>
        <span className="text-white">{data.invoice_number || `#${data.id}`}</span>
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-slate-muted text-sm">Invoice</p>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              {data.invoice_number || `#${data.id}`}
              <StatusBadge status={data.status} />
            </h2>
            <p className="text-slate-muted text-sm mt-1">Source: {data.source || '—'}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-muted">Total</p>
            <p className="text-3xl font-bold text-white">{formatCurrency(data.total_amount, currentCurrency)}</p>
            <p className="text-sm text-green-400">Paid: {formatCurrency(data.amount_paid, currentCurrency)}</p>
            <p className="text-sm text-amber-warn">Balance: {formatCurrency(balance, currentCurrency)}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-muted">
          <div>Invoice Date: <span className="text-white">{formatDate(data.invoice_date)}</span></div>
          <div>Due Date: <span className={cn(data.days_overdue > 0 ? 'text-red-400' : 'text-white')}>{formatDate(data.due_date)}</span></div>
          <div>Paid Date: <span className="text-white">{formatDate(data.paid_date)}</span></div>
          <div>Category: <span className="text-white">{data.category || '—'}</span></div>
        </div>

        <div className="mt-4 text-sm text-slate-muted">
          <p className="text-xs uppercase mb-1">Description</p>
          <p className="text-white">{data.description || 'No description'}</p>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-muted">
          <div>
            <p className="text-xs uppercase mb-1">Customer</p>
            <p className="text-white">
              {data.customer?.name || 'Unknown'} {data.customer?.email ? `• ${data.customer.email}` : ''}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase mb-1">External IDs</p>
            <p className="text-white">
              Splynx: {data.external_ids?.splynx_id ?? '—'} • ERPNext: {data.external_ids?.erpnext_id ?? '—'}
            </p>
          </div>
          <div className="md:col-span-2">
            <p className="text-xs uppercase mb-1">Payments</p>
            {data.payments && data.payments.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {data.payments.map((p) => (
                  <Link
                    key={p.id}
                    href={`/finance/payments/${p.id}`}
                    className="inline-flex items-center gap-2 text-teal-electric hover:text-teal-glow text-sm"
                  >
                    <CreditCard className="w-4 h-4" />
                    Payment #{p.id}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-slate-muted text-sm">No linked payments</p>
            )}
          </div>
          <div className="md:col-span-2">
            <p className="text-xs uppercase mb-1">Credit Notes</p>
            {data.credit_note_id || data.credit_note_number ? (
              <Link
                href={`/finance/credit-notes/${data.credit_note_id ?? ''}`}
                className="inline-flex items-center gap-2 text-teal-electric hover:text-teal-glow text-sm"
              >
                <FileText className="w-4 h-4" />
                {data.credit_note_number || `Credit Note #${data.credit_note_id}`}
              </Link>
            ) : (
              <p className="text-slate-muted text-sm">No linked credit notes</p>
            )}
          </div>
        </div>
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="flex items-center gap-2 mb-3">
          <CreditCard className="w-4 h-4 text-teal-electric" />
          <h3 className="text-lg font-semibold text-white">Payments</h3>
        </div>
        {data.payments && data.payments.length > 0 ? (
          <div className="space-y-2">
            {data.payments.map((pay) => (
              <div key={pay.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 text-sm">
                <div>
                  <p className="text-white font-mono">{formatCurrency(pay.amount, currentCurrency)}</p>
                  <p className="text-slate-muted text-xs">{formatDate(pay.payment_date)}</p>
                </div>
                <div className="text-right text-xs text-slate-muted">
                  <div>{pay.payment_method || '—'}</div>
                  <StatusBadge status={pay.status} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-muted text-sm">No payments recorded.</p>
        )}
      </div>
    </div>
  );
}
