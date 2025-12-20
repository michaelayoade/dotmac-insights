'use client';

import { useState } from 'react';
import { usePurchasingAging, usePurchasingSuppliers } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { AlertTriangle, Calendar, DollarSign, Clock, TrendingDown, Filter, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatPercent(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0%';
  return `${value.toFixed(1)}%`;
}

interface AgingBucket {
  bucket: string;
  total: number;
  count: number;
  percentage?: number;
}

export default function PurchasingAPAgingPage() {
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [currency, setCurrency] = useState<string>('NGN');
  const [supplierId, setSupplierId] = useState<string>('');

  const { data, isLoading, error } = usePurchasingAging({
    as_of_date: asOfDate || undefined,
    currency: currency || undefined,
    supplier: supplierId || undefined,
  });

  const { data: suppliersData } = usePurchasingSuppliers({ limit: 100, offset: 0 });

  const suppliers = suppliersData?.suppliers || [];
  const buckets: AgingBucket[] = data
    ? [
        { bucket: 'Current', total: data.aging.current.total, count: data.aging.current.count },
        { bucket: '1-30 days', total: data.aging['1_30'].total, count: data.aging['1_30'].count },
        { bucket: '31-60 days', total: data.aging['31_60'].total, count: data.aging['31_60'].count },
        { bucket: '61-90 days', total: data.aging['61_90'].total, count: data.aging['61_90'].count },
        { bucket: 'Over 90 days', total: data.aging.over_90.total, count: data.aging.over_90.count },
      ]
    : [];
  const totalOutstanding = data?.total_payable || 0;

  // Calculate percentages for buckets
  const bucketsWithPercent = buckets.map((bucket) => ({
    ...bucket,
    percentage: totalOutstanding > 0 ? (bucket.total / totalOutstanding) * 100 : 0,
  }));

  // Define aging bucket colors
  const getBucketColor = (index: number) => {
    const colors = [
      { bg: 'bg-green-500', text: 'text-green-400', border: 'border-green-500/30' },
      { bg: 'bg-yellow-500', text: 'text-yellow-400', border: 'border-yellow-500/30' },
      { bg: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/30' },
      { bg: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/30' },
      { bg: 'bg-red-700', text: 'text-red-500', border: 'border-red-700/30' },
    ];
    return colors[index] || colors[colors.length - 1];
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load AP aging data</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Outstanding</p>
          </div>
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-slate-muted" />
          ) : (
            <p className="text-2xl font-bold text-white">{formatCurrency(totalOutstanding)}</p>
          )}
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Current (Not Due)</p>
          </div>
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-xl font-bold text-green-400">
                {formatCurrency(buckets[0]?.total || 0)}
              </p>
              <p className="text-xs text-green-400/70">{formatNumber(buckets[0]?.count || 0)} bills</p>
            </>
          )}
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-orange-400" />
            <p className="text-orange-400 text-sm">1-60 Days Overdue</p>
          </div>
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-xl font-bold text-orange-400">
                {formatCurrency(
                  (buckets[1]?.total || 0) + (buckets[2]?.total || 0)
                )}
              </p>
              <p className="text-xs text-orange-400/70">
                {formatNumber((buckets[1]?.count || 0) + (buckets[2]?.count || 0))} bills
              </p>
            </>
          )}
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <p className="text-red-400 text-sm">60+ Days Overdue</p>
          </div>
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-slate-muted" />
          ) : (
            <>
              <p className="text-xl font-bold text-red-400">
                {formatCurrency(
                  (buckets[3]?.total || 0) + (buckets[4]?.total || 0)
                )}
              </p>
              <p className="text-xs text-red-400/70">
                {formatNumber((buckets[3]?.count || 0) + (buckets[4]?.count || 0))} bills
              </p>
            </>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="As of date"
            />
          </div>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="NGN">NGN - Naira</option>
            <option value="USD">USD - Dollar</option>
          </select>
          {suppliers.length > 0 && (
            <select
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 max-w-[200px]"
            >
              <option value="">All Suppliers</option>
              {suppliers.map((supplier: any) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name || supplier.supplier_name}
                </option>
              ))}
            </select>
          )}
          {(asOfDate || currency !== 'NGN' || supplierId) && (
            <button
              onClick={() => {
                setAsOfDate('');
                setCurrency('NGN');
                setSupplierId('');
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Aging Buckets Visualization */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-6">
          <TrendingDown className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">AP Aging Breakdown</h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-teal-electric" />
          </div>
        ) : bucketsWithPercent.length > 0 ? (
          <div className="space-y-4">
            {/* Stacked bar visualization */}
            <div className="h-8 flex rounded-lg overflow-hidden">
              {bucketsWithPercent.map((bucket, index) => {
                const color = getBucketColor(index);
                if (bucket.percentage === 0) return null;
                return (
                  <div
                    key={bucket.bucket}
                    className={cn('h-full transition-all', color.bg)}
                    style={{ width: `${bucket.percentage}%` }}
                    title={`${bucket.bucket}: ${formatCurrency(bucket.total)} (${formatPercent(bucket.percentage)})`}
                  />
                );
              })}
            </div>

            {/* Detailed breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mt-6">
              {bucketsWithPercent.map((bucket, index) => {
                const color = getBucketColor(index);
                return (
                  <div
                    key={bucket.bucket}
                    className={cn(
                      'rounded-lg p-4 border',
                      `bg-slate-elevated ${color.border}`
                    )}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <div className={cn('w-3 h-3 rounded-full', color.bg)} />
                      <p className={cn('text-sm font-medium', color.text)}>{bucket.bucket}</p>
                    </div>
                    <p className="text-xl font-bold text-white">{formatCurrency(bucket.total)}</p>
                    <div className="flex justify-between mt-1">
                      <p className="text-xs text-slate-muted">{formatNumber(bucket.count)} bills</p>
                      <p className="text-xs text-slate-muted">{formatPercent(bucket.percentage)}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Total row */}
            <div className="flex justify-between items-center pt-4 border-t border-slate-border mt-4">
              <span className="text-slate-muted font-medium">Total Outstanding</span>
              <span className="text-2xl font-bold text-white">{formatCurrency(totalOutstanding)}</span>
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <Clock className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No aging data available</p>
            <p className="text-slate-muted text-sm mt-1">
              Aging data will appear once there are outstanding bills
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
