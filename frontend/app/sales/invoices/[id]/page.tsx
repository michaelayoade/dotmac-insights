'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, FileText, CreditCard, Receipt } from 'lucide-react';
import { useFinanceInvoiceDetail } from '@/hooks/useApi';
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

export default function SalesInvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useFinanceInvoiceDetail(Number.isFinite(id) ? id : null, 'NGN');

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

  const summary = [
    { label: 'Invoice #', value: data.invoice_number || `INV-${data.id}` },
    { label: 'Customer', value: data.customer_name || data.customer?.name || '-' },
    { label: 'Amount', value: formatCurrency(data.total_amount ?? data.amount, data.currency || 'NGN') },
    { label: 'Tax', value: formatCurrency(data.tax_amount ?? 0, data.currency || 'NGN') },
    { label: 'Paid', value: formatCurrency(data.amount_paid || 0, data.currency || 'NGN') },
    { label: 'Balance', value: formatCurrency(data.balance || 0, data.currency || 'NGN') },
    { label: 'Status', value: data.status },
    { label: 'Invoice Date', value: formatDate(data.invoice_date) },
    { label: 'Due Date', value: formatDate(data.due_date) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/invoices"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to invoices
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Invoice</p>
            <h1 className="text-xl font-semibold text-white">{data.invoice_number || `Invoice #${data.id}`}</h1>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href="/sales/payments/new"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
          >
            <CreditCard className="w-4 h-4" />
            Record Payment
          </Link>
          <Link
            href="/sales/credit-notes/new"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-amber-400/50 text-sm text-amber-300 hover:text-amber-200 hover:border-amber-300/70"
          >
            <Receipt className="w-4 h-4" />
            Create Credit Note
          </Link>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className={cn('text-white font-semibold break-all', row.label === 'Status' && 'capitalize')}>
              {row.value}
            </p>
          </div>
        ))}
      </div>

      {(data as any).items?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Items</h3>
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
                    <td className="px-2 py-2 text-white font-mono">{item.item_code || '-'}</td>
                    <td className="px-2 py-2 text-slate-200">{item.item_name || item.description || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.qty ?? item.quantity ?? 0}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.rate ?? item.unit_price ?? 0}</td>
                    <td className="px-2 py-2 text-right text-white font-mono">{item.amount ?? item.net_amount ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {data.payments?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Payments</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Method</th>
                  <th className="text-right px-2 py-2">Amount</th>
                  <th className="text-left px-2 py-2">Status</th>
                  <th className="text-left px-2 py-2">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.payments.map((p: any) => (
                  <tr key={p.id} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-slate-200">{p.payment_method || '-'}</td>
                    <td className="px-2 py-2 text-right text-white font-mono">{formatCurrency(p.amount, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-slate-200 capitalize">{p.status}</td>
                    <td className="px-2 py-2 text-slate-200">{formatDate(p.payment_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {(data as any).credit_notes?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Receipt className="w-4 h-4 text-amber-300" />
            <h3 className="text-white font-semibold">Credit Notes</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Credit #</th>
                  <th className="text-right px-2 py-2">Amount</th>
                  <th className="text-left px-2 py-2">Status</th>
                  <th className="text-left px-2 py-2">Issue Date</th>
                </tr>
              </thead>
              <tbody>
                {(data as any).credit_notes.map((c: any) => (
                  <tr key={c.id} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-white font-mono">{c.credit_number || `CN-${c.id}`}</td>
                    <td className="px-2 py-2 text-right text-white font-mono">{formatCurrency(c.amount, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-slate-200 capitalize">{c.status}</td>
                    <td className="px-2 py-2 text-slate-200">{formatDate(c.issue_date)}</td>
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
