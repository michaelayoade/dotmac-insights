'use client';

import { useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, FileText, CreditCard } from 'lucide-react';
import { useAccountingPurchaseInvoiceDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

export default function PurchaseInvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = useMemo(() => Number(params?.id), [params?.id]);
  const currency = 'NGN';
  const { data, isLoading, error } = useAccountingPurchaseInvoiceDetail(Number.isFinite(id) ? id : null, currency);

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
        <p className="text-red-400">Failed to load purchase invoice</p>
        <Button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
      </div>
    );
  }

  const amountPaid =
    (data as any).amount_paid ??
    (Array.isArray(data.payments)
      ? data.payments.reduce((sum: number, p: { amount?: number }) => sum + (p.amount || 0), 0)
      : 0);
  const balance = data.balance ?? ((data.total_amount || 0) - amountPaid);
  const currentCurrency = data.currency || currency;

  return (
    <div className="space-y-6">
      <Button
        onClick={() => router.back()}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </Button>
      <Link
        href="/books/purchase-invoices"
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
      >
        <FileText className="w-4 h-4" />
        Back to list
      </Link>
      <div className="flex items-center gap-2 text-sm text-slate-muted">
        <Link href="/books" className="hover:text-foreground">Books</Link>
        <span>/</span>
        <Link href="/books/purchase-invoices" className="hover:text-foreground">Purchase Invoices</Link>
        <span>/</span>
        <span className="text-foreground">{data.invoice_number || `#${data.id}`}</span>
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-slate-muted text-sm">Purchase Invoice</p>
            <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
              {data.invoice_number || `#${data.id}`}
              <span className="text-xs px-2 py-1 rounded-full border border-slate-border text-slate-muted capitalize">{data.status}</span>
            </h2>
            <p className="text-slate-muted text-sm mt-1">Supplier: {data.supplier_name || `#${data.supplier_id}`}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-muted">Total</p>
            <p className="text-3xl font-bold text-foreground">{formatAccountingCurrency(data.total_amount, currentCurrency)}</p>
            <p className="text-sm text-amber-warn">Balance: {formatAccountingCurrency(balance, currentCurrency)}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-muted">
          <div>Invoice Date: <span className="text-foreground">{formatAccountingDate(data.invoice_date)}</span></div>
          <div>Due Date: <span className="text-foreground">{formatAccountingDate(data.due_date)}</span></div>
          <div>Description: <span className="text-foreground">{data.description || '—'}</span></div>
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-semibold text-foreground mb-2">Lines</h3>
          {data.lines && data.lines.length > 0 ? (
            <div className="space-y-2">
              {data.lines.map((line: any, idx: number) => (
                <div key={idx} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 text-sm">
                  <div>
                    <p className="text-foreground">{line.item || line.description || 'Line'}</p>
                    <p className="text-slate-muted text-xs">Qty {line.quantity ?? '-'} @ {formatAccountingCurrency(line.rate || 0, currentCurrency)}</p>
                  </div>
                  <p className="font-mono text-foreground">{formatAccountingCurrency(line.amount || 0, currentCurrency)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No line items</p>
          )}
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-semibold text-foreground mb-2">Payments</h3>
          {data.payments && data.payments.length > 0 ? (
            <div className="space-y-2">
              {data.payments.map((pay: { id: number; amount: number; payment_date?: string; method?: string; status?: string }) => (
                <div key={pay.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 text-sm">
                  <div>
                    <p className="text-foreground font-mono">{formatAccountingCurrency(pay.amount, currentCurrency)}</p>
                    <p className="text-slate-muted text-xs">{formatAccountingDate(pay.payment_date)}</p>
                  </div>
                  <div className="text-right text-xs text-slate-muted">
                    <div>{pay.method || '—'}</div>
                    <div className={cn('px-2 py-1 rounded-full border inline-block capitalize', 'border-slate-border text-slate-muted')}>{pay.status}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No payments recorded</p>
          )}
        </div>
      </div>
    </div>
  );
}
