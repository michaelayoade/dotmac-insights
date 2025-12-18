'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CreditCard, FileText, User } from 'lucide-react';
import { useFinancePaymentDetail } from '@/hooks/useApi';

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

export default function SalesPaymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useFinancePaymentDetail(Number.isFinite(id) ? id : null, 'NGN');

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
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
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
    { label: 'Method', value: data.payment_method || '-' },
    { label: 'Date', value: formatDate(data.payment_date) },
    { label: 'Reference', value: data.transaction_reference || data.gateway_reference || '-' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/payments"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to payments
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Payment</p>
            <h1 className="text-xl font-semibold text-white">{data.receipt_number || `Payment #${data.id}`}</h1>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Customer</h3>
          </div>
          {data.customer ? (
            <div className="text-sm text-slate-200 space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{data.customer.name || `Customer ${data.customer.id}`}</span>
                {data.customer.id && (
                  <span className="text-xs text-slate-muted font-mono">#{data.customer.id}</span>
                )}
              </div>
              {data.customer.email && <p className="text-slate-muted text-sm">{data.customer.email}</p>}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No customer linked</p>
          )}
          {data.invoice && data.invoice.id ? (
            <Link
              href={`/sales/invoices/${data.invoice.id}`}
              className="inline-flex items-center gap-2 text-teal-electric text-sm hover:text-teal-glow"
            >
              <FileText className="w-4 h-4" />
              Invoice {data.invoice.invoice_number || `#${data.invoice.id}`}
            </Link>
          ) : (
            <p className="text-slate-muted text-sm">No invoice linked</p>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Notes</h3>
          </div>
          <p className="text-slate-muted text-sm">
            {data.notes || 'No notes provided'}
          </p>
          {data.external_ids && (
            <div className="text-xs text-slate-muted space-y-1">
              {data.external_ids.erpnext_id && <div>ERPNext: {data.external_ids.erpnext_id}</div>}
              {data.external_ids.splynx_id && <div>Splynx: {data.external_ids.splynx_id}</div>}
            </div>
          )}
        </div>
      </div>

      {data.references?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Allocations</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Reference</th>
                  <th className="text-right px-2 py-2">Total</th>
                  <th className="text-right px-2 py-2">Outstanding</th>
                  <th className="text-right px-2 py-2">Allocated</th>
                  <th className="text-left px-2 py-2">Due Date</th>
                </tr>
              </thead>
              <tbody>
                {data.references.map((ref: any) => (
                  <tr key={ref.id || ref.reference_name} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-slate-200">
                      {ref.reference_doctype || '-'} {ref.reference_name || ''}
                    </td>
                    <td className="px-2 py-2 text-right text-slate-200">
                      {formatCurrency(ref.total_amount ?? 0, data.currency || 'NGN')}
                    </td>
                    <td className="px-2 py-2 text-right text-slate-200">
                      {formatCurrency(ref.outstanding_amount ?? 0, data.currency || 'NGN')}
                    </td>
                    <td className="px-2 py-2 text-right text-white font-mono">
                      {formatCurrency(ref.allocated_amount ?? 0, data.currency || 'NGN')}
                    </td>
                    <td className="px-2 py-2 text-slate-200">{formatDate(ref.due_date)}</td>
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
