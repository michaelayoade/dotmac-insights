'use client';

import { FileText, Building2, Package } from 'lucide-react';
import { DataTable } from '@/components/DataTable';
import {
  useReportsExpensesSummary,
  useReportsExpensesTrend,
  useReportsExpensesByCategory,
  useReportsExpensesByVendor,
} from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';

export default function ReportsExpensesPage() {
  const summary = useReportsExpensesSummary();
  const trend = useReportsExpensesTrend();
  const byCategory = useReportsExpensesByCategory();
  const byVendor = useReportsExpensesByVendor();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <FileText className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-white">Expenses Reports</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Expenses</p>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(summary.data?.total_expenses || 0, summary.data?.currency || 'NGN')}
          </p>
        </div>
        {summary.data?.categories?.slice(0, 3).map((cat: any) => (
          <div key={cat.category} className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">{cat.category}</p>
            <p className="text-xl font-bold text-white">{formatCurrency(cat.total, summary.data?.currency || 'NGN')}</p>
            {cat.percentage !== undefined && <p className="text-slate-muted text-xs">{cat.percentage}%</p>}
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold">Expense Trend</h3>
          <span className="text-slate-muted text-sm">{trend.data?.length || 0} periods</span>
        </div>
        <DataTable
          columns={[
            { key: 'period', header: 'Period', render: (row: any) => <span className="text-white">{row.period}</span> },
            { key: 'total', header: 'Total', align: 'right' as const, render: (row: any) => <span className="font-mono text-white">{formatCurrency(row.total, summary.data?.currency || 'NGN')}</span> },
          ]}
          data={trend.data || []}
          keyField="period"
          loading={trend.isLoading}
          emptyMessage="No trend data"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">By Category</h3>
          </div>
          <DataTable
            columns={[
              { key: 'category', header: 'Category', render: (row: any) => <span className="text-white">{row.category}</span> },
              { key: 'total', header: 'Total', align: 'right' as const, render: (row: any) => <span className="font-mono text-white">{formatCurrency(row.total, summary.data?.currency || 'NGN')}</span> },
              { key: 'percentage', header: '%', render: (row: any) => <span className="text-slate-muted text-sm">{row.percentage ?? 0}%</span> },
            ]}
            data={byCategory.data || []}
            keyField="category"
            loading={byCategory.isLoading}
            emptyMessage="No category data"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">By Vendor</h3>
          </div>
          <DataTable
            columns={[
              { key: 'vendor', header: 'Vendor', render: (row: any) => <span className="text-white">{row.vendor || '-'}</span> },
              { key: 'total', header: 'Total', align: 'right' as const, render: (row: any) => <span className="font-mono text-white">{formatCurrency(row.total, summary.data?.currency || 'NGN')}</span> },
            { key: 'invoice_count', header: 'Invoices', render: (row: any) => <span className="text-slate-muted text-sm">{row.invoice_count ?? '-'}</span> },
          ]}
          data={byVendor.data || []}
          keyField="vendor"
          loading={byVendor.isLoading}
          emptyMessage="No vendor data"
        />
      </div>
      </div>
    </div>
  );
}
