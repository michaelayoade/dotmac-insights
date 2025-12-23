'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, FileText, Package } from 'lucide-react';
import { useFinanceOrderDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import { formatCurrency, formatDate } from '@/lib/formatters';

export default function SalesOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useFinanceOrderDetail(Number.isFinite(id) ? id : null, 'NGN');

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
        <p className="text-red-400">Failed to load sales order</p>
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
    { label: 'Order #', value: data.erpnext_id || data.order_number || `SO-${data.id}` },
    { label: 'Customer', value: data.customer_name || (data.customer_id ? `Customer #${data.customer_id}` : '-') },
    { label: 'Status', value: data.status || 'draft' },
    { label: 'Billing', value: data.billing_status || 'n/a' },
    { label: 'Delivery', value: data.delivery_status || 'n/a' },
    { label: 'Order Date', value: formatDate((data as any).transaction_date || data.order_date) },
    { label: 'Delivery Date', value: formatDate((data as any).delivery_date) },
    {
      label: 'Total',
      value: formatCurrency((data as any).grand_total ?? (data as any).total_amount ?? (data as any).total, data.currency || 'NGN'),
    },
    {
      label: 'Net Total',
      value: formatCurrency((data as any).net_total ?? (data as any).total ?? 0, data.currency || 'NGN'),
    },
    {
      label: 'Taxes',
      value: formatCurrency((data as any).total_taxes_and_charges ?? 0, data.currency || 'NGN'),
    },
  ];

  const items = (data as any).items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/sales/orders"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to orders
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Sales Order</p>
            <h1 className="text-xl font-semibold text-foreground">
              {data.order_number || data.erpnext_id || `Order #${data.id}`}
            </h1>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/sales/orders/${id}/edit`}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
          >
            <FileText className="w-4 h-4" />
            Edit Order
          </Link>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p
              className={cn(
                'text-foreground font-semibold break-all',
                row.label === 'Status' && 'capitalize',
                (row.label === 'Billing' || row.label === 'Delivery') && 'capitalize'
              )}
            >
              {row.value}
            </p>
          </div>
        ))}
      </div>

      {items.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-teal-electric" />
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
                  <th className="text-right px-2 py-2">Delivered</th>
                  <th className="text-right px-2 py-2">Billed</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-foreground font-mono">{item.item_code || '-'}</td>
                    <td className="px-2 py-2 text-slate-200">{item.item_name || item.description || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.qty ?? item.stock_qty ?? 0}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.rate ?? item.price_list_rate ?? 0}</td>
                    <td className="px-2 py-2 text-right text-foreground font-mono">{item.amount ?? item.net_amount ?? 0}</td>
                    <td className="px-2 py-2 text-right text-slate-200">
                      {item.delivered_qty ?? item.per_delivered ?? 0}
                    </td>
                    <td className="px-2 py-2 text-right text-slate-200">{item.billed_amt ?? 0}</td>
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
