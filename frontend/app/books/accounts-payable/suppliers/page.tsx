'use client';

import { useState } from 'react';
import { Factory, AlertTriangle } from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useAccountingPayables } from '@/hooks/useApi';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export default function FinanceSuppliersPage() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);

  const { data, isLoading, error } = useAccountingPayables(
    { limit, offset },
    { dedupingInterval: 2 * 60 * 1000 }
  );

  const columns = [
    {
      key: 'supplier_name',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Factory className="w-4 h-4 text-amber-400" />
          <div className="flex flex-col">
            <span className="text-foreground text-sm">{item.supplier_name || 'Unknown'}</span>
            {item.supplier && <span className="text-xs text-slate-muted font-mono">{item.supplier}</span>}
          </div>
        </div>
      ),
    },
    {
      key: 'total_payable',
      header: 'Total AP',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.total_payable)}</span>,
    },
    {
      key: 'current',
      header: 'Current',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-green-400">{formatCurrency(item.current)}</span>,
    },
    {
      key: 'overdue_1_30',
      header: '1-30',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-yellow-400">{formatCurrency(item.overdue_1_30)}</span>,
    },
    {
      key: 'overdue_31_60',
      header: '31-60',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-orange-400">{formatCurrency(item.overdue_31_60)}</span>,
    },
    {
      key: 'overdue_over_90',
      header: '90+',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-red-400">{formatCurrency(item.overdue_over_90)}</span>,
    },
    {
      key: 'bill_count',
      header: '# Bills',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{item.bill_count ?? 0}</span>,
    },
  ];

  const items = data?.items || data?.data || [];
  const total = data?.total || items.length;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load supplier finance view</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Suppliers (Finance)</h1>
          <p className="text-slate-muted text-sm">Payables snapshot by supplier for accounting.</p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={items}
        keyField="supplier"
        loading={isLoading}
        emptyMessage="No suppliers found"
      />

      {total > limit && (
        <Pagination
          total={total}
          limit={limit}
          offset={offset}
          onPageChange={setOffset}
          onLimitChange={(val) => {
            setLimit(val);
            setOffset(0);
          }}
        />
      )}
    </div>
  );
}
