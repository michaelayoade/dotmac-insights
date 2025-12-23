'use client';

import { useState } from 'react';
import { useAccountingChartOfAccounts } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { AlertTriangle } from 'lucide-react';
import { getChartOfAccountsColumns } from '@/lib/config/accounting-tables';

export default function ChartOfAccountsPage() {
  const [accountType, setAccountType] = useState<string>('');
  const [search, setSearch] = useState('');
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

  const columns = getChartOfAccountsColumns();

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load chart of accounts</p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Accounts</p>
          <p className="text-2xl font-bold text-foreground">{data?.total || 0}</p>
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
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>
        <select
          value={accountType}
          onChange={(e) => setAccountType(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
      />
    </div>
  );
}
