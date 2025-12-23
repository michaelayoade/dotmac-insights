'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAccountingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';

import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui';
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
  const summary = (data as any) || {};

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
          <p className="text-2xl font-bold text-foreground">{summary.total || 0}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Active</p>
          <p className="text-2xl font-bold text-green-400">{summary.active || summary.by_status?.active || 0}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">Total Outstanding</p>
          <p className="text-xl font-bold text-orange-400">{formatAccountingCurrency(summary.total_outstanding)}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Total Purchases</p>
          <p className="text-xl font-bold text-blue-400">{formatAccountingCurrency(summary.total_purchases)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search suppliers..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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

      {/* Table */}
      <DataTable
        columns={columns}
        data={summary.suppliers || summary.data || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No suppliers found"
        onRowClick={(item) => router.push(`/accounting/suppliers/${(item as any).id}`)}
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
