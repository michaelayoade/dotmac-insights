'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAccountingJournalEntries } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { AlertTriangle, ClipboardList, Calendar, FileText, CreditCard, Receipt, ShoppingCart } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs text-slate-muted mb-1">{children}</label>;
}

function VoucherTypeBadge({ type }: { type: string }) {
  const config: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    'Journal Entry': { bg: 'bg-teal-500/10', border: 'border-teal-500/40', text: 'text-teal-300', icon: <ClipboardList className="w-3 h-3" /> },
    'Payment Entry': { bg: 'bg-violet-500/10', border: 'border-violet-500/40', text: 'text-violet-300', icon: <CreditCard className="w-3 h-3" /> },
    'Sales Invoice': { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: <Receipt className="w-3 h-3" /> },
    'Purchase Invoice': { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', icon: <ShoppingCart className="w-3 h-3" /> },
  };
  const style = config[type] || { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-slate-300', icon: <FileText className="w-3 h-3" /> };
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', style.bg, style.border, style.text)}>
      {style.icon}
      <span>{type || 'Unknown'}</span>
    </span>
  );
}

export default function JournalEntriesPage() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [voucherType, setVoucherType] = useState<string>('');

  const { data, isLoading, error } = useAccountingJournalEntries({
    voucher_type: voucherType || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit,
    offset,
  });
  const summary = (data as any)?.summary || {};
  const entries = (data as any)?.entries || (data as any)?.data || [];

  const columns = [
    {
      key: 'entry_number',
      header: 'Entry Number',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-teal-electric font-medium">{item.voucher_no || `JE-${item.id}`}</span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Posting Date',
      sortable: true,
      render: (item: any) => (
        <span className="text-slate-muted">{formatDate(item.posting_date)}</span>
      ),
    },
    {
      key: 'voucher_type',
      header: 'Voucher Type',
      render: (item: any) => <VoucherTypeBadge type={item.voucher_type} />,
    },
    {
      key: 'debit_total',
      header: 'Total Debit',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-cyan-400">
          {formatCurrency(item.debit_total || item.total_debit)}
        </span>
      ),
    },
    {
      key: 'credit_total',
      header: 'Total Credit',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-emerald-400">
          {formatCurrency(item.credit_total || item.total_credit)}
        </span>
      ),
    },
    {
      key: 'remarks',
      header: 'Remarks',
      render: (item: any) => (
        <span className="text-slate-muted text-sm truncate max-w-[240px] block">
          {item.user_remark || '-'}
        </span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load journal entries</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Entries</p>
          <p className="text-2xl font-bold text-white">{data?.total || 0}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">Total Debit</p>
          <p className="text-2xl font-bold text-blue-400">{formatCurrency(summary.total_debit)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <p className="text-green-400 text-sm">Total Credit</p>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(summary.total_credit)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <p className="text-xs text-slate-muted mb-3">Filter Journal Entries</p>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="min-w-[200px]">
            <FormLabel>Voucher Type</FormLabel>
            <select
              value={voucherType}
              onChange={(e) => { setVoucherType(e.target.value); setOffset(0); }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="">All Types</option>
              <option value="Journal Entry">Journal Entry</option>
              <option value="Payment Entry">Payment Entry</option>
              <option value="Sales Invoice">Sales Invoice</option>
              <option value="Purchase Invoice">Purchase Invoice</option>
            </select>
          </div>
          <div>
            <FormLabel>Start Date</FormLabel>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-muted" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => { setStartDate(e.target.value); setOffset(0); }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div>
            <FormLabel>End Date</FormLabel>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-muted" />
              <input
                type="date"
                value={endDate}
                onChange={(e) => { setEndDate(e.target.value); setOffset(0); }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          {(startDate || endDate || voucherType) && (
            <button
              onClick={() => { setStartDate(''); setEndDate(''); setVoucherType(''); setOffset(0); }}
              className="px-3 py-2 text-slate-muted text-sm hover:text-white border border-slate-border rounded-lg hover:border-slate-muted transition-colors"
            >
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={entries}
        keyField="id"
        loading={isLoading}
        emptyMessage="No journal entries found"
        onRowClick={(item) => router.push(`/books/journal-entries/${(item as any).id}`)}
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
