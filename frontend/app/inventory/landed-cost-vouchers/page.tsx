'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useLandedCostVouchers, useLandedCostVoucherMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Boxes, CheckCircle2, Loader2 } from 'lucide-react';

export default function LandedCostVouchersPage() {
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error, mutate } = useLandedCostVouchers({ limit, offset });
  const { submit } = useLandedCostVoucherMutations();

  const rows = data?.data || data || [];

  const columns = [
    {
      key: 'id',
      header: 'Voucher',
      render: (item: any) => (
        <Link href={`/inventory/landed-cost-vouchers/${item.id}`} className="text-teal-electric hover:underline">
          {item.name || `LCV-${item.id}`}
        </Link>
      ),
    },
    { key: 'company', header: 'Company' },
    { key: 'posting_date', header: 'Posting Date' },
    { key: 'status', header: 'Status' },
    {
      key: 'total_taxes_and_charges',
      header: 'Total',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{item.total_taxes_and_charges ?? item.total ?? 0}</span>,
    },
    {
      key: 'actions',
      header: '',
      render: (item: any) => (
        item.status === 'draft' ? (
          <button
            onClick={async () => { await submit(item.id); await mutate(); }}
            className="text-xs px-2 py-1 rounded-md bg-teal-electric text-slate-950 hover:bg-teal-electric/90"
          >
            Submit
          </button>
        ) : (
          <span className="text-xs inline-flex items-center gap-1 text-green-400">
            <CheckCircle2 className="w-4 h-4" /> {item.status}
          </span>
        )
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load landed cost vouchers</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Boxes className="w-5 h-5 text-teal-electric" />
          <h1 className="text-2xl font-bold text-white">Landed Cost Vouchers</h1>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={rows}
        keyField="id"
        loading={isLoading}
        emptyMessage="No landed cost vouchers found"
      />

      {data && data.total > limit && (
        <Pagination
          total={data.total}
          limit={limit}
          offset={offset}
          onPageChange={setOffset}
          onLimitChange={(newLimit) => { setLimit(newLimit); setOffset(0); }}
        />
      )}
    </div>
  );
}
