'use client';

import { TrendingUp, Users, Package } from 'lucide-react';
import { DataTable } from '@/components/DataTable';
import {
  useReportsRevenueSummary,
  useReportsRevenueTrend,
  useReportsRevenueByCustomer,
  useReportsRevenueByProduct,
} from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';

function formatPeriod(period: string) {
  return period;
}

export default function ReportsRevenuePage() {
  const summary = useReportsRevenueSummary();
  const trend = useReportsRevenueTrend();
  const byCustomer = useReportsRevenueByCustomer();
  const byProduct = useReportsRevenueByProduct();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-foreground">Revenue Reports</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'MRR', value: summary.data?.mrr },
          { label: 'ARR', value: summary.data?.arr },
          { label: 'Total Revenue', value: summary.data?.total_revenue },
          { label: 'Growth', value: summary.data?.growth_rate, suffix: '%', isPercent: true },
        ].map((card) => (
          <div key={card.label} className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">{card.label}</p>
            <p className="text-2xl font-bold text-foreground">
              {card.isPercent
                ? `${card.value ?? 0}${card.suffix || ''}`
                : formatCurrency(card.value || 0, summary.data?.currency || 'NGN')}
            </p>
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-foreground font-semibold">Revenue Trend</h3>
          <span className="text-slate-muted text-sm">{trend.data?.length || 0} periods</span>
        </div>
        <DataTable
          columns={[
            { key: 'period', header: 'Period', render: (row: any) => <span className="text-foreground">{formatPeriod(row.period)}</span> },
            { key: 'revenue', header: 'Revenue', align: 'right' as const, render: (row: any) => <span className="font-mono text-foreground">{formatCurrency(row.revenue, summary.data?.currency || 'NGN')}</span> },
            { key: 'mrr', header: 'MRR', align: 'right' as const, render: (row: any) => <span className="font-mono text-slate-200">{formatCurrency(row.mrr || 0, summary.data?.currency || 'NGN')}</span> },
            { key: 'arr', header: 'ARR', align: 'right' as const, render: (row: any) => <span className="font-mono text-slate-200">{formatCurrency(row.arr || 0, summary.data?.currency || 'NGN')}</span> },
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
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Top Customers</h3>
          </div>
          <DataTable
            columns={[
              { key: 'customer', header: 'Customer', render: (row: any) => <span className="text-foreground">{row.customer || `Customer #${row.customer_id}`}</span> },
              { key: 'revenue', header: 'Revenue', align: 'right' as const, render: (row: any) => <span className="font-mono text-foreground">{formatCurrency(row.revenue, summary.data?.currency || 'NGN')}</span> },
            { key: 'growth_rate', header: 'Growth', render: (row: any) => <span className="text-slate-muted text-sm">{row.growth_rate ?? 0}%</span> },
          ]}
          data={byCustomer.data || []}
          keyField="customer"
          loading={byCustomer.isLoading}
          emptyMessage="No customer data"
        />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">By Product</h3>
          </div>
          <DataTable
            columns={[
              { key: 'product', header: 'Product', render: (row: any) => <span className="text-foreground">{row.product || '-'}</span> },
              { key: 'revenue', header: 'Revenue', align: 'right' as const, render: (row: any) => <span className="font-mono text-foreground">{formatCurrency(row.revenue, summary.data?.currency || 'NGN')}</span> },
            { key: 'growth_rate', header: 'Growth', render: (row: any) => <span className="text-slate-muted text-sm">{row.growth_rate ?? 0}%</span> },
          ]}
          data={byProduct.data || []}
          keyField="product"
          loading={byProduct.isLoading}
          emptyMessage="No product data"
        />
        </div>
      </div>
    </div>
  );
}
