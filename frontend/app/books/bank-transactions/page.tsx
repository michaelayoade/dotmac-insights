'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAccountingBankTransactions } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Landmark, Plus, Upload } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function BankTransactionsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [account, setAccount] = useState('');
  const [search, setSearch] = useState('');

  const { data, isLoading, error } = useAccountingBankTransactions({
    status: status || undefined,
    account: account || undefined,
    search: search || undefined,
    page,
    page_size: pageSize,
  });

  const columns = [
    { key: 'id', header: 'ID', render: (item: any) => <span className="font-mono text-teal-electric">#{item.erpnext_id || item.id}</span> },
    { key: 'account', header: 'Account', render: (item: any) => <span className="text-white">{item.account}</span> },
    { key: 'type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.transaction_type || '-'}</span> },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <span className="font-mono text-white">{formatCurrency(item.amount ?? item.deposit ?? item.withdrawal, item.currency)}</span>
          <div className="text-xs text-slate-muted">
            {item.deposit ? `+${formatCurrency(item.deposit, item.currency)}` : null}
            {item.withdrawal ? `-${formatCurrency(item.withdrawal, item.currency)}` : null}
          </div>
        </div>
      ),
    },
    {
      key: 'allocated',
      header: 'Allocated',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-slate-200">
          {formatCurrency(item.allocated_amount ?? 0, item.currency)} / {formatCurrency(item.amount ?? item.deposit ?? 0, item.currency)}
        </span>
      ),
    },
    { key: 'status', header: 'Status', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.status}</span> },
    { key: 'transaction_date', header: 'Date', render: (item: any) => <span className="text-slate-muted">{formatDate(item.transaction_date)}</span> },
    { key: 'description', header: 'Description', render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[220px] block">{item.description || item.reference || item.reference_number || '-'}</span> },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load bank transactions</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Landmark className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-white">Bank Transactions</h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/books/bank-transactions/new"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-muted transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Transaction
          </Link>
          <Link
            href="/books/bank-transactions/import"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Import
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search reference/description..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="input-field"
          />
        </div>
        <input
          type="text"
          placeholder="Account"
          value={account}
          onChange={(e) => { setAccount(e.target.value); setPage(1); }}
          className="input-field"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="input-field"
        >
          <option value="">All Status</option>
          <option value="posted">Posted</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <DataTable
        columns={columns}
        data={data?.transactions || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No bank transactions found"
        onRowClick={(item) => router.push(`/books/bank-transactions/${(item as any).id}`)}
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => { setPageSize(newLimit); setPage(1); }}
        />
      )}
    </div>
  );
}
