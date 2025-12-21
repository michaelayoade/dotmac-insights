'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CreditCard, FileText, Receipt } from 'lucide-react';
import { usePurchasingPaymentDetail } from '@/hooks/useApi';

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

export default function PurchasingPaymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = usePurchasingPaymentDetail(Number.isFinite(id) ? id : null);

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
        <p className="text-red-400">Failed to load payment</p>
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

  const summary = [
    { label: 'Receipt #', value: data.receipt_number || `Payment #${data.id}` },
    { label: 'Amount', value: formatCurrency(data.amount, data.currency || 'NGN') },
    { label: 'Status', value: data.status },
    { label: 'Method', value: data.payment_method || 'bank_transfer' },
    { label: 'Date', value: formatDate(data.payment_date) },
    { label: 'Reference', value: data.transaction_reference || data.gateway_reference || '—' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/payments"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to payments
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Vendor Payment</p>
            <h1 className="text-xl font-semibold text-foreground">{data.receipt_number || `Payment #${data.id}`}</h1>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-foreground font-semibold break-all">{row.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Supplier</h3>
          </div>
          <p className="text-slate-200 text-sm">
            {data.supplier_name || (data as any).supplier || 'Unknown supplier'}
            {data.supplier_id ? ` (#${data.supplier_id})` : ''}
          </p>
          {data.purchase_invoice_id ? (
            <Link
              href={`/purchasing/bills/${data.purchase_invoice_id}`}
              className="inline-flex items-center gap-2 text-teal-electric text-sm hover:text-teal-glow"
            >
              <FileText className="w-4 h-4" />
              Bill #{data.purchase_invoice_id}
            </Link>
          ) : (
            <p className="text-slate-muted text-sm">No linked bill</p>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Receipt className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Notes</h3>
          </div>
          <p className="text-slate-muted text-sm">{data.notes || 'No notes provided'}</p>
        </div>
      </div>
    </div>
  );
}
