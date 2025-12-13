'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, ShoppingCart, Calendar, Building2, Package } from 'lucide-react';
import { usePurchasingOrderDetail, usePurchasingOrderMutations } from '@/hooks/useApi';
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

export default function PurchasingOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = usePurchasingOrderDetail(Number.isFinite(id) ? id : null);
  const { updateOrder } = usePurchasingOrderMutations();
  const [statusInput, setStatusInput] = useState('draft');
  const [perReceived, setPerReceived] = useState('');
  const [perBilled, setPerBilled] = useState('');
  const [scheduleDate, setScheduleDate] = useState('');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setStatusInput(data.status || 'draft');
      setPerReceived((data as any).per_received !== undefined && (data as any).per_received !== null ? String((data as any).per_received) : '');
      setPerBilled((data as any).per_billed !== undefined && (data as any).per_billed !== null ? String((data as any).per_billed) : '');
      setScheduleDate((data as any).schedule_date || (data as any).delivery_date || '');
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
        <p className="text-red-400">Failed to load purchase order</p>
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

  const summaryRows = [
    { label: 'Supplier', value: data.supplier || '-' },
    { label: 'Order Date', value: formatDate((data as any).transaction_date || data.date) },
    { label: 'Schedule Date', value: formatDate((data as any).schedule_date || data.delivery_date) },
    { label: 'Status', value: data.status || 'draft' },
    { label: 'Total', value: formatCurrency((data as any).grand_total ?? data.total, data.currency || 'NGN') },
    { label: 'Net Total', value: formatCurrency((data as any).net_total ?? data.total, data.currency || 'NGN') },
  ];

  const writeBackClass = cn(
    'px-2 py-1 rounded-full text-xs font-semibold border',
    data.write_back_status === 'pending' && 'border-yellow-500/40 text-yellow-400 bg-yellow-500/10',
    data.write_back_status === 'failed' && 'border-red-500/40 text-red-400 bg-red-500/10',
    data.write_back_status === 'synced' && 'border-green-500/40 text-green-400 bg-green-500/10'
  );

  const handleQuickUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!data) return;
    setSaving(true);
    setActionError(null);
    try {
      await updateOrder(id, {
        status: statusInput || null,
        per_received: perReceived ? Number(perReceived) : undefined,
        per_billed: perBilled ? Number(perBilled) : undefined,
        schedule_date: scheduleDate || undefined,
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to update order');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/orders"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to orders
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Purchase Order</p>
            <h1 className="text-xl font-semibold text-white">{data.order_no || data.order_number || `PO #${id}`}</h1>
            {data.write_back_status && (
              <span className={writeBackClass}>Write-back: {data.write_back_status}</span>
            )}
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summaryRows.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-white font-semibold">{row.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <h3 className="text-white font-semibold">Quick update</h3>
        {actionError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-2 text-sm">{actionError}</div>
        )}
        <form onSubmit={handleQuickUpdate} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Status</label>
            <select
              value={statusInput}
              onChange={(e) => setStatusInput(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="draft">Draft</option>
              <option value="to receive and bill">To receive and bill</option>
              <option value="to bill">To bill</option>
              <option value="to receive">To receive</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="closed">Closed</option>
              <option value="on hold">On hold</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">% Received</label>
            <input
              type="number"
              value={perReceived}
              onChange={(e) => setPerReceived(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">% Billed</label>
            <input
              type="number"
              value={perBilled}
              onChange={(e) => setPerBilled(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Schedule Date</label>
            <input
              type="date"
              value={scheduleDate}
              onChange={(e) => setScheduleDate(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
            <Package className="w-4 h-4 text-teal-electric" />
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
    </div>
  );
}
