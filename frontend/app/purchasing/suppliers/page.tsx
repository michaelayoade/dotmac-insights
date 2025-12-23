'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingSuppliers, usePurchasingSupplierGroups } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { Button, FilterCard, FilterInput, FilterSelect, LoadingState } from '@/components/ui';
import {
  AlertTriangle,
  Building2,
  Phone,
  Mail,
  CheckCircle2,
  XCircle,
  FileText,
  Users,
  DollarSign,
} from 'lucide-react';
import { formatCurrency, formatNumber } from '@/lib/formatters';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function PurchasingSuppliersPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:read');
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [groupId, setGroupId] = useState<string>('');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = usePurchasingSuppliers(
    {
      search: search || undefined,
      supplier_group: groupId || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    },
    { isPaused: () => !canFetch }
  );

  const { data: groupsData } = usePurchasingSupplierGroups({ isPaused: () => !canFetch });

  const suppliers = data?.suppliers || [];
  const total = data?.total || 0;
  const groups = groupsData?.groups || [];

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:read permission to view suppliers."
        backHref="/purchasing"
        backLabel="Back to Purchasing"
      />
    );
  }

  const columns = [
    {
      key: 'name',
      header: 'Supplier Name',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-teal-electric" />
          <div>
            <p className="text-foreground font-medium">{item.name || item.supplier_name}</p>
            {item.company_name && item.company_name !== item.name && (
              <p className="text-slate-muted text-xs">{item.company_name}</p>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'contact',
      header: 'Contact',
      render: (item: any) => (
        <div className="space-y-1">
          {item.email || item.email_id ? (
            <div className="flex items-center gap-1 text-sm">
              <Mail className="w-3 h-3 text-slate-muted" />
              <span className="text-foreground-secondary truncate max-w-[180px]">{item.email || item.email_id}</span>
            </div>
          ) : null}
          {item.mobile || item.phone ? (
            <div className="flex items-center gap-1 text-sm">
              <Phone className="w-3 h-3 text-slate-muted" />
              <span className="text-foreground-secondary">{item.mobile || item.phone}</span>
            </div>
          ) : null}
          {!item.email && !item.phone && <span className="text-slate-muted">-</span>}
        </div>
      ),
    },
    {
      key: 'outstanding',
      header: 'Outstanding',
      align: 'right' as const,
      render: (item: any) => {
        const outstanding = item.outstanding || 0;
        return (
          <span
            className={cn('font-mono', outstanding > 0 ? 'text-orange-400' : 'text-green-400')}
          >
            {formatCurrency(outstanding)}
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
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-4 h-4 text-teal-electric" />
          <p className="text-slate-muted text-sm">Total Suppliers</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Active</p>
          </div>
          <p className="text-2xl font-bold text-green-400">
            {formatNumber(total)}
          </p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-orange-400" />
            <p className="text-orange-400 text-sm">Total Outstanding</p>
          </div>
          <p className="text-xl font-bold text-orange-400">
            {formatCurrency(suppliers.reduce((sum: number, s: any) => sum + (s.outstanding || 0), 0))}
          </p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Bills</p>
          </div>
          <p className="text-2xl font-bold text-blue-400">
            {formatNumber(0)}
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={(search || groupId) && (
          <Button
            onClick={() => {
              setSearch('');
              setGroupId('');
              setPage(1);
            }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        contentClassName="flex flex-wrap gap-4 items-center"
      >
        <div className="flex-1 min-w-[200px] max-w-md">
          <FilterInput
            type="text"
            placeholder="Search suppliers..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full placeholder:text-slate-muted focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        {groups.length > 0 && (
          <FilterSelect
            value={groupId}
            onChange={(e) => {
              setGroupId(e.target.value);
              setPage(1);
            }}
            className="focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Groups</option>
            {groups.map((group: any) => (
              <option key={group.name} value={group.name}>
                {group.name}
              </option>
            ))}
          </FilterSelect>
        )}
      </FilterCard>

      {/* Table */}
      <DataTable
        columns={columns}
        data={suppliers}
        keyField="id"
        loading={isLoading}
        emptyMessage="No suppliers found"
        onRowClick={(item) => router.push(`/purchasing/suppliers/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
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
