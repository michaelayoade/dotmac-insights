'use client';

import { useState } from 'react';
import { usePurchasingExpenses } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Receipt, Calendar, DollarSign, Building2, Filter, Briefcase, Tag, TrendingDown, Search, BookOpen } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function GLExpensesPage() {
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [costCenter, setCostCenter] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const { data, isLoading, error } = usePurchasingExpenses({
    cost_center: costCenter || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    search: search || undefined,
    currency,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const expenses = data?.expenses || [];
  const total = data?.total || 0;
  const summary = data?.summary || {};
  const totalAmount = expenses.reduce((sum: number, e: { amount?: number }) => sum + (e.amount || 0), 0);
  const avgAmount = total > 0 ? totalAmount / total : 0;

  const columns = [
    {
      key: 'expense_number',
      header: 'Voucher #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-teal-400" />
          <span className="font-mono text-white font-medium">
            {item.voucher_no || `#${item.id}`}
          </span>
        </div>
      ),
    },
    {
      key: 'expense_type',
      header: 'Type',
      render: (item: any) => (
        <div className="flex items-center gap-1.5">
          <Tag className="w-3.5 h-3.5 text-slate-muted" />
          <span className="text-slate-300 text-sm capitalize">
            {item.voucher_type || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'account',
      header: 'Account',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-slate-muted" />
          <span className="text-slate-300 truncate max-w-[180px]">
            {item.account || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'party',
      header: 'Party',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-muted" />
          <span className="text-slate-300 truncate max-w-[150px]">
            {item.party || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-slate-300">
            {formatDate(item.posting_date)}
          </span>
        </div>
      ),
    },
    {
      key: 'cost_center',
      header: 'Cost Center',
      render: (item: any) => (
        <div className="flex items-center gap-1.5">
          <Briefcase className="w-3.5 h-3.5 text-slate-muted" />
          <span className="text-slate-muted text-sm truncate max-w-[120px]">
            {item.cost_center || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white font-medium">
          {formatCurrency(item.amount)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load GL expense entries</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      {/* Header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">GL Expense Entries</h1>
            <p className="text-slate-muted text-sm mt-1">
              Read-only view of expense-type journal entries from the general ledger
            </p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Receipt className="w-4 h-4 text-teal-400" />
            <p className="text-slate-muted text-sm">Total Entries</p>
          </div>
          <p className="text-2xl font-bold text-white">{formatNumber(total)}</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <p className="text-red-400 text-sm">Total Expenses</p>
          </div>
          <p className="text-xl font-bold text-red-400">
            {formatCurrency(summary.total_amount || summary.total_spent || 0)}
          </p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-blue-400" />
            <p className="text-blue-400 text-sm">Average Entry</p>
          </div>
          <p className="text-xl font-bold text-blue-400">
            {formatCurrency(avgAmount)}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <p className="text-slate-muted text-sm">Period</p>
          </div>
          <p className="text-sm font-medium text-white">
            {startDate && endDate ? `${formatDate(startDate)} - ${formatDate(endDate)}` : 'All time'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-400" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="w-4 h-4 text-slate-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search entries..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            />
          </div>
          <div className="flex-1 min-w-[200px] max-w-md">
            <input
              type="text"
              placeholder="Filter by cost center"
              value={costCenter}
              onChange={(e) => {
                setCostCenter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
              placeholder="Start date"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
              placeholder="End date"
            />
          </div>
          {(search || costCenter || startDate || endDate) && (
            <button
              onClick={() => {
                setSearch('');
                setCostCenter('');
                setStartDate('');
                setEndDate('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={expenses}
        keyField="id"
        loading={isLoading}
        emptyMessage="No GL expense entries found"
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
