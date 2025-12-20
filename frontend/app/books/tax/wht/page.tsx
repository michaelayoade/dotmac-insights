'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useWHTTransactions, useWHTRemittanceDue, useTaxMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { formatCurrency } from '@/lib/utils';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import {
  Receipt,
  Plus,
  ArrowLeft,
  FileText,
  ChevronDown,
  ChevronRight,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const WHT_PAYMENT_TYPES = [
  { value: 'DIVIDEND', label: 'Dividend', rate: 10 },
  { value: 'INTEREST', label: 'Interest', rate: 10 },
  { value: 'RENT', label: 'Rent', rate: 10 },
  { value: 'ROYALTY', label: 'Royalty', rate: 10 },
  { value: 'PROFESSIONAL', label: 'Professional Services', rate: 10 },
  { value: 'CONTRACT', label: 'Contract', rate: 5 },
  { value: 'DIRECTOR_FEE', label: 'Director Fee', rate: 10 },
  { value: 'COMMISSION', label: 'Commission', rate: 10 },
  { value: 'OTHER', label: 'Other', rate: 5 },
];

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function WHTPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [period, setPeriod] = useState('');
  const [showDeductForm, setShowDeductForm] = useState(false);

  const { data, isLoading, error, mutate } = useWHTTransactions({
    period: period || undefined,
    page,
    page_size: pageSize,
  });
  const { data: remittanceDue } = useWHTRemittanceDue();
  const { deductWHT, generateWHTCertificate } = useTaxMutations();

  const columns = [
    {
      key: 'payment_type',
      header: 'Type',
      render: (item: any) => (
        <span className="text-slate-200 text-sm">
          {WHT_PAYMENT_TYPES.find(t => t.value === item.payment_type)?.label || item.payment_type}
        </span>
      ),
    },
    { key: 'supplier_name', header: 'Supplier', render: (item: any) => <span className="text-white">{item.supplier_name}</span> },
    {
      key: 'supplier_tin',
      header: 'TIN',
      render: (item: any) => (
        <span className={cn('font-mono text-xs', item.has_tin ? 'text-slate-muted' : 'text-amber-400')}>
          {item.supplier_tin || 'No TIN (2x penalty)'}
        </span>
      ),
    },
    {
      key: 'gross_amount',
      header: 'Gross',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.gross_amount, 'NGN')}</span>,
    },
    {
      key: 'wht_rate',
      header: 'Rate',
      render: (item: any) => (
        <span className={cn('text-sm', item.penalty_rate > 0 ? 'text-amber-400' : 'text-slate-muted')}>
          {item.wht_rate}%{item.penalty_rate > 0 ? ` (${item.penalty_rate}% penalty)` : ''}
        </span>
      ),
    },
    {
      key: 'wht_amount',
      header: 'WHT Deducted',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-amber-300">{formatCurrency(item.wht_amount, 'NGN')}</span>,
    },
    { key: 'transaction_date', header: 'Date', render: (item: any) => <span className="text-slate-muted">{formatDate(item.transaction_date)}</span> },
    {
      key: 'is_remitted',
      header: 'Remitted',
      render: (item: any) => item.is_remitted ? (
        <span className="text-emerald-400 text-xs">Yes</span>
      ) : (
        <span className="text-amber-400 text-xs">Pending</span>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load WHT transactions."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
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
            <Receipt className="w-5 h-5 text-amber-400" />
            <h1 className="text-xl font-semibold text-white">Withholding Tax (WHT)</h1>
          </div>
        </div>
        <button
          onClick={() => setShowDeductForm(!showDeductForm)}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/20 text-amber-300 text-sm hover:bg-amber-500/30"
        >
          <Plus className="w-4 h-4" />
          Deduct WHT
        </button>
      </div>

      {/* Remittance Due Alert */}
      {remittanceDue && (
        <div className={cn(
          'rounded-xl p-4 border',
          remittanceDue.is_overdue ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30'
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className={cn('w-5 h-5', remittanceDue.is_overdue ? 'text-red-400' : 'text-amber-400')} />
              <div>
                <h3 className={cn('font-semibold', remittanceDue.is_overdue ? 'text-red-400' : 'text-amber-400')}>
                  WHT Remittance {remittanceDue.is_overdue ? 'Overdue' : 'Due'}
                </h3>
                <p className="text-slate-muted text-sm">
                  {remittanceDue.transaction_count} transactions for {remittanceDue.period}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xl font-semibold text-white font-mono">{formatCurrency(remittanceDue.total_deducted, 'NGN')}</p>
              <p className="text-sm text-slate-muted">
                Due: {formatDate(remittanceDue.deadline)}
                {remittanceDue.is_overdue && (
                  <span className="text-red-400 ml-2">({Math.abs(remittanceDue.days_until_due)} days overdue)</span>
                )}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* WHT Deduct Form */}
      {showDeductForm && (
        <WHTDeductForm
          onSubmit={async (data) => {
            await deductWHT(data);
            setShowDeductForm(false);
          }}
          onCancel={() => setShowDeductForm(false)}
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <input
          type="month"
          value={period}
          onChange={(e) => { setPeriod(e.target.value); setPage(1); }}
          className="input-field max-w-[180px]"
          placeholder="Filter by period"
        />
      </div>

      {/* Transactions Table */}
      <DataTable
        columns={columns}
        data={data?.transactions || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No WHT transactions found"
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
        />
      )}

      {/* WHT Rate Guide */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-teal-electric" />
          WHT Rate Guide
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {WHT_PAYMENT_TYPES.map((type) => (
            <div key={type.value} className="bg-slate-elevated rounded-lg p-2 text-sm">
              <span className="text-slate-muted">{type.label}</span>
              <span className="float-right text-amber-300 font-mono">{type.rate}%</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-muted mt-3">
          Note: Suppliers without TIN incur 2x the standard rate as penalty
        </p>
      </div>
    </div>
  );
}

function WHTDeductForm({ onSubmit, onCancel }: { onSubmit: (data: any) => Promise<void>; onCancel: () => void }) {
  const [form, setForm] = useState({
    supplier_name: '',
    supplier_tin: '',
    payment_type: 'CONTRACT',
    gross_amount: '',
    transaction_date: new Date().toISOString().slice(0, 10),
    invoice_reference: '',
  });
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        supplier_name: form.supplier_name,
        supplier_tin: form.supplier_tin || undefined,
        payment_type: form.payment_type,
        gross_amount: Number(form.gross_amount),
        transaction_date: form.transaction_date,
        invoice_reference: form.invoice_reference || undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const selectedType = WHT_PAYMENT_TYPES.find(t => t.value === form.payment_type);
  const hasTIN = !!form.supplier_tin;
  const effectiveRate = hasTIN ? (selectedType?.rate || 5) : (selectedType?.rate || 5) * 2;
  const whtAmount = Number(form.gross_amount || 0) * (effectiveRate / 100);

  return (
    <form onSubmit={handleSubmit} className="bg-slate-card border border-amber-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Plus className="w-4 h-4 text-amber-400" />
          Deduct Withholding Tax
        </h3>
        <button type="button" onClick={onCancel} className="text-slate-muted hover:text-white text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Supplier Name *</label>
          <input
            type="text"
            value={form.supplier_name}
            onChange={(e) => setForm({ ...form, supplier_name: e.target.value })}
            className="input-field"
            required
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Payment Type *</label>
          <select
            value={form.payment_type}
            onChange={(e) => setForm({ ...form, payment_type: e.target.value })}
            className="input-field"
          >
            {WHT_PAYMENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>{type.label} ({type.rate}%)</option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Gross Amount *</label>
          <input
            type="number"
            value={form.gross_amount}
            onChange={(e) => setForm({ ...form, gross_amount: e.target.value })}
            className="input-field"
            required
            min={0}
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Transaction Date *</label>
          <input
            type="date"
            value={form.transaction_date}
            onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
            className="input-field"
            required
          />
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowMore(!showMore)}
        className="flex items-center gap-2 text-sm text-slate-muted hover:text-white"
      >
        {showMore ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        More options
      </button>

      {showMore && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-border/50">
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Supplier TIN</label>
            <input
              type="text"
              value={form.supplier_tin}
              onChange={(e) => setForm({ ...form, supplier_tin: e.target.value })}
              className="input-field"
              placeholder="Avoids 2x penalty rate"
            />
            {!hasTIN && form.gross_amount && (
              <p className="text-xs text-amber-400">No TIN = 2x penalty rate ({effectiveRate}% instead of {selectedType?.rate}%)</p>
            )}
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Invoice Reference</label>
            <input
              type="text"
              value={form.invoice_reference}
              onChange={(e) => setForm({ ...form, invoice_reference: e.target.value })}
              className="input-field"
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-slate-border/50">
        <div className="text-sm space-y-1">
          <div>
            <span className="text-slate-muted">WHT Rate: </span>
            <span className={cn('font-mono', !hasTIN && form.gross_amount ? 'text-amber-400' : 'text-white')}>
              {effectiveRate}%
            </span>
          </div>
          <div>
            <span className="text-slate-muted">WHT Amount: </span>
            <span className="text-amber-300 font-mono font-semibold">{formatCurrency(whtAmount, 'NGN')}</span>
          </div>
          <div>
            <span className="text-slate-muted">Net Payment: </span>
            <span className="text-white font-mono">{formatCurrency(Number(form.gross_amount || 0) - whtAmount, 'NGN')}</span>
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-amber-500/20 text-amber-300 font-semibold hover:bg-amber-500/30 disabled:opacity-60"
        >
          {saving ? 'Recording...' : 'Deduct WHT'}
        </button>
      </div>
    </form>
  );
}
