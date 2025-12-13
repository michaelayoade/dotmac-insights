'use client';

import { CreditCard, Landmark } from 'lucide-react';
import { DataTable } from '@/components/DataTable';
import {
  useReportsCashPositionSummary,
  useReportsCashPositionForecast,
  useReportsCashPositionRunway,
} from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';

export default function ReportsCashPositionPage() {
  const summary = useReportsCashPositionSummary();
  const forecast = useReportsCashPositionForecast();
  const runway = useReportsCashPositionRunway();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <CreditCard className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-white">Cash Position</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Total Cash</p>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(summary.data?.total_cash || 0, summary.data?.currency || 'NGN')}
          </p>
          {summary.data?.updated_at && <p className="text-slate-muted text-xs">Updated {summary.data.updated_at}</p>}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Runway</p>
          <p className="text-2xl font-bold text-white">
            {runway.data?.months_of_runway !== undefined ? `${runway.data.months_of_runway} months` : '—'}
          </p>
          {runway.data?.burn_rate !== undefined && (
            <p className="text-slate-muted text-xs">
              Burn {formatCurrency(runway.data.burn_rate, runway.data.currency || 'NGN')}
            </p>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Accounts</p>
          <p className="text-2xl font-bold text-white">{summary.data?.accounts?.length || 0}</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Landmark className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Balances by Account</h3>
        </div>
        <DataTable
          columns={[
            { key: 'account', header: 'Account', render: (row: any) => <span className="text-white">{row.account}</span> },
            { key: 'balance', header: 'Balance', align: 'right' as const, render: (row: any) => <span className="font-mono text-white">{formatCurrency(row.balance, summary.data?.currency || 'NGN')}</span> },
          ]}
          data={summary.data?.accounts || []}
          keyField="account"
          loading={summary.isLoading}
          emptyMessage="No accounts"
        />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold">Forecast</h3>
          <span className="text-slate-muted text-sm">{forecast.data?.length || 0} periods</span>
        </div>
        <DataTable
          columns={[
            { key: 'period', header: 'Period', render: (row: any) => <span className="text-white">{row.period}</span> },
            { key: 'projected_cash', header: 'Projected Cash', align: 'right' as const, render: (row: any) => <span className="font-mono text-white">{formatCurrency(row.projected_cash, summary.data?.currency || 'NGN')}</span> },
          ]}
          data={forecast.data || []}
          keyField="period"
          loading={forecast.isLoading}
          emptyMessage="No forecast data"
        />
      </div>
    </div>
  );
}
