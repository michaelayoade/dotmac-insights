'use client';

import { Calculator, Users } from 'lucide-react';
import { DataTable } from '@/components/DataTable';
import {
  useReportsProfitabilityMargins,
  useReportsProfitabilityTrend,
  useReportsProfitabilityBySegment,
} from '@/hooks/useApi';

function formatPercent(value: number | undefined | null) {
  if (value === undefined || value === null) return '0%';
  return `${value}%`;
}

export default function ReportsProfitabilityPage() {
  const margins = useReportsProfitabilityMargins();
  const trend = useReportsProfitabilityTrend();
  const bySegment = useReportsProfitabilityBySegment();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Calculator className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-foreground">Profitability Reports</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: 'Gross Margin', value: margins.data?.gross_margin },
          { label: 'Operating Margin', value: margins.data?.operating_margin },
          { label: 'Net Margin', value: margins.data?.net_margin },
        ].map((card) => (
          <div key={card.label} className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">{card.label}</p>
            <p className="text-2xl font-bold text-foreground">{formatPercent(card.value)}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-foreground font-semibold">Margin Trend</h3>
          <span className="text-slate-muted text-sm">{trend.data?.length || 0} periods</span>
        </div>
        <DataTable
          columns={[
            { key: 'period', header: 'Period', render: (row: any) => <span className="text-foreground">{row.period}</span> },
            { key: 'gross_margin', header: 'Gross', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.gross_margin)}</span> },
            { key: 'operating_margin', header: 'Operating', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.operating_margin)}</span> },
            { key: 'net_margin', header: 'Net', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.net_margin)}</span> },
          ]}
          data={trend.data || []}
          keyField="period"
          loading={trend.isLoading}
          emptyMessage="No trend data"
        />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-teal-electric" />
          <h3 className="text-foreground font-semibold">By Segment</h3>
        </div>
        <DataTable
          columns={[
            { key: 'segment', header: 'Segment', render: (row: any) => <span className="text-foreground">{row.segment}</span> },
            { key: 'gross_margin', header: 'Gross', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.gross_margin)}</span> },
            { key: 'operating_margin', header: 'Operating', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.operating_margin)}</span> },
            { key: 'net_margin', header: 'Net', render: (row: any) => <span className="text-slate-200 text-sm">{formatPercent(row.net_margin)}</span> },
          ]}
          data={bySegment.data || []}
          keyField="segment"
          loading={bySegment.isLoading}
          emptyMessage="No segment data"
        />
      </div>
    </div>
  );
}
