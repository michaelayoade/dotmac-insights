'use client';

import Link from 'next/link';
import {
  usePurchasingDashboard,
  usePurchasingSuppliers,
  usePurchasingBills,
  usePurchasingAging,
  usePurchasingBySupplier,
  usePurchasingPayments,
  usePurchasingOrders,
  usePurchasingDebitNotes,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  DollarSign,
  TrendingDown,
  Users,
  FileText,
  Calendar,
  AlertTriangle,
  Loader2,
  Clock,
  CreditCard,
  Building2,
  ArrowDownRight,
  ShoppingCart,
  ArrowLeftRight,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

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

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  loading?: boolean;
}

function MetricCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', loading }: MetricCardProps) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-slate-muted text-sm">{title}</p>
          {loading ? (
            <Loader2 className="w-6 h-6 animate-spin text-slate-muted" />
          ) : (
            <p className={cn('text-2xl font-bold', colorClass)}>{value}</p>
          )}
          {subtitle && <p className="text-slate-muted text-xs">{subtitle}</p>}
        </div>
        <div className={cn('p-2 rounded-lg bg-slate-elevated')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

interface StatusBadgeProps {
  status: string;
  count: number;
  total: number;
}

function StatusBadge({ status, count, total }: StatusBadgeProps) {
  const statusColors: Record<string, string> = {
    open: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    paid: 'bg-green-500/20 text-green-400 border-green-500/30',
    overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
    partially_paid: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    draft: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  };

  const colorClass = statusColors[status.toLowerCase()] || statusColors.draft;

  return (
    <div className={cn('rounded-lg px-3 py-2 border', colorClass)}>
      <p className="text-xs font-medium capitalize">{status.replace('_', ' ')}</p>
      <p className="text-lg font-bold">{count}</p>
      <p className="text-xs opacity-75">{formatCurrency(total)}</p>
    </div>
  );
}

export default function PurchasingDashboardPage() {
  const currency = 'NGN';
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError, mutate: refetchDashboard } = usePurchasingDashboard({ currency });
  const { data: suppliers, isLoading: suppliersLoading, error: suppliersError, mutate: refetchSuppliers } = usePurchasingSuppliers({ limit: 1, offset: 0 });
  const { data: bills, isLoading: billsLoading, error: billsError, mutate: refetchBills } = usePurchasingBills({ limit: 1, offset: 0, currency });
  const { data: aging, isLoading: agingLoading, error: agingError, mutate: refetchAging } = usePurchasingAging({ currency });
  const { data: bySupplier, isLoading: bySupplierLoading, error: bySupplierError, mutate: refetchBySupplier } = usePurchasingBySupplier({ limit: 5, currency });
  const { data: recentBills, isLoading: recentBillsLoading, error: recentBillsError, mutate: refetchRecentBills } = usePurchasingBills({ limit: 5, currency, sort_by: 'posting_date', sort_dir: 'desc' });
  const { data: recentPayments, isLoading: recentPaymentsLoading, error: recentPaymentsError, mutate: refetchRecentPayments } = usePurchasingPayments({ limit: 5, currency });
  const { data: recentOrders, isLoading: recentOrdersLoading, error: recentOrdersError, mutate: refetchRecentOrders } = usePurchasingOrders({ limit: 5, currency, sort_by: 'transaction_date', sort_dir: 'desc' });
  const { data: recentDebitNotes, isLoading: recentDebitNotesLoading, error: recentDebitNotesError, mutate: refetchRecentDebitNotes } = usePurchasingDebitNotes({ limit: 5, currency, sort_by: 'posting_date', sort_dir: 'desc' });

  const swrStates = [
    { error: dashboardError, isLoading: dashboardLoading, mutate: refetchDashboard },
    { error: suppliersError, isLoading: suppliersLoading, mutate: refetchSuppliers },
    { error: billsError, isLoading: billsLoading, mutate: refetchBills },
    { error: agingError, isLoading: agingLoading, mutate: refetchAging },
    { error: bySupplierError, isLoading: bySupplierLoading, mutate: refetchBySupplier },
    { error: recentBillsError, isLoading: recentBillsLoading, mutate: refetchRecentBills },
    { error: recentPaymentsError, isLoading: recentPaymentsLoading, mutate: refetchRecentPayments },
    { error: recentOrdersError, isLoading: recentOrdersLoading, mutate: refetchRecentOrders },
    { error: recentDebitNotesError, isLoading: recentDebitNotesLoading, mutate: refetchRecentDebitNotes },
  ];

  const firstError = swrStates.find((state) => state.error)?.error;
  const isDataLoading = swrStates.some((state) => state.isLoading);
  const retryAll = () => swrStates.forEach((state) => state.mutate?.());

  if (isDataLoading) {
    return <LoadingState />;
  }

  if (firstError) {
    return (
      <ErrorDisplay
        message="Failed to load purchasing dashboard data."
        error={firstError as Error}
        onRetry={retryAll}
      />
    );
  }

  const loading = dashboardLoading;

  // Extract key metrics
  const totalOutstanding = dashboard?.total_outstanding ?? 0;
  const totalOverdue = dashboard?.total_overdue ?? 0;
  const overduePercentage = dashboard?.overdue_percentage ?? 0;
  const supplierCount = dashboard?.supplier_count ?? suppliers?.total ?? 0;
  const statusBreakdown = dashboard?.status_breakdown ?? {};
  const dueThisWeek = dashboard?.due_this_week ?? { count: 0, total: 0 };
  const topSuppliers = dashboard?.top_suppliers ?? [];

  // Aging buckets
  const agingBuckets = aging
    ? Object.entries(aging.aging || {}).map(([bucket, value]: any) => ({
        bucket: bucket.replace('_', '-'),
        total: value.total,
        count: value.count,
      }))
    : [];
  const agingTotal = aging?.total_payable ?? 0;

  // Top suppliers by spend
  const topSuppliersList = bySupplier?.suppliers ?? [];

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Outstanding"
          value={formatCurrency(totalOutstanding)}
          subtitle="All unpaid bills"
          icon={DollarSign}
          colorClass="text-blue-400"
          loading={loading}
        />
        <MetricCard
          title="Total Overdue"
          value={formatCurrency(totalOverdue)}
          subtitle={formatPercent(overduePercentage) + ' of outstanding'}
          icon={AlertTriangle}
          colorClass="text-red-400"
          loading={loading}
        />
        <MetricCard
          title="Due This Week"
          value={formatCurrency(dueThisWeek.total)}
          subtitle={`${dueThisWeek.count} bills due`}
          icon={Calendar}
          colorClass="text-yellow-400"
          loading={loading}
        />
        <MetricCard
          title="Active Suppliers"
          value={formatNumber(supplierCount)}
          subtitle="With outstanding balance"
          icon={Users}
          colorClass="text-teal-electric"
          loading={loading}
        />
      </div>

      {/* Status Breakdown */}
      {Object.keys(statusBreakdown).length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-white">Bills by Status</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {Object.entries(statusBreakdown).map(([status, data]: [string, any]) => (
              <StatusBadge
                key={status}
                status={status}
                count={data.count}
                total={data.total}
              />
            ))}
          </div>
        </div>
      )}

      {/* AP Aging & Top Suppliers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AP Aging Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-white">AP Aging Summary</h2>
          </div>
          {agingBuckets.length > 0 ? (
            <div className="space-y-3">
              {agingBuckets.map((bucket: any, index: number) => {
                const percent = agingTotal > 0 ? (bucket.total / agingTotal) * 100 : 0;
                const barColors = [
                  'bg-green-500',
                  'bg-yellow-500',
                  'bg-orange-500',
                  'bg-red-500',
                  'bg-red-700',
                ];
                return (
                  <div key={bucket.bucket || index}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-muted">{bucket.bucket}</span>
                      <span className="text-white font-medium">{formatCurrency(bucket.total)}</span>
                    </div>
                    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', barColors[index] || 'bg-slate-500')}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs mt-1">
                      <span className="text-slate-muted">{bucket.count} bills</span>
                      <span className="text-slate-muted">{percent.toFixed(1)}%</span>
                    </div>
                  </div>
                );
              })}
              <div className="pt-3 border-t border-slate-border mt-4">
                <div className="flex justify-between">
                  <span className="text-slate-muted">Total Outstanding</span>
                  <span className="text-white font-bold">{formatCurrency(agingTotal)}</span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No aging data available</p>
          )}
        </div>

        {/* Top Suppliers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-white">Top Suppliers by Outstanding</h2>
          </div>
          {topSuppliers.length > 0 ? (
            <div className="space-y-3">
              {topSuppliers.slice(0, 5).map((supplier: any, index: number) => (
                <div key={supplier.name || index} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-elevated flex items-center justify-center text-sm font-medium text-white">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-white text-sm font-medium truncate max-w-[200px]">{supplier.name}</p>
                      <p className="text-slate-muted text-xs">{supplier.bill_count} bills</p>
                    </div>
                  </div>
                  <p className="text-white font-medium">{formatCurrency(supplier.outstanding)}</p>
                </div>
              ))}
            </div>
          ) : topSuppliersList.length > 0 ? (
            <div className="space-y-3">
              {topSuppliersList.slice(0, 5).map((supplier: any, index: number) => (
                <div key={supplier.supplier_name || index} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-elevated flex items-center justify-center text-sm font-medium text-white">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-white text-sm font-medium truncate max-w-[200px]">{supplier.supplier_name}</p>
                      <p className="text-slate-muted text-xs">{supplier.bill_count} bills</p>
                    </div>
                  </div>
                  <p className="text-white font-medium">{formatCurrency(supplier.total_amount)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No supplier data available</p>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <FileText className="w-6 h-6 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(bills?.total)}</p>
          <p className="text-slate-muted text-sm">Total Bills</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <Users className="w-6 h-6 text-green-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(suppliers?.total)}</p>
          <p className="text-slate-muted text-sm">Total Suppliers</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <CreditCard className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(statusBreakdown?.paid?.count || 0)}</p>
          <p className="text-slate-muted text-sm">Paid Bills</p>
        </div>
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center">
          <ArrowDownRight className="w-6 h-6 text-red-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{formatNumber(statusBreakdown?.overdue?.count || 0)}</p>
          <p className="text-slate-muted text-sm">Overdue Bills</p>
        </div>
      </div>

      {/* Quick lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Bills</h3>
            </div>
            <Link href="/purchasing/bills" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentBills?.bills?.length ? (
            <div className="space-y-2">
              {recentBills.bills.map((bill: any) => (
                <div key={bill.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">Bill #{bill.id}</p>
                    <p className="text-xs text-slate-muted">
                      {bill.supplier_name || bill.supplier || 'Unknown'} • {formatDate((bill as any).posting_date || (bill as any).invoice_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency((bill as any).grand_total || (bill as any).total_amount || 0, bill.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{bill.status}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No bills yet.</p>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Payments</h3>
            </div>
            <Link href="/purchasing/payments" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentPayments?.payments?.length ? (
            <div className="space-y-2">
              {recentPayments.payments.map((pay: any) => (
                <div key={pay.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">Payment #{pay.id}</p>
                    <p className="text-xs text-slate-muted">
                      {(pay as any).supplier || (pay as any).party || 'Unknown'} • {formatDate((pay as any).posting_date || pay.payment_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency(pay.amount || 0, pay.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{(pay as any).status || 'processed'}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No payments yet.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ShoppingCart className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Orders</h3>
            </div>
            <Link href="/purchasing/orders" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentOrders?.orders?.length ? (
            <div className="space-y-2">
              {recentOrders.orders.map((order: any) => (
                <div key={order.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">PO #{order.id}</p>
                    <p className="text-xs text-slate-muted">
                      {order.supplier || 'Unknown'} • {formatDate((order as any).date || (order as any).transaction_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency((order as any).total || order.grand_total || 0, order.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{order.status || 'draft'}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No orders yet.</p>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ArrowLeftRight className="w-4 h-4 text-teal-electric" />
              <h3 className="text-white font-semibold text-sm">Recent Debit Notes</h3>
            </div>
            <Link href="/purchasing/debit-notes" className="text-teal-electric text-xs hover:text-teal-glow">Open list</Link>
          </div>
          {recentDebitNotes?.debit_notes?.length ? (
            <div className="space-y-2">
              {recentDebitNotes.debit_notes.map((note: any) => (
                <div key={note.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-white text-sm font-medium">Debit #{note.id}</p>
                    <p className="text-xs text-slate-muted">
                      {note.supplier || 'Unknown'} • {formatDate((note as any).posting_date || (note as any).issue_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-white font-mono">{formatCurrency((note as any).grand_total || (note as any).amount || 0, (note as any).currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{note.status || 'draft'}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No debit notes yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
