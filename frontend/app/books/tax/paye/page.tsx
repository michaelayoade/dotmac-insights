'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePAYECalculations, useTaxMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { formatCurrency } from '@/lib/utils';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import {
  Users,
  Plus,
  ArrowLeft,
  FileText,
  ChevronDown,
  ChevronRight,
  Calculator,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const PAYE_TAX_BANDS = [
  { min: 0, max: 300000, rate: 7 },
  { min: 300000, max: 600000, rate: 11 },
  { min: 600000, max: 1100000, rate: 15 },
  { min: 1100000, max: 1600000, rate: 19 },
  { min: 1600000, max: 3200000, rate: 21 },
  { min: 3200000, max: Infinity, rate: 24 },
];

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function PAYEPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [period, setPeriod] = useState('');
  const [showCalculator, setShowCalculator] = useState(false);

  const { data, isLoading, error, mutate } = usePAYECalculations({
    period: period || undefined,
    page,
    page_size: pageSize,
  });
  const { calculatePAYE } = useTaxMutations();

  const columns = [
    {
      key: 'employee_name',
      header: 'Employee',
      render: (item: any) => <span className="text-foreground font-medium">{item.employee_name}</span>,
    },
    {
      key: 'gross_income',
      header: 'Gross Income',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.gross_income, 'NGN')}</span>,
    },
    {
      key: 'tax_free_allowance',
      header: 'Allowances',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-slate-muted">{formatCurrency(item.tax_free_allowance, 'NGN')}</span>,
    },
    {
      key: 'taxable_income',
      header: 'Taxable Income',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.taxable_income, 'NGN')}</span>,
    },
    {
      key: 'paye_amount',
      header: 'PAYE',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-emerald-300 font-semibold">{formatCurrency(item.paye_amount, 'NGN')}</span>,
    },
    {
      key: 'effective_rate',
      header: 'Effective Rate',
      render: (item: any) => (
        <span className="text-slate-muted text-sm">
          {((item.paye_amount / item.gross_income) * 100).toFixed(1)}%
        </span>
      ),
    },
    {
      key: 'period',
      header: 'Period',
      render: (item: any) => <span className="text-slate-muted">{item.period}</span>,
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  // Calculate summary stats
  const totalPAYE = data?.calculations?.reduce((sum: number, c: any) => sum + c.paye_amount, 0) || 0;
  const employeeCount = data?.calculations?.length || 0;

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load PAYE calculations."
          error={error as Error}
          onRetry={() => mutate()}
        />
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
            <Users className="w-5 h-5 text-emerald-400" />
            <h1 className="text-xl font-semibold text-foreground">PAYE (Pay As You Earn)</h1>
          </div>
        </div>
        <button
          onClick={() => setShowCalculator(!showCalculator)}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 text-sm hover:bg-emerald-500/30"
        >
          <Calculator className="w-4 h-4" />
          Calculate PAYE
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total PAYE (This Period)</p>
          <p className="text-2xl font-semibold text-emerald-400 font-mono mt-1">
            {formatCurrency(totalPAYE, 'NGN')}
          </p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Employees</p>
          <p className="text-2xl font-semibold text-foreground font-mono mt-1">{employeeCount}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Avg PAYE per Employee</p>
          <p className="text-2xl font-semibold text-foreground font-mono mt-1">
            {employeeCount > 0 ? formatCurrency(totalPAYE / employeeCount, 'NGN') : '-'}
          </p>
        </div>
      </div>

      {/* PAYE Calculator Form */}
      {showCalculator && (
        <PAYECalculatorForm
          onSubmit={async (data) => {
            await calculatePAYE(data);
            setShowCalculator(false);
          }}
          onCancel={() => setShowCalculator(false)}
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

      {/* Calculations Table */}
      <DataTable
        columns={columns}
        data={data?.calculations || []}
        keyField="id"
        loading={isLoading}
        emptyMessage="No PAYE calculations found"
      />

      {data && data.total > pageSize && (
        <Pagination
          total={data.total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
        />
      )}

      {/* PAYE Tax Bands Guide */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-foreground font-semibold mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-teal-electric" />
          Nigerian PAYE Tax Bands (Annual)
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {PAYE_TAX_BANDS.map((band, idx) => (
            <div key={idx} className="bg-slate-elevated rounded-lg p-3 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-muted">
                  {band.max === Infinity
                    ? `Above ${formatCurrency(band.min, 'NGN')}`
                    : `${formatCurrency(band.min, 'NGN')} - ${formatCurrency(band.max, 'NGN')}`}
                </span>
                <span className="text-emerald-300 font-mono font-semibold">{band.rate}%</span>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 text-xs text-slate-muted space-y-1">
          <p>* First ₦200,000 of gross income is tax-exempt (Consolidated Relief Allowance)</p>
          <p>* Additional 20% of gross income is also exempt (CRA)</p>
          <p>* Pension contributions (up to 8%) and NHF (2.5%) are deductible</p>
        </div>
      </div>
    </div>
  );
}

function PAYECalculatorForm({ onSubmit, onCancel }: { onSubmit: (data: any) => Promise<void>; onCancel: () => void }) {
  const [form, setForm] = useState({
    employee_name: '',
    employee_id: '',
    gross_income: '',
    pension_contribution: '',
    nhf_contribution: '',
    other_deductions: '',
    period: new Date().toISOString().slice(0, 7),
  });
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        employee_name: form.employee_name,
        employee_id: form.employee_id || undefined,
        gross_income: Number(form.gross_income),
        pension_contribution: form.pension_contribution ? Number(form.pension_contribution) : undefined,
        nhf_contribution: form.nhf_contribution ? Number(form.nhf_contribution) : undefined,
        other_deductions: form.other_deductions ? Number(form.other_deductions) : undefined,
        period: form.period,
      });
    } finally {
      setSaving(false);
    }
  };

  // Calculate preview
  const grossIncome = Number(form.gross_income || 0);
  const pension = Number(form.pension_contribution || 0);
  const nhf = Number(form.nhf_contribution || 0);
  const otherDeductions = Number(form.other_deductions || 0);

  // CRA: 200,000 or 1% of gross + 20% of gross
  const cra = Math.max(200000, grossIncome * 0.01) + (grossIncome * 0.2);
  const taxableIncome = Math.max(0, grossIncome - cra - pension - nhf - otherDeductions);

  // Calculate PAYE using progressive bands
  let paye = 0;
  let remaining = taxableIncome;
  for (const band of PAYE_TAX_BANDS) {
    const bandWidth = band.max === Infinity ? remaining : Math.min(band.max - band.min, remaining);
    if (bandWidth > 0) {
      paye += bandWidth * (band.rate / 100);
      remaining -= bandWidth;
    }
    if (remaining <= 0) break;
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-card border border-emerald-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-foreground font-semibold flex items-center gap-2">
          <Calculator className="w-4 h-4 text-emerald-400" />
          Calculate Employee PAYE
        </h3>
        <button type="button" onClick={onCancel} className="text-slate-muted hover:text-foreground text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Employee Name *</label>
          <input
            type="text"
            value={form.employee_name}
            onChange={(e) => setForm({ ...form, employee_name: e.target.value })}
            className="input-field"
            required
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Annual Gross Income *</label>
          <input
            type="number"
            value={form.gross_income}
            onChange={(e) => setForm({ ...form, gross_income: e.target.value })}
            className="input-field"
            required
            min={0}
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm text-slate-muted">Period *</label>
          <input
            type="month"
            value={form.period}
            onChange={(e) => setForm({ ...form, period: e.target.value })}
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
        Deductions & allowances
      </button>

      {showMore && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2 border-t border-slate-border/50">
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Employee ID</label>
            <input
              type="text"
              value={form.employee_id}
              onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
              className="input-field"
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Pension (Annual)</label>
            <input
              type="number"
              value={form.pension_contribution}
              onChange={(e) => setForm({ ...form, pension_contribution: e.target.value })}
              className="input-field"
              placeholder="Up to 8% of gross"
              min={0}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">NHF (Annual)</label>
            <input
              type="number"
              value={form.nhf_contribution}
              onChange={(e) => setForm({ ...form, nhf_contribution: e.target.value })}
              className="input-field"
              placeholder="2.5% of basic"
              min={0}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Other Deductions</label>
            <input
              type="number"
              value={form.other_deductions}
              onChange={(e) => setForm({ ...form, other_deductions: e.target.value })}
              className="input-field"
              min={0}
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-slate-border/50">
        <div className="text-sm space-y-1">
          <div>
            <span className="text-slate-muted">CRA (Tax-Free): </span>
            <span className="text-foreground font-mono">{formatCurrency(cra, 'NGN')}</span>
          </div>
          <div>
            <span className="text-slate-muted">Taxable Income: </span>
            <span className="text-foreground font-mono">{formatCurrency(taxableIncome, 'NGN')}</span>
          </div>
          <div>
            <span className="text-slate-muted">Annual PAYE: </span>
            <span className="text-emerald-300 font-mono font-semibold">{formatCurrency(paye, 'NGN')}</span>
          </div>
          <div>
            <span className="text-slate-muted">Monthly PAYE: </span>
            <span className="text-emerald-300 font-mono">{formatCurrency(paye / 12, 'NGN')}</span>
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 font-semibold hover:bg-emerald-500/30 disabled:opacity-60"
        >
          {saving ? 'Calculating...' : 'Save Calculation'}
        </button>
      </div>
    </form>
  );
}
