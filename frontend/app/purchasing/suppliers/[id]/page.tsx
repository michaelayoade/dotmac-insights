'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Building2, FileText, Mail, Phone, Receipt, Users } from 'lucide-react';
import { usePurchasingSupplierDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null | undefined) {
  if (!date) return '—';
  return new Date(date).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function PurchasingSupplierDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = usePurchasingSupplierDetail(Number.isFinite(id) ? id : null);

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
        <p className="text-red-400">Failed to load supplier</p>
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
    { label: 'Supplier', value: data.name || data.supplier_name || `Supplier #${data.id}` },
    { label: 'Group', value: data.group || '—' },
    { label: 'Type', value: data.type || '—' },
    { label: 'Country', value: data.country || '—' },
    { label: 'Currency', value: data.currency || 'NGN' },
    { label: 'Tax ID', value: data.tax_id || '—' },
    { label: 'PAN', value: data.pan || '—' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/suppliers"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to suppliers
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Supplier</p>
            <h1 className="text-xl font-semibold text-white">{data.name || data.supplier_name || `Supplier #${data.id}`}</h1>
          </div>
        </div>
        <Link
          href="/purchasing/bills/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <Receipt className="w-4 h-4" />
          New Bill
        </Link>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Contact</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-slate-200">
              <Mail className="w-4 h-4 text-slate-muted" />
              <span>{data.email || data.email_id || '—'}</span>
            </div>
            <div className="flex items-center gap-2 text-slate-200">
              <Phone className="w-4 h-4 text-slate-muted" />
              <span>{data.mobile || data.phone || '—'}</span>
            </div>
            <p className="text-slate-muted text-sm">Currency: {data.currency || 'NGN'}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Total Purchases</p>
              <p className="text-white font-semibold">{formatCurrency(data.total_purchases)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Outstanding</p>
              <p className="text-white font-semibold">{formatCurrency(data.total_outstanding)}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Bill Count</p>
              <p className="text-white font-semibold">{data.bill_count ?? 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Recent Bills</h3>
          </div>
          {data.recent_bills?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-muted">
                  <tr>
                    <th className="text-left px-2 py-2">Bill</th>
                    <th className="text-left px-2 py-2">Date</th>
                    <th className="text-right px-2 py-2">Amount</th>
                    <th className="text-right px-2 py-2">Outstanding</th>
                    <th className="text-left px-2 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_bills.map((bill) => (
                    <tr key={bill.id} className="border-t border-slate-border/60">
                      <td className="px-2 py-2 text-white font-mono">
                        <Link href={`/purchasing/bills/${bill.id}`} className="hover:text-teal-electric">
                          {bill.bill_no || `Bill #${bill.id}`}
                        </Link>
                      </td>
                      <td className="px-2 py-2 text-slate-200">{formatDate(bill.date)}</td>
                      <td className="px-2 py-2 text-right text-white font-mono">
                        {formatCurrency(bill.amount, data.currency || 'NGN')}
                      </td>
                      <td className="px-2 py-2 text-right text-slate-200">
                        {formatCurrency(bill.outstanding, data.currency || 'NGN')}
                      </td>
                      <td className="px-2 py-2 text-slate-200 capitalize">{bill.status || 'open'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No recent bills</p>
          )}
        </div>
      </div>
    </div>
  );
}
