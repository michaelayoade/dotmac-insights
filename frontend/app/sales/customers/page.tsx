'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useFinanceCustomers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Users, FileText } from 'lucide-react';

export default function SalesCustomersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const { data, isLoading, error } = useFinanceCustomers({
    search: search || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const customers = (data as any)?.items || (data as any)?.customers || [];
  const total = data?.total || 0;

  const columns = [
    {
      key: 'name',
      header: 'Customer',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="text-foreground font-medium">{item.name}</span>
          <span className="text-xs text-slate-muted">{item.email || item.phone || '—'}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <span className="text-xs text-slate-muted capitalize">{item.status || 'active'}</span>,
    },
    {
      key: 'city',
      header: 'City',
      render: (item: any) => <span className="text-slate-muted text-sm">{item.city || '-'}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load customers</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Sales Customers</h1>
        </div>
        <Link
          href="/sales/customers/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <FileText className="w-4 h-4" />
          New Customer
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search customers..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full sm:w-64 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
      </div>

      <DataTable
        columns={columns}
        data={customers}
        keyField="id"
        loading={isLoading}
        emptyMessage="No customers found"
        onRowClick={(item: { id: number }) => router.push(`/sales/customers/${item.id}`)}
        className="cursor-pointer"
      />

      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
