'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAccountingChartOfAccounts } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, BookOpen, ChevronRight, Folder, FolderOpen } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function getAccountTypeColor(type: string) {
  const colors: Record<string, string> = {
    asset: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    liability: 'bg-red-500/20 text-red-400 border-red-500/30',
    equity: 'bg-green-500/20 text-green-400 border-green-500/30',
    income: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    revenue: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    expense: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  };
  return colors[type?.toLowerCase()] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
}

export default function ChartOfAccountsPage() {
  const [accountType, setAccountType] = useState<string>('');
  const [search, setSearch] = useState('');
  const router = useRouter();
  const { data, isLoading, error } = useAccountingChartOfAccounts(accountType || undefined);

  const accounts = (data as any)?.accounts || (data as any)?.data || [];
  const totals = (data as any) || {};

  // Filter accounts by search term
  const filteredAccounts = accounts.filter((account: any) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      account.account_number?.toLowerCase().includes(searchLower) ||
      account.name?.toLowerCase().includes(searchLower) ||
      account.account_name?.toLowerCase().includes(searchLower) ||
      account.description?.toLowerCase().includes(searchLower)
    );
  });

  const columns = [
    {
      key: 'account_number',
      header: 'Account #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-teal-electric">{item.account_number || '-'}</span>
        </div>
      ),
    },
    {
      key: 'account_name',
      header: 'Account Name',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          {item.is_group ? (
            <FolderOpen className="w-4 h-4 text-yellow-400" />
          ) : item.parent_account ? (
            <ChevronRight className="w-4 h-4 text-slate-muted ml-4" />
          ) : (
            <Folder className="w-4 h-4 text-slate-muted" />
          )}
          <span className={cn('text-white', item.is_group && 'font-semibold')}>
            {item.name || item.account_name}
          </span>
        </div>
      ),
    },
    {
      key: 'account_type',
      header: 'Type',
      render: (item: any) => (
        <span className={cn('px-2 py-1 rounded-full text-xs font-medium border capitalize', getAccountTypeColor(item.root_type || item.account_type))}>
          {item.root_type || item.account_type || '-'}
        </span>
      ),
    },
    {
      key: 'balance',
      header: 'Balance',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn(
          'font-mono',
          (item.balance || 0) >= 0 ? 'text-green-400' : 'text-red-400'
        )}>
          {formatCurrency(item.balance)}
        </span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item: any) => (
        <span className="text-slate-muted text-sm truncate max-w-[200px] block">
          {item.description || '-'}
        </span>
      ),
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (item: any) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border',
          !item.disabled
            ? 'bg-green-500/20 text-green-400 border-green-500/30'
            : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
        )}>
          {!item.disabled ? 'Active' : 'Inactive'}
        </span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load chart of accounts</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Accounts</p>
          <p className="text-2xl font-bold text-white">{data?.total || 0}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Assets</p>
          <p className="text-2xl font-bold text-blue-400">{totals.by_root_type?.asset || totals.by_type?.asset || 0}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">Liabilities</p>
          <p className="text-2xl font-bold text-red-400">{totals.by_root_type?.liability || totals.by_type?.liability || 0}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Equity</p>
          <p className="text-2xl font-bold text-green-400">{totals.by_root_type?.equity || totals.by_type?.equity || 0}</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <p className="text-orange-400 text-sm">Expenses</p>
          <p className="text-2xl font-bold text-orange-400">{totals.by_root_type?.expense || totals.by_type?.expense || 0}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search accounts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <select
          value={accountType}
          onChange={(e) => setAccountType(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Types</option>
          <option value="asset">Assets</option>
          <option value="liability">Liabilities</option>
          <option value="equity">Equity</option>
          <option value="income">Income</option>
          <option value="expense">Expenses</option>
        </select>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={filteredAccounts}
        keyField="id"
        loading={isLoading}
        emptyMessage="No accounts found"
        onRowClick={(item) => {
          if (!(item as any).is_group) {
            router.push(`/books/chart-of-accounts/${(item as any).id}`);
          }
        }}
      />
    </div>
  );
}
