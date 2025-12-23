'use client';

import { useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, Receipt, FileText, Pencil } from 'lucide-react';
import { useFinanceCreditNoteDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import { formatCurrency, formatDate } from '@/lib/formatters';

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    applied: 'bg-green-500/20 text-green-400 border-green-500/30',
    pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    partial: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    cancelled: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    expired: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const color = colors[status?.toLowerCase()] || 'bg-slate-500/20 text-foreground-secondary border-slate-500/30';
  return <span className={cn('px-2 py-1 rounded-full text-xs font-medium border', color)}>{status || 'Unknown'}</span>;
}

export default function CreditNoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = useMemo(() => Number(params?.id), [params?.id]);
  const currency = 'NGN';
  const { data, isLoading, error } = useFinanceCreditNoteDetail(Number.isFinite(id) ? id : null, currency);

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
        <p className="text-red-400">Failed to load credit note</p>
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
      <div className="flex items-center gap-2">
        <Link
          href="/sales/credit-notes"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <Receipt className="w-4 h-4" />
          Back to list
        </Link>
        <Link
          href={`/sales/credit-notes/${data.id}/edit`}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <Pencil className="w-4 h-4" />
          Edit
        </Link>
      </div>
      <div className="flex items-center gap-2 text-sm text-slate-muted">
        <Link href="/sales" className="hover:text-foreground">Sales</Link>
        <span>/</span>
        <Link href="/sales/credit-notes" className="hover:text-foreground">Credit Notes</Link>
        <span>/</span>
        <span className="text-foreground">{data.credit_number || `#${data.id}`}</span>
      </div>

      <div className="bg-slate-card rounded-xl border border-slate-border p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-slate-muted text-sm">Credit Note</p>
            <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
              {data.credit_number || `#${data.id}`}
              <StatusBadge status={data.status} />
            </h2>
            <p className="text-slate-muted text-sm mt-1">Source: {data.source || '—'}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-muted">Amount</p>
            <p className="text-3xl font-bold text-foreground">-{formatCurrency(data.amount, currentCurrency)}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-muted">
          <div>Issue Date: <span className="text-foreground">{formatDate(data.issue_date)}</span></div>
          <div>Applied: <span className="text-foreground">{formatDate(data.applied_date)}</span></div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-muted">
          <div>
            <p className="text-xs uppercase mb-1">Customer</p>
            <p className="text-foreground">
              {data.customer_name || 'Unknown'}
            </p>
          </div>
          <div className="md:col-span-2">
            <p className="text-xs uppercase text-slate-muted mb-1">Invoice</p>
            {data.invoice?.id ? (
              <Link href={`/sales/invoices/${data.invoice.id}`} className="inline-flex items-center gap-2 text-teal-electric hover:text-teal-glow text-sm">
                <FileText className="w-4 h-4" />
                {data.invoice.invoice_number || `Invoice #${data.invoice.id}`}
              </Link>
            ) : (
              <p className="text-slate-muted text-sm">No linked invoice</p>
            )}
          </div>
        </div>

        <div className="mt-4 text-sm text-slate-muted">
          <p className="text-xs uppercase mb-1">Description</p>
          <p className="text-foreground">{data.description || 'No description'}</p>
        </div>
      </div>
    </div>
  );
}
