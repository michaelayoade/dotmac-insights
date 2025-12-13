'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingDebitNotes, usePurchasingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  FileText,
  Calendar,
  DollarSign,
  Building2,
  CheckCircle2,
  Clock,
  XCircle,
  Filter,
  Search,
  Receipt,
  ArrowLeftRight,
} from 'lucide-react';

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

export default function PurchasingDebitNotesPage() {
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [supplierId, setSupplierId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const { data, isLoading, error } = usePurchasingDebitNotes({
    status: status || undefined,
    supplier: supplierId || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    search: search || undefined,
    currency,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { data: suppliersData } = usePurchasingSuppliers({ limit: 100, offset: 0 });

  const debitNotes = data?.debit_notes || [];
  const total = data?.total || 0;
  const summary = data?.summary || {};
  const suppliers = suppliersData?.suppliers || [];

  const getStatusConfig = (noteStatus: string) => {
    const statusLower = noteStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      draft: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: FileText,
        label: 'Draft',
      },
      open: {
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: FileText,
        label: 'Open',
      },
      applied: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Applied',
      },
      partially_applied: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Partial',
      },
      voided: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: XCircle,
        label: 'Voided',
      },
      closed: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: XCircle,
        label: 'Closed',
      },
    };
    return configs[statusLower] || configs.draft;
  };

  const columns = [
    {
      key: 'debit_note_number',
      header: 'Debit Note #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-white font-medium">
            {item.erpnext_id || `#${item.id}`}
          </span>
        </div>
      ),
    },
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-muted" />
          <span className="text-slate-300 truncate max-w-[180px]">
            {item.supplier || '-'}
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
      key: 'bill_reference',
      header: 'Bill Reference',
      render: (item: any) => (
        <span className="font-mono text-slate-muted text-sm">
          {item.bill_number || item.bill_reference || item.invoice_reference || '-'}
        </span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white font-medium">
          {formatCurrency(item.grand_total)}
        </span>
      ),
    },
    {
      key: 'applied_amount',
      header: 'Applied',
      align: 'right' as const,
      render: (item: any) => {
        const applied = item.applied_amount || item.amount_applied || 0;
        const total = item.total || item.amount || 0;
        const remaining = total - applied;
        return (
          <div className="text-right">
            <span className={cn('font-mono', applied > 0 ? 'text-green-400' : 'text-slate-muted')}>
              {formatCurrency(applied)}
            </span>
            {remaining > 0 && (
              <p className="text-xs text-orange-400">{formatCurrency(remaining)} remaining</p>
            )}
          </div>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const noteStatus = item.status || 'draft';
        const config = getStatusConfig(noteStatus);
        const StatusIcon = config.icon;
        return (
          <span
            className={cn(
              'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
              config.color
            )}
          >
            <StatusIcon className="w-3 h-3" />
            {config.label}
          </span>
        );
      },
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load debit notes</p>
        <p className="text-slate-muted text-sm mt-1">
          {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Debit Notes</h1>
          <p className="text-slate-muted text-sm">Track vendor credits and write-backs</p>
        </div>
        <button
          onClick={() => router.push('/purchasing/debit-notes/new')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Receipt className="w-4 h-4" />
          New Debit Note
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Receipt className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Debit Notes</p>
          </div>
          <p className="text-2xl font-bold text-white">{formatNumber(total)}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Value</p>
          </div>
          <p className="text-xl font-bold text-blue-400">
            {formatCurrency(summary.total_value || summary.total_amount || 0)}
          </p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <ArrowLeftRight className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Applied</p>
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatCurrency(summary.total_applied || summary.applied_amount || 0)}
          </p>
          <p className="text-xs text-green-400/70">
            {formatNumber(summary.applied_count)} notes
          </p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-orange-400" />
            <p className="text-orange-400 text-sm">Unapplied</p>
          </div>
          <p className="text-xl font-bold text-orange-400">
            {formatCurrency(summary.total_unapplied || summary.unapplied_amount || 0)}
          </p>
          <p className="text-xs text-orange-400/70">
            {formatNumber(summary.unapplied_count || summary.open_count)} open
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="w-4 h-4 text-slate-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search debit notes..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Status</option>
            <option value="draft">Draft</option>
            <option value="open">Open</option>
            <option value="applied">Applied</option>
            <option value="partially_applied">Partially Applied</option>
            <option value="voided">Voided</option>
          </select>
          {suppliers.length > 0 && (
            <select
              value={supplierId}
              onChange={(e) => {
                setSupplierId(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 max-w-[200px]"
            >
              <option value="">All Suppliers</option>
              {suppliers.map((supplier: any) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name || supplier.supplier_name}
                </option>
              ))}
            </select>
          )}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="End date"
            />
          </div>
          {(search || status || supplierId || startDate || endDate) && (
            <button
              onClick={() => {
                setSearch('');
                setStatus('');
                setSupplierId('');
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
        data={debitNotes}
        keyField="id"
        loading={isLoading}
        emptyMessage="No debit notes found"
        onRowClick={(item) => router.push(`/purchasing/debit-notes/${(item as any).id}`)}
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
