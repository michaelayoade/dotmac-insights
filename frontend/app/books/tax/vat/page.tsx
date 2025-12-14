'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useVATTransactions, useVATSummary, useTaxMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { formatCurrency } from '@/lib/utils';
import {
  Percent,
  Plus,
  ArrowLeft,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function getCurrentPeriod() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export default function VATPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [typeFilter, setTypeFilter] = useState('');
  const [period, setPeriod] = useState(getCurrentPeriod());
  const [showOutputForm, setShowOutputForm] = useState(false);
  const [showInputForm, setShowInputForm] = useState(false);

  const { data, isLoading, error } = useVATTransactions({
    period: period || undefined,
    type: typeFilter || undefined,
    page,
    page_size: pageSize,
  });
  const { data: summary } = useVATSummary(period);
  const { recordVATOutput, recordVATInput } = useTaxMutations();

  const columns = [
    {
      key: 'transaction_type',
      header: 'Type',
      render: (item: any) => (
        <span className={cn(
          'px-2 py-1 rounded text-xs font-medium',
          item.transaction_type === 'OUTPUT' ? 'bg-blue-500/20 text-blue-300' : 'bg-emerald-500/20 text-emerald-300'
        )}>
          {item.transaction_type}
        </span>
      ),
    },
    { key: 'party_name', header: 'Party', render: (item: any) => <span className="text-white">{item.party_name}</span> },
    { key: 'party_tin', header: 'TIN', render: (item: any) => <span className="text-slate-muted font-mono text-xs">{item.party_tin || '-'}</span> },
    {
      key: 'gross_amount',
      header: 'Gross',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-white">{formatCurrency(item.gross_amount, 'NGN')}</span>,
    },
    {
      key: 'vat_amount',
      header: 'VAT (7.5%)',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn('font-mono', item.transaction_type === 'OUTPUT' ? 'text-blue-300' : 'text-emerald-300')}>
          {formatCurrency(item.vat_amount, 'NGN')}
        </span>
      ),
    },
    { key: 'transaction_date', header: 'Date', render: (item: any) => <span className="text-slate-muted">{formatDate(item.transaction_date)}</span> },
    {
      key: 'is_exempt',
      header: 'Status',
      render: (item: any) => item.is_exempt ? (
        <span className="text-amber-400 text-xs">Exempt</span>
      ) : (
        <span className="text-slate-muted text-xs">Taxable</span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load VAT transactions</p>
      </div>
    );
  }

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
            <Percent className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-semibold text-white">Value Added Tax (VAT)</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowInputForm(!showInputForm)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <TrendingDown className="w-4 h-4 text-emerald-400" />
            Record Input
          </button>
          <button
            onClick={() => setShowOutputForm(!showOutputForm)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/20 text-blue-300 text-sm hover:bg-blue-500/30"
          >
            <TrendingUp className="w-4 h-4" />
            Record Output
          </button>
        </div>
      </div>

      {/* VAT Summary */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Output VAT</p>
            <p className="text-xl font-semibold text-blue-300 font-mono">{formatCurrency(summary.output_vat, 'NGN')}</p>
            <p className="text-xs text-slate-muted mt-1">{summary.output_count} transactions</p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Input VAT</p>
            <p className="text-xl font-semibold text-emerald-300 font-mono">{formatCurrency(summary.input_vat, 'NGN')}</p>
            <p className="text-xs text-slate-muted mt-1">{summary.input_count} transactions</p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Net VAT Payable</p>
            <p className={cn(
              'text-xl font-semibold font-mono',
              summary.net_vat >= 0 ? 'text-amber-300' : 'text-teal-electric'
            )}>
              {formatCurrency(summary.net_vat, 'NGN')}
            </p>
            <p className="text-xs text-slate-muted mt-1">{summary.net_vat >= 0 ? 'Due to FIRS' : 'Credit available'}</p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Exempt Amount</p>
            <p className="text-xl font-semibold text-slate-200 font-mono">{formatCurrency(summary.exempt_amount, 'NGN')}</p>
            <p className="text-xs text-slate-muted mt-1">Zero-rated/exempt</p>
          </div>
        </div>
      )}

      {/* Output VAT Form */}
      {showOutputForm && (
        <VATOutputForm
          onSubmit={async (data) => {
            await recordVATOutput(data);
            setShowOutputForm(false);
          }}
          onCancel={() => setShowOutputForm(false)}
        />
      )}

      {/* Input VAT Form */}
      {showInputForm && (
        <VATInputForm
          onSubmit={async (data) => {
            await recordVATInput(data);
            setShowInputForm(false);
          }}
          onCancel={() => setShowInputForm(false)}
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <input
          type="month"
          value={period}
          onChange={(e) => { setPeriod(e.target.value); setPage(1); }}
          className="input-field max-w-[180px]"
        />
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="input-field max-w-[150px]"
        >
          <option value="">All Types</option>
          <option value="OUTPUT">Output</option>
          <option value="INPUT">Input</option>
        </select>
      </div>

      {/* Transactions Table */}
      <DataTable
        columns={columns}
        data={data?.transactions || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No VAT transactions found"
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
        />
      )}
    </div>
  );
}

function VATOutputForm({ onSubmit, onCancel }: { onSubmit: (data: any) => Promise<void>; onCancel: () => void }) {
  const [form, setForm] = useState({
    party_name: '',
    party_tin: '',
    transaction_date: new Date().toISOString().slice(0, 10),
    gross_amount: '',
    description: '',
    is_exempt: false,
    exemption_reason: '',
  });
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        party_name: form.party_name,
        party_tin: form.party_tin || undefined,
        transaction_date: form.transaction_date,
        gross_amount: Number(form.gross_amount),
        description: form.description || undefined,
        is_exempt: form.is_exempt,
        exemption_reason: form.is_exempt ? form.exemption_reason : undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const vatAmount = form.is_exempt ? 0 : Number(form.gross_amount || 0) * 0.075;

  return (
    <form onSubmit={handleSubmit} className="bg-slate-card border border-blue-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-400" />
          Record Output VAT
        </h3>
        <button type="button" onClick={onCancel} className="text-slate-muted hover:text-white text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Customer Name *</label>
          <input
            type="text"
            value={form.party_name}
            onChange={(e) => setForm({ ...form, party_name: e.target.value })}
            className="input-field"
            required
          />
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
            <label className="block text-sm text-slate-muted">Customer TIN</label>
            <input
              type="text"
              value={form.party_tin}
              onChange={(e) => setForm({ ...form, party_tin: e.target.value })}
              className="input-field"
              placeholder="Tax Identification Number"
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Description</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="input-field"
            />
          </div>
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_exempt"
              checked={form.is_exempt}
              onChange={(e) => setForm({ ...form, is_exempt: e.target.checked })}
              className="rounded border-slate-border bg-slate-elevated"
            />
            <label htmlFor="is_exempt" className="text-sm text-slate-muted">VAT Exempt</label>
          </div>
          {form.is_exempt && (
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Exemption Reason</label>
              <input
                type="text"
                value={form.exemption_reason}
                onChange={(e) => setForm({ ...form, exemption_reason: e.target.value })}
                className="input-field"
              />
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-slate-border/50">
        <div className="text-sm">
          <span className="text-slate-muted">VAT Amount (7.5%): </span>
          <span className="text-blue-300 font-mono font-semibold">{formatCurrency(vatAmount, 'NGN')}</span>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-300 font-semibold hover:bg-blue-500/30 disabled:opacity-60"
        >
          {saving ? 'Recording...' : 'Record Output VAT'}
        </button>
      </div>
    </form>
  );
}

function VATInputForm({ onSubmit, onCancel }: { onSubmit: (data: any) => Promise<void>; onCancel: () => void }) {
  const [form, setForm] = useState({
    party_name: '',
    party_tin: '',
    transaction_date: new Date().toISOString().slice(0, 10),
    gross_amount: '',
    vat_amount: '',
    description: '',
  });
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        party_name: form.party_name,
        party_tin: form.party_tin || undefined,
        transaction_date: form.transaction_date,
        gross_amount: Number(form.gross_amount),
        vat_amount: Number(form.vat_amount),
        description: form.description || undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-slate-card border border-emerald-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-emerald-400" />
          Record Input VAT
        </h3>
        <button type="button" onClick={onCancel} className="text-slate-muted hover:text-white text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Supplier Name *</label>
          <input
            type="text"
            value={form.party_name}
            onChange={(e) => setForm({ ...form, party_name: e.target.value })}
            className="input-field"
            required
          />
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
          <label className="block text-sm text-slate-muted">VAT Amount *</label>
          <input
            type="number"
            value={form.vat_amount}
            onChange={(e) => setForm({ ...form, vat_amount: e.target.value })}
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
              value={form.party_tin}
              onChange={(e) => setForm({ ...form, party_tin: e.target.value })}
              className="input-field"
              placeholder="Required for VAT credit"
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Description</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="input-field"
            />
          </div>
        </div>
      )}

      <div className="flex justify-end pt-4 border-t border-slate-border/50">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 font-semibold hover:bg-emerald-500/30 disabled:opacity-60"
        >
          {saving ? 'Recording...' : 'Record Input VAT'}
        </button>
      </div>
    </form>
  );
}
