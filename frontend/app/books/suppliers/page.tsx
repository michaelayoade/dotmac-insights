'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAccountingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';

import { AlertTriangle, Plus } from 'lucide-react';
import { Button, LinkButton } from '@/components/ui';
import { getSuppliersColumns } from '@/lib/config/accounting-tables';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

export default function SuppliersPage() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');

  const { data, isLoading, error } = useAccountingSuppliers({
    search: search || undefined,
    status: status || undefined,
    limit,
    offset,
  });
  const supplierStats: any = data || {};
  const totalOutstanding = supplierStats.total_outstanding ?? supplierStats.outstanding ?? 0;
  const totalPurchases = supplierStats.total_purchases ?? supplierStats.total_invoices ?? 0;
  const supplierRows = supplierStats.suppliers ?? supplierStats.data ?? [];

  const columns = getSuppliersColumns();

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load suppliers</p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Suppliers</p>
          <p className="text-2xl font-bold text-foreground">{data?.total || 0}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Active</p>
          <p className="text-2xl font-bold text-green-400">{supplierStats?.active || supplierStats?.by_status?.active || 0}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">Total Outstanding</p>
          <p className="text-xl font-bold text-orange-400">{formatAccountingCurrency(totalOutstanding)}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Total Purchases</p>
          <p className="text-xl font-bold text-blue-400">{formatAccountingCurrency(totalPurchases)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap gap-4 items-center flex-1">
          <div className="flex-1 min-w-[200px] max-w-md">
            <input
              type="text"
              placeholder="Search suppliers..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
              className="input-field"
            />
          </div>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
            className="input-field"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          {(search || status) && (
            <Button
              onClick={() => { setSearch(''); setStatus(''); setOffset(0); }}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear filters
            </Button>
          )}
        </div>
        <LinkButton href="/books/suppliers/new" module="books" icon={Plus}>
          Add Supplier
        </LinkButton>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={supplierRows as any[]}
        keyField="id"
        loading={isLoading}
        emptyMessage="No suppliers found"
        onRowClick={(item) => router.push(`/books/suppliers/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {data && (data.total || 0) > limit && (
        <Pagination
          total={data.total || 0}
          limit={limit}
          offset={offset}
          onPageChange={setOffset}
          onLimitChange={(newLimit) => {
            setLimit(newLimit);
            setOffset(0);
          }}
        />
      )}
    </div>
  );
}
