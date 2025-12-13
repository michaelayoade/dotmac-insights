'use client';

import { useState } from 'react';
import { useInventoryValuation } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Boxes, Search } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export default function InventoryValuationPage() {
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useInventoryValuation({
    search: search || undefined,
    limit,
    offset,
  });

  const columns = [
    { key: 'item_code', header: 'Item Code' },
    { key: 'item_name', header: 'Item Name' },
    { key: 'warehouse', header: 'Warehouse' },
    {
      key: 'qty',
      header: 'Qty',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{item.qty}</span>,
    },
    {
      key: 'valuation_rate',
      header: 'Rate',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.valuation_rate, item.currency || 'NGN')}</span>,
    },
    {
      key: 'valuation',
      header: 'Value',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.valuation, item.currency || 'NGN')}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Boxes className="w-5 h-5 text-teal-electric" />
          <h1 className="text-2xl font-bold text-white">Inventory Valuation</h1>
        </div>
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-slate-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Search item code or name"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load valuation.</span>
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.data || data || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No inventory valuation available"
        onRowClick={(item) => window.location.assign(`/inventory/valuation/${(item as any).item_code}`)}
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
