'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useTaxMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { formatCurrency } from '@/lib/utils';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import {
  FileCheck,
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  FileText,
  RefreshCw,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import useSWR from 'swr';
import { api } from '@/lib/api';

// Local hook for e-invoices (may need to add to useApi.ts)
function useEInvoices(params?: { status?: string; page?: number; page_size?: number }) {
  const queryString = params ? new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
  ).toString() : '';
  return useSWR(
    ['einvoices', queryString],
    () => api.getEInvoices(params)
  );
}

const STATUS_CONFIG: Record<string, { bg: string; text: string; icon: any }> = {
  DRAFT: { bg: 'bg-slate-border/30', text: 'text-slate-muted', icon: FileText },
  PENDING: { bg: 'bg-amber-500/10', text: 'text-amber-400', icon: Clock },
  SUBMITTED: { bg: 'bg-blue-500/10', text: 'text-blue-400', icon: Send },
  VALIDATED: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', icon: CheckCircle2 },
  REJECTED: { bg: 'bg-red-500/10', text: 'text-red-400', icon: XCircle },
  CANCELLED: { bg: 'bg-slate-border/30', text: 'text-slate-muted', icon: XCircle },
};

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function EInvoicePage() {
  const [filters, setFilters] = usePersistentState<{
    page: number;
    pageSize: number;
    statusFilter: string;
    search: string;
  }>('books.tax.einvoice.filters', {
    page: 1,
    pageSize: 20,
    statusFilter: '',
    search: '',
  });
  const { page, pageSize, statusFilter, search } = filters;
  const [selectedInvoice, setSelectedInvoice] = useState<string | null>(null);

  const { data, isLoading, error, mutate } = useEInvoices({
    status: statusFilter || undefined,
    page,
    page_size: pageSize,
  });
  const { createEInvoice, validateEInvoice } = useTaxMutations();

  const handleValidate = async (invoiceId: string) => {
    try {
      await validateEInvoice(invoiceId);
      mutate();
    } catch (err) {
      console.error('Validation failed:', err);
    }
  };

  const columns = [
    {
      key: 'invoice_number',
      header: 'Invoice #',
      render: (item: any) => (
        <span className="text-white font-medium font-mono">{item.invoice_number}</span>
      ),
    },
    {
      key: 'firs_reference',
      header: 'FIRS Reference',
      render: (item: any) => (
        <span className="text-slate-muted font-mono text-xs">
          {item.firs_reference || '-'}
        </span>
      ),
    },
    {
      key: 'customer_name',
      header: 'Customer',
      render: (item: any) => <span className="text-white">{item.customer_name}</span>,
    },
    {
      key: 'customer_tin',
      header: 'Customer TIN',
      render: (item: any) => (
        <span className={cn('font-mono text-xs', item.customer_tin ? 'text-slate-muted' : 'text-amber-400')}>
          {item.customer_tin || 'No TIN'}
        </span>
      ),
    },
    {
      key: 'total',
      header: 'Total',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white">{formatCurrency(item.total, item.currency || 'NGN')}</span>
      ),
    },
    {
      key: 'vat_amount',
      header: 'VAT',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-blue-400">{formatCurrency(item.vat_amount, item.currency || 'NGN')}</span>
      ),
    },
    {
      key: 'invoice_date',
      header: 'Date',
      render: (item: any) => <span className="text-slate-muted">{formatDate(item.invoice_date)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.DRAFT;
        const Icon = config.icon;
        return (
          <span className={cn('inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium', config.bg, config.text)}>
            <Icon className="w-3 h-3" />
            {item.status}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          {(item.status === 'DRAFT' || item.status === 'PENDING') && (
            <button
              onClick={() => handleValidate(item.id)}
              className="p-1.5 rounded hover:bg-slate-border/30 text-blue-400 hover:text-blue-300"
              title="Submit to FIRS"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
          {item.status === 'REJECTED' && (
            <button
              onClick={() => handleValidate(item.id)}
              className="p-1.5 rounded hover:bg-slate-border/30 text-amber-400 hover:text-amber-300"
              title="Resubmit"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          )}
          {item.firs_reference && (
            <span
              className="p-1.5 rounded text-emerald-400"
              title={`FIRS Ref: ${item.firs_reference}`}
            >
              <CheckCircle2 className="w-4 h-4" />
            </span>
          )}
        </div>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load e-invoices."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  // Calculate stats
  const stats = {
    total: data?.total || 0,
    validated: data?.einvoices?.filter((e: any) => e.status === 'VALIDATED').length || 0,
    pending: data?.einvoices?.filter((e: any) => ['DRAFT', 'PENDING', 'SUBMITTED'].includes(e.status)).length || 0,
    rejected: data?.einvoices?.filter((e: any) => e.status === 'REJECTED').length || 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/tax"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Tax
          </Link>
          <div className="flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-white">E-Invoice (FIRS BIS 3.0)</h1>
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <FileCheck className="w-5 h-5 text-blue-400 mt-0.5" />
          <div>
            <h3 className="text-blue-400 font-semibold">FIRS Basic Invoice System (BIS 3.0)</h3>
            <p className="text-slate-muted text-sm mt-1">
              E-invoices are automatically generated from your sales invoices. Submit them to FIRS to get
              an Invoice Reference Number (IRN) for tax compliance. Validated invoices can be verified on
              the FIRS portal.
            </p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total E-Invoices</p>
          <p className="text-2xl font-semibold text-white font-mono mt-1">{stats.total}</p>
        </div>
        <div className="bg-slate-card border border-emerald-500/30 rounded-xl p-4">
          <p className="text-slate-muted text-sm">Validated</p>
          <p className="text-2xl font-semibold text-emerald-400 font-mono mt-1">{stats.validated}</p>
        </div>
        <div className="bg-slate-card border border-amber-500/30 rounded-xl p-4">
          <p className="text-slate-muted text-sm">Pending Submission</p>
          <p className="text-2xl font-semibold text-amber-400 font-mono mt-1">{stats.pending}</p>
        </div>
        <div className="bg-slate-card border border-red-500/30 rounded-xl p-4">
          <p className="text-slate-muted text-sm">Rejected</p>
          <p className="text-2xl font-semibold text-red-400 font-mono mt-1">{stats.rejected}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search invoices..."
            value={search}
            onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
            className="input-field pl-9 max-w-[220px]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setFilters((prev) => ({ ...prev, statusFilter: e.target.value, page: 1 }))}
          className="input-field max-w-[160px]"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="PENDING">Pending</option>
          <option value="SUBMITTED">Submitted</option>
          <option value="VALIDATED">Validated</option>
          <option value="REJECTED">Rejected</option>
        </select>
        {(search || statusFilter) && (
          <button
            onClick={() => setFilters((prev) => ({ ...prev, search: '', statusFilter: '', page: 1 }))}
            className="text-slate-muted text-sm hover:text-white transition-colors"
          >
            Reset
          </button>
        )}
      </div>

      {/* E-Invoices Table */}
      <DataTable
        columns={columns}
        data={data?.einvoices || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No e-invoices found"
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setFilters((prev) => ({ ...prev, page: Math.floor(newOffset / pageSize) + 1 }))}
        />
      )}

      {/* E-Invoice Requirements */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-teal-electric" />
          E-Invoice Requirements
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h4 className="text-white text-sm font-medium mb-2">Required Fields</h4>
            <ul className="text-sm text-slate-muted space-y-1">
              <li>• Seller TIN (your company)</li>
              <li>• Buyer TIN (if registered taxpayer)</li>
              <li>• Invoice number and date</li>
              <li>• Line items with description and amount</li>
              <li>• VAT amount (7.5% standard rate)</li>
              <li>• Total amount</li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-medium mb-2">Status Flow</h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="w-20 text-slate-muted">Draft</span>
                <span className="text-slate-muted">→</span>
                <span className="text-slate-muted">Invoice created, not submitted</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="w-20 text-amber-400">Pending</span>
                <span className="text-slate-muted">→</span>
                <span className="text-slate-muted">Queued for submission</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="w-20 text-blue-400">Submitted</span>
                <span className="text-slate-muted">→</span>
                <span className="text-slate-muted">Sent to FIRS, awaiting validation</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="w-20 text-emerald-400">Validated</span>
                <span className="text-slate-muted">→</span>
                <span className="text-slate-muted">IRN assigned, tax compliant</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="w-20 text-red-400">Rejected</span>
                <span className="text-slate-muted">→</span>
                <span className="text-slate-muted">Validation failed, needs correction</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
