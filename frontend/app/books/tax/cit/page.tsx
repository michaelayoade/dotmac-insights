'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useCITAssessments, useTaxMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { formatCurrency } from '@/lib/utils';
import {
  Building2,
  Plus,
  ArrowLeft,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const CIT_RATES = [
  { size: 'SMALL', label: 'Small Company', rate: 0, turnoverMax: 25000000, description: 'Turnover < ₦25M' },
  { size: 'MEDIUM', label: 'Medium Company', rate: 20, turnoverMax: 100000000, description: 'Turnover ₦25M - ₦100M' },
  { size: 'LARGE', label: 'Large Company', rate: 30, turnoverMax: Infinity, description: 'Turnover > ₦100M' },
];

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function CITPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [year, setYear] = useState(new Date().getFullYear());
  const [showAssessmentForm, setShowAssessmentForm] = useState(false);

  const { data, isLoading, error } = useCITAssessments({
    year,
    page,
    page_size: pageSize,
  });
  const { createCITAssessment } = useTaxMutations();

  const columns = [
    {
      key: 'year',
      header: 'Year',
      render: (item: any) => <span className="text-foreground font-medium">{item.year}</span>,
    },
    {
      key: 'company_size',
      header: 'Company Size',
      render: (item: any) => {
        const sizeInfo = CIT_RATES.find(r => r.size === item.company_size);
        return (
          <span className={cn(
            'px-2 py-1 rounded text-xs font-medium',
            item.company_size === 'SMALL' ? 'bg-emerald-500/20 text-emerald-400' :
            item.company_size === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' :
            'bg-purple-500/20 text-purple-400'
          )}>
            {sizeInfo?.label || item.company_size}
          </span>
        );
      },
    },
    {
      key: 'turnover',
      header: 'Turnover',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.turnover, 'NGN')}</span>,
    },
    {
      key: 'profit_before_tax',
      header: 'Profit Before Tax',
      align: 'right' as const,
      render: (item: any) => (
        <span className={cn('font-mono', item.profit_before_tax >= 0 ? 'text-emerald-400' : 'text-red-400')}>
          {formatCurrency(item.profit_before_tax, 'NGN')}
        </span>
      ),
    },
    {
      key: 'taxable_profit',
      header: 'Taxable Profit',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.taxable_profit, 'NGN')}</span>,
    },
    {
      key: 'cit_rate',
      header: 'Rate',
      render: (item: any) => <span className="text-slate-muted">{item.cit_rate}%</span>,
    },
    {
      key: 'cit_liability',
      header: 'CIT Liability',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-purple-300 font-semibold">{formatCurrency(item.cit_liability, 'NGN')}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => (
        <span className={cn(
          'text-xs',
          item.status === 'FILED' ? 'text-emerald-400' :
          item.status === 'DRAFT' ? 'text-slate-muted' :
          'text-amber-400'
        )}>
          {item.status}
        </span>
      ),
    },
  ];

  // Get latest assessment for summary
  const latestAssessment = data?.assessments?.[0];
  const latestProfitBeforeTax = latestAssessment?.profit_before_tax ?? 0;
  const latestCitLiability = latestAssessment?.cit_liability ?? 0;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load CIT assessments</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/tax"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Tax
          </Link>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-purple-400" />
            <h1 className="text-xl font-semibold text-foreground">Company Income Tax (CIT)</h1>
          </div>
        </div>
        <button
          onClick={() => setShowAssessmentForm(!showAssessmentForm)}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-sm hover:bg-purple-500/30"
        >
          <Plus className="w-4 h-4" />
          New Assessment
        </button>
      </div>

      {/* Summary Cards */}
      {latestAssessment && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-slate-muted" />
              <p className="text-slate-muted text-sm">Turnover ({latestAssessment.year})</p>
            </div>
            <p className="text-xl font-semibold text-foreground font-mono">
              {formatCurrency(latestAssessment.turnover, 'NGN')}
            </p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              {latestProfitBeforeTax >= 0 ? (
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-400" />
              )}
              <p className="text-slate-muted text-sm">Profit Before Tax</p>
            </div>
            <p className={cn(
              'text-xl font-semibold font-mono',
              latestProfitBeforeTax >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}>
              {formatCurrency(latestProfitBeforeTax, 'NGN')}
            </p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">Company Size</p>
            <p className="text-xl font-semibold text-foreground mt-1">
              {CIT_RATES.find(r => r.size === latestAssessment.company_size)?.label || latestAssessment.company_size}
            </p>
            <p className="text-xs text-slate-muted mt-1">Rate: {latestAssessment.cit_rate}%</p>
          </div>
          <div className="bg-slate-card border border-purple-500/30 rounded-xl p-4">
            <p className="text-slate-muted text-sm">CIT Liability</p>
            <p className="text-2xl font-semibold text-purple-400 font-mono mt-1">
              {formatCurrency(latestCitLiability, 'NGN')}
            </p>
          </div>
        </div>
      )}

      {/* Assessment Form */}
      {showAssessmentForm && (
        <CITAssessmentForm
          onSubmit={async (data) => {
            await createCITAssessment(data);
            setShowAssessmentForm(false);
          }}
          onCancel={() => setShowAssessmentForm(false)}
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <select
          value={year}
          onChange={(e) => { setYear(Number(e.target.value)); setPage(1); }}
          className="input-field max-w-[150px]"
        >
          {[...Array(5)].map((_, i) => {
            const y = new Date().getFullYear() - i;
            return <option key={y} value={y}>{y}</option>;
          })}
        </select>
      </div>

      {/* Assessments Table */}
      <DataTable
        columns={columns}
        data={data?.assessments || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No CIT assessments found"
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
        />
      )}

      {/* CIT Rate Guide */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-foreground font-semibold mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-teal-electric" />
          Nigerian CIT Rate Guide
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {CIT_RATES.map((rate) => (
            <div
              key={rate.size}
              className={cn(
                'rounded-lg p-4 border',
                rate.size === 'SMALL' ? 'bg-emerald-500/10 border-emerald-500/30' :
                rate.size === 'MEDIUM' ? 'bg-amber-500/10 border-amber-500/30' :
                'bg-purple-500/10 border-purple-500/30'
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-foreground font-medium">{rate.label}</span>
                <span className={cn(
                  'text-xl font-mono font-semibold',
                  rate.size === 'SMALL' ? 'text-emerald-400' :
                  rate.size === 'MEDIUM' ? 'text-amber-400' :
                  'text-purple-400'
                )}>
                  {rate.rate}%
                </span>
              </div>
              <p className="text-sm text-slate-muted">{rate.description}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-slate-muted space-y-1">
          <p>* CIT is payable on taxable profits, not turnover</p>
          <p>* Companies must file annual returns within 6 months of year-end</p>
          <p>* Tertiary Education Tax (TET) of 2.5% applies to assessable profits</p>
          <p>* Minimum tax of 0.5% of turnover applies if CIT is less</p>
        </div>
      </div>
    </div>
  );
}

function CITAssessmentForm({ onSubmit, onCancel }: { onSubmit: (data: any) => Promise<void>; onCancel: () => void }) {
  const [form, setForm] = useState({
    year: new Date().getFullYear(),
    turnover: '',
    profit_before_tax: '',
    capital_allowances: '',
    disallowable_expenses: '',
    loss_brought_forward: '',
  });
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        year: form.year,
        turnover: Number(form.turnover),
        profit_before_tax: Number(form.profit_before_tax),
        capital_allowances: form.capital_allowances ? Number(form.capital_allowances) : undefined,
        disallowable_expenses: form.disallowable_expenses ? Number(form.disallowable_expenses) : undefined,
        loss_brought_forward: form.loss_brought_forward ? Number(form.loss_brought_forward) : undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  // Determine company size based on turnover
  const turnover = Number(form.turnover || 0);
  const profitBeforeTax = Number(form.profit_before_tax || 0);
  const capitalAllowances = Number(form.capital_allowances || 0);
  const disallowable = Number(form.disallowable_expenses || 0);
  const lossForward = Number(form.loss_brought_forward || 0);

  let companySize = 'SMALL';
  let citRate = 0;
  if (turnover > 100000000) {
    companySize = 'LARGE';
    citRate = 30;
  } else if (turnover > 25000000) {
    companySize = 'MEDIUM';
    citRate = 20;
  }

  const taxableProfit = Math.max(0, profitBeforeTax - capitalAllowances + disallowable - lossForward);
  const citLiability = taxableProfit * (citRate / 100);
  const minimumTax = turnover * 0.005; // 0.5% of turnover
  const finalCIT = Math.max(citLiability, minimumTax);

  return (
    <form onSubmit={handleSubmit} className="bg-slate-card border border-purple-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-foreground font-semibold flex items-center gap-2">
          <Plus className="w-4 h-4 text-purple-400" />
          New CIT Assessment
        </h3>
        <button type="button" onClick={onCancel} className="text-slate-muted hover:text-foreground text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Assessment Year *</label>
          <select
            value={form.year}
            onChange={(e) => setForm({ ...form, year: Number(e.target.value) })}
            className="input-field"
          >
            {[...Array(5)].map((_, i) => {
              const y = new Date().getFullYear() - i;
              return <option key={y} value={y}>{y}</option>;
            })}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Turnover *</label>
          <input
            type="number"
            value={form.turnover}
            onChange={(e) => setForm({ ...form, turnover: e.target.value })}
            className="input-field"
            required
            min={0}
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Profit Before Tax *</label>
          <input
            type="number"
            value={form.profit_before_tax}
            onChange={(e) => setForm({ ...form, profit_before_tax: e.target.value })}
            className="input-field"
            required
          />
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowMore(!showMore)}
        className="flex items-center gap-2 text-sm text-slate-muted hover:text-foreground"
      >
        {showMore ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Adjustments
      </button>

      {showMore && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-slate-border/50">
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Capital Allowances</label>
            <input
              type="number"
              value={form.capital_allowances}
              onChange={(e) => setForm({ ...form, capital_allowances: e.target.value })}
              className="input-field"
              placeholder="Deductible"
              min={0}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Disallowable Expenses</label>
            <input
              type="number"
              value={form.disallowable_expenses}
              onChange={(e) => setForm({ ...form, disallowable_expenses: e.target.value })}
              className="input-field"
              placeholder="Added back"
              min={0}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Loss Brought Forward</label>
            <input
              type="number"
              value={form.loss_brought_forward}
              onChange={(e) => setForm({ ...form, loss_brought_forward: e.target.value })}
              className="input-field"
              placeholder="Prior year losses"
              min={0}
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-slate-border/50">
        <div className="text-sm space-y-1">
          <div>
            <span className="text-slate-muted">Company Size: </span>
            <span className={cn(
              'font-medium',
              companySize === 'SMALL' ? 'text-emerald-400' :
              companySize === 'MEDIUM' ? 'text-amber-400' :
              'text-purple-400'
            )}>
              {CIT_RATES.find(r => r.size === companySize)?.label} ({citRate}%)
            </span>
          </div>
          <div>
            <span className="text-slate-muted">Taxable Profit: </span>
            <span className="text-foreground font-mono">{formatCurrency(taxableProfit, 'NGN')}</span>
          </div>
          <div>
            <span className="text-slate-muted">CIT Liability: </span>
            <span className="text-purple-300 font-mono font-semibold">{formatCurrency(citLiability, 'NGN')}</span>
            {citLiability < minimumTax && (
              <span className="text-xs text-amber-400 ml-2">(Min tax: {formatCurrency(minimumTax, 'NGN')})</span>
            )}
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 font-semibold hover:bg-purple-500/30 disabled:opacity-60"
        >
          {saving ? 'Saving...' : 'Save Assessment'}
        </button>
      </div>
    </form>
  );
}
