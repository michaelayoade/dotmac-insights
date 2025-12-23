'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useInventoryValuationDetail } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Boxes } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export default function InventoryValuationDetailPage() {
  const params = useParams();
  const code = params?.item_code as string;
  const { data, isLoading, error } = useInventoryValuationDetail(code || null);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load valuation detail</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link
            href="/inventory/valuation"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <Boxes className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">{code}</h1>
        </div>
      </div>

      {isLoading ? (
        <p className="text-slate-muted">Loading...</p>
      ) : (
        <>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Info label="Item" value={data?.item_name || code} />
            <Info label="Warehouse" value={data?.warehouse || '—'} />
            <Info label="Qty" value={data?.qty ?? 0} />
            <Info label="Valuation Rate" value={formatCurrency(data?.valuation_rate ?? 0, data?.currency || 'NGN')} />
            <Info label="Value" value={formatCurrency(data?.valuation ?? 0, data?.currency || 'NGN')} />
            <Info label="Method" value={data?.valuation_method || '—'} />
          </div>

          {data?.cost_layers?.length ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-4">
              <p className="text-sm text-slate-muted mb-3">Cost Layers</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-slate-muted">
                    <tr>
                      <th className="text-left px-2 py-2">Date</th>
                      <th className="text-left px-2 py-2">Qty</th>
                      <th className="text-left px-2 py-2">Rate</th>
                      <th className="text-left px-2 py-2">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cost_layers.map((layer: any, idx: number) => (
                      <tr key={idx} className="border-t border-slate-border/60">
                        <td className="px-2 py-2 text-slate-200">{layer.date || '-'}</td>
                        <td className="px-2 py-2 text-slate-200">{layer.qty}</td>
                        <td className="px-2 py-2 text-slate-200">{formatCurrency(layer.rate, data.currency || 'NGN')}</td>
                        <td className="px-2 py-2 text-slate-200">{formatCurrency(layer.value, data.currency || 'NGN')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.08em] text-slate-muted">{label}</p>
      <p className="text-foreground font-semibold">{value}</p>
    </div>
  );
}
