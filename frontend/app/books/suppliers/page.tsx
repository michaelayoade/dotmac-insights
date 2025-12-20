'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAccountingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, Building, Phone, Mail, MapPin, CheckCircle2, XCircle } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

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

  const columns = [
    {
      key: 'name',
      header: 'Supplier Name',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building className="w-4 h-4 text-teal-electric" />
          <span className="text-white font-medium">{item.name || item.supplier_name}</span>
        </div>
      ),
    },
    {
      key: 'code',
      header: 'Code',
      render: (item: any) => (
        <span className="font-mono text-slate-muted">{item.code || item.supplier_code || '-'}</span>
      ),
    },
    {
      key: 'contact',
      header: 'Contact',
      render: (item: any) => (
        <div className="space-y-1">
          {item.email && (
            <div className="flex items-center gap-1 text-sm">
              <Mail className="w-3 h-3 text-slate-muted" />
              <span className="text-slate-300">{item.email}</span>
            </div>
          )}
          {item.phone && (
            <div className="flex items-center gap-1 text-sm">
              <Phone className="w-3 h-3 text-slate-muted" />
              <span className="text-slate-300">{item.phone}</span>
            </div>
          )}
          {!item.email && !item.phone && <span className="text-slate-muted">-</span>}
        </div>
      ),
    },
    {
      key: 'balance',
      header: 'Outstanding',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn(
          'font-mono',
          (item.balance || item.outstanding_balance || 0) > 0 ? 'text-orange-400' : 'text-green-400'
        )}>
          {formatCurrency(item.balance || item.outstanding_balance)}
        </span>
      ),
    },
    {
      key: 'total_purchases',
      header: 'Total Purchases',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white">
          {formatCurrency(item.total_purchases || item.total_invoices)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const isActive = item.status === 'active' || item.is_active !== false;
        return (
          <span className={cn(
            'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
            isActive
              ? 'bg-green-500/20 text-green-400 border-green-500/30'
              : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
          )}>
            {isActive ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
            {isActive ? 'Active' : 'Inactive'}
          </span>
        );
      },
    },
  ];

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
          <p className="text-2xl font-bold text-white">{data?.total || 0}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Active</p>
          <p className="text-2xl font-bold text-green-400">{supplierStats?.active || supplierStats?.by_status?.active || 0}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">Total Outstanding</p>
          <p className="text-xl font-bold text-orange-400">{formatCurrency(totalOutstanding)}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Total Purchases</p>
          <p className="text-xl font-bold text-blue-400">{formatCurrency(totalPurchases)}</p>
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
          <button
            onClick={() => { setSearch(''); setStatus(''); setOffset(0); }}
            className="text-slate-muted text-sm hover:text-white transition-colors"
          >
            Clear filters
          </button>
        )}
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
