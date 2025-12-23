'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, FileText, Users } from 'lucide-react';
import { useFinanceCustomerDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import { formatCurrency, formatDate } from '@/lib/formatters';

export default function SalesCustomerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useFinanceCustomerDetail(Number.isFinite(id) ? id : null);

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
        <p className="text-red-400">Failed to load customer</p>
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

  const summary = [
    { label: 'Customer', value: data.name || `Customer #${data.id}` },
    { label: 'Email', value: data.email || '—' },
    { label: 'Phone', value: data.phone || '—' },
    { label: 'Status', value: data.status || 'active' },
    { label: 'Type', value: data.customer_type || 'business' },
    { label: 'Billing Type', value: data.billing_type || '—' },
    { label: 'City', value: data.city || '—' },
    { label: 'State', value: data.state || '—' },
    { label: 'Signup Date', value: formatDate(data.signup_date) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/customers"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to customers
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Sales Customer</p>
            <h1 className="text-xl font-semibold text-foreground">{data.name || `Customer #${data.id}`}</h1>
          </div>
        </div>
        <Link
          href={`/sales/customers/${data.id}/edit`}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <FileText className="w-4 h-4" />
          Edit Customer
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className={cn('text-foreground font-semibold break-all', row.label === 'Status' && 'capitalize')}>
              {row.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Billing & Metrics</h3>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">MRR</p>
              <p className="text-foreground font-semibold">{formatCurrency(data.mrr ?? 0)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Invoiced</p>
              <p className="text-foreground font-semibold">{formatCurrency(data.invoiced_total ?? 0)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Paid</p>
              <p className="text-foreground font-semibold">{formatCurrency(data.paid_total ?? 0)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Outstanding</p>
              <p className="text-foreground font-semibold">{formatCurrency(data.outstanding_balance ?? 0)}</p>
            </div>
          </div>
          <p className="text-slate-muted text-sm">
            Address: {data.address || '—'}
          </p>
        </div>

        {data.subscriptions?.length ? (
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Subscriptions</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-muted">
                  <tr>
                    <th className="text-left px-2 py-2">Plan</th>
                    <th className="text-right px-2 py-2">Price</th>
                    <th className="text-left px-2 py-2">Status</th>
                    <th className="text-left px-2 py-2">Start</th>
                    <th className="text-left px-2 py-2">End</th>
                  </tr>
                </thead>
                <tbody>
                  {data.subscriptions.map((sub: any) => (
                    <tr key={sub.id} className="border-t border-slate-border/60">
                      <td className="px-2 py-2 text-foreground">{sub.plan_name}</td>
                      <td className="px-2 py-2 text-right text-foreground font-mono">{formatCurrency(sub.price)}</td>
                      <td className="px-2 py-2 text-slate-200 capitalize">{sub.status}</td>
                      <td className="px-2 py-2 text-slate-200">{formatDate(sub.start_date)}</td>
                      <td className="px-2 py-2 text-slate-200">{formatDate(sub.end_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>

      {data.recent_invoices?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Recent Invoices</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Invoice</th>
                  <th className="text-right px-2 py-2">Total</th>
                  <th className="text-right px-2 py-2">Paid</th>
                  <th className="text-left px-2 py-2">Status</th>
                  <th className="text-left px-2 py-2">Due Date</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_invoices.map((inv: any) => (
                  <tr key={inv.id} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-foreground font-mono">
                      <Link href={`/sales/invoices/${inv.id}`} className="hover:text-teal-electric">
                        {inv.invoice_number || `INV-${inv.id}`}
                      </Link>
                    </td>
                    <td className="px-2 py-2 text-right text-foreground font-mono">
                      {formatCurrency(inv.total_amount ?? inv.total ?? 0)}
                    </td>
                    <td className="px-2 py-2 text-right text-slate-200">
                      {formatCurrency(inv.amount_paid ?? 0)}
                    </td>
                    <td className="px-2 py-2 text-slate-200 capitalize">{inv.status}</td>
                    <td className="px-2 py-2 text-slate-200">{formatDate(inv.due_date)}</td>
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
