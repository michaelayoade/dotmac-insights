'use client';

import { useState } from 'react';
import {
  FileText,
  FileSpreadsheet,
  Download,
  Calendar,
  Filter,
  Loader2,
  BarChart3,
  Wallet2,
  CreditCard,
  ChevronRight,
  PieChart,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useExpenseSummaryReport, useExpenseReportExports } from '@/hooks/useExpenses';
import { useErrorHandler } from '@/hooks/useErrorHandler';
import type { ExpenseSummaryReport } from '@/lib/expenses.types';

type ReportType = 'claims' | 'advances' | 'transactions';
type ExportFormat = 'csv' | 'excel' | 'pdf';

const REPORT_TYPES: { id: ReportType; label: string; icon: typeof FileText; description: string; formats: ExportFormat[] }[] = [
  { id: 'claims', label: 'Expense Claims', icon: FileText, description: 'All submitted expense claims with line items', formats: ['csv', 'excel', 'pdf'] },
  { id: 'advances', label: 'Cash Advances', icon: Wallet2, description: 'Cash advance requests and settlements', formats: ['csv', 'excel', 'pdf'] },
  { id: 'transactions', label: 'Card Transactions', icon: CreditCard, description: 'Corporate card transaction history', formats: ['csv', 'excel'] },
];

const FORMAT_CONFIG: Record<ExportFormat, { label: string; icon: typeof FileText; color: string }> = {
  csv: { label: 'CSV', icon: FileText, color: 'text-green-400' },
  excel: { label: 'Excel', icon: FileSpreadsheet, color: 'text-emerald-400' },
  pdf: { label: 'PDF', icon: FileText, color: 'text-red-400' },
};

function formatCurrency(amount: number, currency: string = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function getDefaultDateRange() {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 1);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

export default function ExpenseReportsPage() {
  const { handleError } = useErrorHandler();
  const defaultRange = getDefaultDateRange();
  const [startDate, setStartDate] = useState(defaultRange.start);
  const [endDate, setEndDate] = useState(defaultRange.end);
  const [selectedReport, setSelectedReport] = useState<ReportType>('claims');
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('excel');
  const [includeLines, setIncludeLines] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [exporting, setExporting] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useExpenseSummaryReport({
    start_date: startDate,
    end_date: endDate,
  });

  const { exportClaims, exportAdvances, exportTransactions } = useExpenseReportExports();

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = {
        format: selectedFormat,
        start_date: startDate,
        end_date: endDate,
        status: statusFilter || undefined,
      };

      if (selectedReport === 'claims') {
        await exportClaims({ ...params, include_lines: includeLines });
      } else if (selectedReport === 'advances') {
        await exportAdvances(params);
      } else {
        await exportTransactions({ ...params, format: selectedFormat === 'pdf' ? 'csv' : selectedFormat });
      }
    } catch (err) {
      handleError(err, 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const currentReportConfig = REPORT_TYPES.find((r) => r.id === selectedReport);
  const availableFormats = currentReportConfig?.formats || ['csv', 'excel'];

  // Ensure selected format is available for current report
  if (!availableFormats.includes(selectedFormat)) {
    setSelectedFormat(availableFormats[0]);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
          <BarChart3 className="w-5 h-5 text-violet-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Expense Reports</h1>
          <p className="text-slate-muted text-sm">Generate and export expense data</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Filters & Export Options */}
        <div className="lg:col-span-2 space-y-6">
          {/* Date Range */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Calendar className="w-4 h-4 text-violet-400" />
              <h2 className="text-lg font-semibold text-foreground">Date Range</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              {[
                { label: 'This Month', getValue: () => { const d = new Date(); return { start: new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10), end: d.toISOString().slice(0, 10) }; } },
                { label: 'Last Month', getValue: () => { const d = new Date(); return { start: new Date(d.getFullYear(), d.getMonth() - 1, 1).toISOString().slice(0, 10), end: new Date(d.getFullYear(), d.getMonth(), 0).toISOString().slice(0, 10) }; } },
                { label: 'This Quarter', getValue: () => { const d = new Date(); const q = Math.floor(d.getMonth() / 3); return { start: new Date(d.getFullYear(), q * 3, 1).toISOString().slice(0, 10), end: d.toISOString().slice(0, 10) }; } },
                { label: 'This Year', getValue: () => { const d = new Date(); return { start: new Date(d.getFullYear(), 0, 1).toISOString().slice(0, 10), end: d.toISOString().slice(0, 10) }; } },
              ].map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => { const v = preset.getValue(); setStartDate(v.start); setEndDate(v.end); }}
                  className="px-3 py-1.5 text-xs font-medium bg-slate-elevated hover:bg-slate-border/50 text-slate-muted hover:text-foreground rounded-lg transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Report Type Selection */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-4 h-4 text-violet-400" />
              <h2 className="text-lg font-semibold text-foreground">Report Type</h2>
            </div>
            <div className="grid gap-3">
              {REPORT_TYPES.map((report) => {
                const Icon = report.icon;
                const isSelected = selectedReport === report.id;
                return (
                  <button
                    key={report.id}
                    onClick={() => setSelectedReport(report.id)}
                    className={cn(
                      'flex items-center gap-4 p-4 rounded-xl border transition-all text-left',
                      isSelected
                        ? 'bg-violet-500/10 border-violet-500/40'
                        : 'bg-slate-elevated border-slate-border hover:border-slate-border/80'
                    )}
                  >
                    <div className={cn(
                      'p-3 rounded-xl',
                      isSelected ? 'bg-violet-500/20 text-violet-300' : 'bg-slate-border/30 text-slate-muted'
                    )}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <p className={cn('font-medium', isSelected ? 'text-foreground' : 'text-slate-muted')}>{report.label}</p>
                      <p className="text-xs text-slate-muted mt-0.5">{report.description}</p>
                    </div>
                    <ChevronRight className={cn('w-4 h-4', isSelected ? 'text-violet-400' : 'text-slate-muted')} />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Export Options */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-4 h-4 text-violet-400" />
              <h2 className="text-lg font-semibold text-foreground">Export Options</h2>
            </div>

            <div className="space-y-4">
              {/* Format Selection */}
              <div>
                <label className="block text-sm text-slate-muted mb-2">Format</label>
                <div className="flex gap-2">
                  {availableFormats.map((format) => {
                    const config = FORMAT_CONFIG[format];
                    const isSelected = selectedFormat === format;
                    return (
                      <button
                        key={format}
                        onClick={() => setSelectedFormat(format)}
                        className={cn(
                          'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
                          isSelected
                            ? 'bg-violet-500/15 border-violet-500/40 text-foreground'
                            : 'bg-slate-elevated border-slate-border text-slate-muted hover:text-foreground'
                        )}
                      >
                        <config.icon className={cn('w-4 h-4', isSelected ? config.color : '')} />
                        {config.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Status Filter */}
              <div>
                <label className="block text-sm text-slate-muted mb-2">Status Filter</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                >
                  <option value="">All statuses</option>
                  {selectedReport === 'claims' && (
                    <>
                      <option value="draft">Draft</option>
                      <option value="pending_approval">Pending Approval</option>
                      <option value="approved">Approved</option>
                      <option value="rejected">Rejected</option>
                      <option value="posted">Posted</option>
                      <option value="paid">Paid</option>
                    </>
                  )}
                  {selectedReport === 'advances' && (
                    <>
                      <option value="draft">Draft</option>
                      <option value="pending_approval">Pending Approval</option>
                      <option value="approved">Approved</option>
                      <option value="disbursed">Disbursed</option>
                      <option value="settled">Settled</option>
                    </>
                  )}
                  {selectedReport === 'transactions' && (
                    <>
                      <option value="imported">Imported</option>
                      <option value="matched">Matched</option>
                      <option value="unmatched">Unmatched</option>
                      <option value="disputed">Disputed</option>
                    </>
                  )}
                </select>
              </div>

              {/* Include Line Items (Claims only) */}
              {selectedReport === 'claims' && (
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="includeLines"
                    checked={includeLines}
                    onChange={(e) => setIncludeLines(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
                  />
                  <label htmlFor="includeLines" className="text-sm text-slate-muted">
                    Include line item details (expanded rows)
                  </label>
                </div>
              )}
            </div>

            {/* Export Button */}
            <button
              onClick={handleExport}
              disabled={exporting}
              className="mt-6 w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-foreground font-semibold rounded-xl transition-colors disabled:opacity-50"
            >
              {exporting ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Download className="w-5 h-5" />
              )}
              {exporting ? 'Generating Report...' : `Download ${FORMAT_CONFIG[selectedFormat].label}`}
            </button>
          </div>
        </div>

        {/* Right column: Summary Stats */}
        <div className="space-y-6">
          {/* Period Summary */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <PieChart className="w-4 h-4 text-violet-400" />
              <h2 className="text-lg font-semibold text-foreground">Period Summary</h2>
            </div>

            {summaryLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
              </div>
            ) : summary ? (
              <div className="space-y-4">
                {/* Claims Summary */}
                <Link href="/expenses/claims" className="block p-4 bg-slate-elevated rounded-xl group hover:bg-slate-elevated/80 transition-colors cursor-pointer">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-sky-400" />
                      <span className="text-sm font-medium text-foreground">Expense Claims</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-sky-400 group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-slate-muted">Count</p>
                      <p className="text-foreground font-semibold">{summary.claims.count}</p>
                    </div>
                    <div>
                      <p className="text-slate-muted">Total Claimed</p>
                      <p className="text-foreground font-semibold">{formatCurrency(summary.claims.total_claimed)}</p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-slate-muted">Approved</p>
                      <p className="text-emerald-400 font-semibold">{formatCurrency(summary.claims.total_approved)}</p>
                    </div>
                  </div>
                </Link>

                {/* Advances Summary */}
                <Link href="/expenses/advances" className="block p-4 bg-slate-elevated rounded-xl group hover:bg-slate-elevated/80 transition-colors cursor-pointer">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Wallet2 className="w-4 h-4 text-amber-400" />
                      <span className="text-sm font-medium text-foreground">Cash Advances</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-amber-400 group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-slate-muted">Count</p>
                      <p className="text-foreground font-semibold">{summary.advances.count}</p>
                    </div>
                    <div>
                      <p className="text-slate-muted">Requested</p>
                      <p className="text-foreground font-semibold">{formatCurrency(summary.advances.total_requested)}</p>
                    </div>
                    <div>
                      <p className="text-slate-muted">Disbursed</p>
                      <p className="text-emerald-400 font-semibold">{formatCurrency(summary.advances.total_disbursed)}</p>
                    </div>
                    <div>
                      <p className="text-slate-muted">Outstanding</p>
                      <p className="text-amber-400 font-semibold">{formatCurrency(summary.advances.total_outstanding)}</p>
                    </div>
                  </div>
                </Link>

                {/* Top Categories */}
                {summary.top_categories && summary.top_categories.length > 0 && (
                  <div className="p-4 bg-slate-elevated rounded-xl">
                    <p className="text-sm font-medium text-foreground mb-3">Top Expense Categories</p>
                    <div className="space-y-2">
                      {summary.top_categories.slice(0, 5).map((cat, i) => (
                        <div key={i} className="flex items-center justify-between text-sm">
                          <span className="text-slate-muted truncate">{cat.category}</span>
                          <span className="text-foreground font-medium">{formatCurrency(cat.total)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Status Breakdown */}
                {summary.claims.by_status && summary.claims.by_status.length > 0 && (
                  <div className="p-4 bg-slate-elevated rounded-xl">
                    <p className="text-sm font-medium text-foreground mb-3">Claims by Status</p>
                    <div className="space-y-2">
                      {summary.claims.by_status.map((s, i) => (
                        <div key={i} className="flex items-center justify-between text-sm">
                          <span className="text-slate-muted capitalize">{s.status.replace(/_/g, ' ')}</span>
                          <span className="text-foreground">
                            <span className="font-medium">{s.count}</span>
                            <span className="text-slate-muted ml-2">({formatCurrency(s.amount)})</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-muted text-sm text-center py-4">No data for selected period</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
