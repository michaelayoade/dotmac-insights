'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useLandedCostVoucherDetail, useLandedCostVoucherMutations } from '@/hooks/useApi';
import { AlertTriangle, ArrowLeft, Boxes, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui';

export default function LandedCostVoucherDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const { data, isLoading, error, mutate } = useLandedCostVoucherDetail(id || null);
  const { submit } = useLandedCostVoucherMutations();

  const onSubmit = async () => {
    await submit(id);
    await mutate();
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load voucher</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link
            href="/inventory/landed-cost-vouchers"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <Boxes className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Voucher {id}</h1>
        </div>
        {data?.status === 'draft' ? (
          <Button
            onClick={onSubmit}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
          >
            Submit
          </Button>
        ) : (
          <span className="inline-flex items-center gap-2 text-green-400 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            {data?.status || 'Submitted'}
          </span>
        )}
      </div>

      {isLoading ? (
        <Loader2 className="w-6 h-6 animate-spin text-teal-electric" />
      ) : (
        <>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Info label="Company" value={data?.company || '—'} />
            <Info label="Posting Date" value={data?.posting_date || '—'} />
            <Info label="Total" value={data?.total_taxes_and_charges ?? data?.total ?? 0} />
            <Info label="Currency" value={data?.currency || 'NGN'} />
            <Info label="Status" value={data?.status || 'draft'} />
          </div>

          {data?.items?.length ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-4">
              <p className="text-sm text-slate-muted mb-2">Items</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-slate-muted">
                    <tr>
                      <th className="text-left px-2 py-2">Item</th>
                      <th className="text-left px-2 py-2">Qty</th>
                      <th className="text-left px-2 py-2">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((it: any, idx: number) => (
                      <tr key={idx} className="border-t border-slate-border/60">
                        <td className="px-2 py-2 text-slate-200">{it.item_code}</td>
                        <td className="px-2 py-2 text-slate-200">{it.qty}</td>
                        <td className="px-2 py-2 text-slate-200">{it.amount}</td>
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
