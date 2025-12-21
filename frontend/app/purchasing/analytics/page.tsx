'use client';

import { useState, useMemo } from 'react';
import {
  useConsolidatedPurchasingDashboard,
  usePurchasingBySupplier,
  usePurchasingByCostCenter,
  usePurchasingExpenseTrend,
} from '@/hooks/useApi';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Building2,
  Briefcase,
  Calendar,
  DollarSign,
  PieChart,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

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

function getDateRange(range: string): { start_date: string; end_date: string } {
  const now = new Date();
  const end = now.toISOString().split('T')[0];
  let start: Date;

  switch (range) {
    case '7d':
      start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    case '30d':
      start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      break;
    case '90d':
      start = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
      break;
    case '1y':
      start = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
      break;
    case 'ytd':
      start = new Date(now.getFullYear(), 0, 1);
      break;
    default:
      start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }

  return {
    start_date: start.toISOString().split('T')[0],
    end_date: end,
  };
}

function getTrendParams(range: string): { months: number; interval: 'month' | 'week' } {
  const now = new Date();
  switch (range) {
    case '7d':
      return { months: 1, interval: 'week' };
    case '30d':
      return { months: 1, interval: 'month' };
    case '90d':
      return { months: 3, interval: 'month' };
    case '1y':
      return { months: 12, interval: 'month' };
    case 'ytd':
      return { months: now.getMonth() + 1, interval: 'month' };
    default:
      return { months: 6, interval: 'month' };
  }
}

export default function PurchasingAnalyticsPage() {
  const currency = 'NGN';
  const [dateRange, setDateRange] = useState('30d');
  const { start_date, end_date } = useMemo(() => getDateRange(dateRange), [dateRange]);
  const { months, interval } = useMemo(() => getTrendParams(dateRange), [dateRange]);

  const { data: dashboardData, error: dashboardError } = useConsolidatedPurchasingDashboard(currency, {
    start_date,
    end_date,
  });
  const { data: supplierData, isLoading: supplierLoading } = usePurchasingBySupplier({
    start_date,
    end_date,
    limit: 10,
    currency,
  });
  const { data: costCenterData, isLoading: costCenterLoading } = usePurchasingByCostCenter({
    start_date,
    end_date,
    currency,
  });
  const { data: trendData, isLoading: trendLoading } = usePurchasingExpenseTrend({
    months,
    interval,
    currency,
  });

  const topSuppliers = supplierData?.suppliers || [];
  const costCenters = costCenterData?.cost_centers || [];
  const expenseTrend = trendData?.trend || [];
  const totalOutstanding = dashboardData?.summary?.total_outstanding || 0;
  const totalOverdue = dashboardData?.summary?.total_overdue || 0;
  const supplierCount = dashboardData?.summary?.supplier_count || 0;
  const dueThisWeek = dashboardData?.summary?.due_this_week?.total || 0;
  const dueThisWeekCount = dashboardData?.summary?.due_this_week?.count || 0;

  // Calculate totals for percentage calculations
  const totalSupplierSpend = topSuppliers.reduce(
    (sum: number, s: any) => sum + (s.total_purchases || 0),
    0
  );
  const totalCostCenterSpend = costCenters.reduce(
    (sum: number, c: any) => sum + (c.total || 0),
    0
  );

  // Get max value for bar chart scaling
  const maxTrendValue = Math.max(
    ...expenseTrend.map((t: any) => t.total || 0),
    1
  );
  const totalTransactions = expenseTrend.reduce((sum: number, t: any) => sum + (t.entry_count || 0), 0);

  if (dashboardError) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load analytics</p>
        <p className="text-slate-muted text-sm mt-1">
          {dashboardError instanceof Error ? dashboardError.message : 'Unknown error'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Date Range Filter */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Purchasing Analytics</h2>
          <p className="text-slate-muted text-sm">Spending insights and trends ({start_date} → {end_date})</p>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-muted" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="ytd">Year to Date</option>
            <option value="1y">Last Year</option>
          </select>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/purchasing/purchase-invoices?status=unpaid" className="bg-slate-card border border-slate-border rounded-xl p-4 group hover:border-slate-border/80 hover:bg-slate-card/80 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-teal-electric" />
              <p className="text-slate-muted text-sm">Total Outstanding</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-teal-electric group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(totalOutstanding)}
          </p>
        </Link>

        <Link href="/books/suppliers" className="bg-slate-card border border-slate-border rounded-xl p-4 group hover:border-slate-border/80 hover:bg-slate-card/80 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-blue-400" />
              <p className="text-slate-muted text-sm">Active Suppliers</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-teal-electric group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-2xl font-bold text-white">
            {formatNumber(supplierCount)}
          </p>
          <p className="text-xs text-slate-muted mt-1">Due this week: {formatCurrency(dueThisWeek)} ({formatNumber(dueThisWeekCount)} bills)</p>
        </Link>

        <Link href="/purchasing/purchase-invoices" className="bg-slate-card border border-slate-border rounded-xl p-4 group hover:border-slate-border/80 hover:bg-slate-card/80 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-purple-400" />
              <p className="text-slate-muted text-sm">Avg Transaction</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-teal-electric group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(totalSupplierSpend && supplierCount ? totalSupplierSpend / supplierCount : 0)}
          </p>
        </Link>

        <Link href="/purchasing/purchase-invoices?status=overdue" className="bg-slate-card border border-slate-border rounded-xl p-4 group hover:border-slate-border/80 hover:bg-slate-card/80 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-400" />
              <p className="text-slate-muted text-sm">Overdue</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-teal-electric group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-2xl font-bold text-red-400">
            {formatCurrency(totalOverdue)}
          </p>
          <p className="text-xs text-slate-muted mt-1">
            Entries in range: {formatNumber(totalTransactions)}
          </p>
        </Link>
      </div>

      {/* Expense Trend Chart */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-teal-electric" />
            <h3 className="text-white font-medium">Spending Trend</h3>
          </div>
        </div>

        {trendLoading ? (
          <div className="h-48 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-teal-electric"></div>
          </div>
        ) : expenseTrend.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-slate-muted">
            No trend data available for this period
          </div>
        ) : (
          <div className="space-y-3">
            {expenseTrend.map((item: any, index: number) => {
              const amount = item.total || 0;
              const percentage = (amount / maxTrendValue) * 100;
              const prevAmount =
                index > 0
                  ? expenseTrend[index - 1].total || 0
                  : amount;
              const change = prevAmount > 0 ? ((amount - prevAmount) / prevAmount) * 100 : 0;

              return (
                <div key={item.period || item.month || index} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-300">
                      {item.period || item.month || item.date || `Period ${index + 1}`}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-white font-medium">{formatCurrency(amount)}</span>
                      {index > 0 && (
                        <span
                          className={cn(
                            'text-xs flex items-center gap-0.5',
                            change >= 0 ? 'text-red-400' : 'text-green-400'
                          )}
                        >
                          {change >= 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {Math.abs(change).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-teal-electric to-teal-electric/50 rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Top Suppliers & Cost Centers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Suppliers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-6">
            <Building2 className="w-5 h-5 text-blue-400" />
            <h3 className="text-white font-medium">Top Suppliers by Spend</h3>
          </div>

          {supplierLoading ? (
            <div className="h-48 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-400"></div>
            </div>
          ) : topSuppliers.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-muted">
              No supplier data available
            </div>
          ) : (
            <div className="space-y-4">
              {topSuppliers.slice(0, 8).map((supplier: any, index: number) => {
                const amount = supplier.total_purchases || 0;
                const percentage = totalSupplierSpend > 0 ? (amount / totalSupplierSpend) * 100 : 0;
                const colors = [
                  'bg-blue-500',
                  'bg-purple-500',
                  'bg-teal-500',
                  'bg-orange-500',
                  'bg-pink-500',
                  'bg-indigo-500',
                  'bg-yellow-500',
                  'bg-green-500',
                ];

                return (
                  <div key={supplier.name || supplier.id || index} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            'w-3 h-3 rounded-full flex-shrink-0',
                            colors[index % colors.length]
                          )}
                        />
                        <span className="text-slate-300 text-sm truncate">
                          {supplier.name || 'Unknown'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-white font-mono text-sm">
                          {formatCurrency(amount)}
                        </span>
                        <span className="text-slate-muted text-xs">
                          ({formatPercent(percentage)})
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all duration-500', colors[index % colors.length])}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cost Centers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-6">
            <Briefcase className="w-5 h-5 text-purple-400" />
            <h3 className="text-white font-medium">Spend by Cost Center</h3>
          </div>

          {costCenterLoading ? (
            <div className="h-48 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-400"></div>
            </div>
          ) : costCenters.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-muted">
              No cost center data available
            </div>
          ) : (
            <div className="space-y-4">
              {costCenters.slice(0, 8).map((center: any, index: number) => {
                const amount = center.total || 0;
                const percentage =
                  totalCostCenterSpend > 0 ? (amount / totalCostCenterSpend) * 100 : 0;
                const colors = [
                  'bg-purple-500',
                  'bg-indigo-500',
                  'bg-blue-500',
                  'bg-cyan-500',
                  'bg-teal-500',
                  'bg-green-500',
                  'bg-yellow-500',
                  'bg-orange-500',
                ];

                return (
                  <div key={center.name || index} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            'w-3 h-3 rounded-full flex-shrink-0',
                            colors[index % colors.length]
                          )}
                        />
                        <span className="text-slate-300 text-sm truncate">
                          {center.cost_center || center.name || 'Unassigned'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-white font-mono text-sm">
                          {formatCurrency(amount)}
                        </span>
                        <span className="text-slate-muted text-xs">
                          ({formatPercent(percentage)})
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all duration-500', colors[index % colors.length])}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/purchasing/purchase-invoices?status=paid" className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 group hover:bg-green-500/20 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <PieChart className="w-4 h-4 text-green-400" />
              <p className="text-green-400 text-sm">Paid Bills</p>
            </div>
            <ChevronRight className="w-4 h-4 text-green-400/50 group-hover:text-green-400 group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatCurrency(totalSupplierSpend)}
          </p>
          <p className="text-xs text-green-400/70 mt-1">
            {formatNumber(totalTransactions)} entries
          </p>
        </Link>

        <Link href="/purchasing/purchase-invoices?status=unpaid" className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 group hover:bg-orange-500/20 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-orange-400" />
              <p className="text-orange-400 text-sm">Outstanding</p>
            </div>
            <ChevronRight className="w-4 h-4 text-orange-400/50 group-hover:text-orange-400 group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-xl font-bold text-orange-400">
            {formatCurrency(totalOutstanding)}
          </p>
          <p className="text-xs text-orange-400/70 mt-1">
            {formatNumber(totalSupplierSpend ? totalTransactions : 0)} entries
          </p>
        </Link>

        <Link href="/purchasing/purchase-invoices?status=overdue" className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 group hover:bg-red-500/20 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <p className="text-red-400 text-sm">Overdue</p>
            </div>
            <ChevronRight className="w-4 h-4 text-red-400/50 group-hover:text-red-400 group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-xl font-bold text-red-400">
            {formatCurrency(totalOverdue)}
          </p>
          <p className="text-xs text-red-400/70 mt-1">
            {formatNumber(topSuppliers.length)} suppliers in data
          </p>
        </Link>

        <Link href="/purchasing/purchase-invoices?due_this_week=true" className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 group hover:bg-blue-500/20 transition-colors cursor-pointer">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-blue-400" />
              <p className="text-blue-400 text-sm">Due This Week</p>
            </div>
            <ChevronRight className="w-4 h-4 text-blue-400/50 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />
          </div>
          <p className="text-xl font-bold text-blue-400">
            {formatCurrency(dueThisWeek)}
          </p>
          <p className="text-xs text-blue-400/70 mt-1">
            {formatNumber(dueThisWeekCount)} bills
          </p>
        </Link>
      </div>
    </div>
  );
}
