'use client';

import Link from 'next/link';
import { useConsolidatedPurchasingDashboard } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import {
  DollarSign,
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
  ArrowRight,
} from 'lucide-react';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';

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
  href?: string;
}

function MetricCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', loading, href }: MetricCardProps) {
  const content = (
    <div className={cn(
      'bg-slate-card border border-slate-border rounded-xl p-5 transition-colors',
      href && 'hover:border-teal-electric/50 cursor-pointer'
    )}>
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
      {href && (
        <div className="mt-3 pt-3 border-t border-slate-border/50 flex items-center text-xs text-teal-electric">
          <span>View details</span>
          <ArrowRight className="w-3 h-3 ml-1" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

interface StatusBadgeProps {
  status: string;
  count: number;
  total: number;
  href?: string;
}

function StatusBadge({ status, count, total, href }: StatusBadgeProps) {
  const statusColors: Record<string, string> = {
    open: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    submitted: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    unpaid: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    paid: 'bg-green-500/20 text-green-400 border-green-500/30',
    overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
    partially_paid: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    draft: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  };

  const colorClass = statusColors[status.toLowerCase()] || statusColors.draft;

  const content = (
    <div className={cn(
      'rounded-lg px-3 py-2 border transition-all',
      colorClass,
      href && 'hover:opacity-80 cursor-pointer'
    )}>
      <p className="text-xs font-medium capitalize">{status.replace('_', ' ')}</p>
      <p className="text-lg font-bold">{count}</p>
      <p className="text-xs opacity-75">{formatCurrency(total)}</p>
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

export default function PurchasingDashboardPage() {
  const currency = 'NGN';
  const { data, isLoading, error, mutate } = useConsolidatedPurchasingDashboard(currency);

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load purchasing dashboard data."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) {
    return <LoadingState />;
  }

  const { summary, aging, top_suppliers, recent } = data;

  // Aging buckets
  const agingBuckets = aging?.buckets
    ? [
        { bucket: 'Current', ...aging.buckets.current },
        { bucket: '1-30', ...aging.buckets['1_30'] },
        { bucket: '31-60', ...aging.buckets['31_60'] },
        { bucket: '61-90', ...aging.buckets['61_90'] },
        { bucket: 'Over 90', ...aging.buckets.over_90 },
      ]
    : [];
  const agingTotal = agingBuckets.reduce((sum, b) => sum + (b.total || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchasing Dashboard"
        subtitle="Accounts payable, supplier management, and procurement overview"
        icon={ShoppingCart}
        iconClassName="bg-orange-500/10 border border-orange-500/30"
      />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Outstanding"
          value={formatCurrency(summary?.total_outstanding)}
          subtitle="All unpaid bills"
          icon={DollarSign}
          colorClass="text-blue-400"
          href="/purchasing/bills?status=unpaid"
        />
        <MetricCard
          title="Total Overdue"
          value={formatCurrency(summary?.total_overdue)}
          subtitle={formatPercent(summary?.overdue_percentage) + ' of outstanding'}
          icon={AlertTriangle}
          colorClass="text-red-400"
          href="/purchasing/bills?status=overdue"
        />
        <MetricCard
          title="Due This Week"
          value={formatCurrency(summary?.due_this_week?.total)}
          subtitle={`${summary?.due_this_week?.count || 0} bills due`}
          icon={Calendar}
          colorClass="text-yellow-400"
          href="/purchasing/bills?due_this_week=true"
        />
        <MetricCard
          title="Active Suppliers"
          value={formatNumber(summary?.supplier_count)}
          subtitle="With outstanding balance"
          icon={Users}
          colorClass="text-teal-electric"
          href="/purchasing/suppliers"
        />
      </div>

      {/* Status Breakdown */}
      {summary?.status_breakdown && Object.keys(summary.status_breakdown).length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-teal-electric" />
              <h2 className="text-lg font-semibold text-foreground">Bills by Status</h2>
            </div>
            <Link href="/purchasing/bills" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All Bills <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {Object.entries(summary.status_breakdown).map(([status, data]: [string, any]) => (
              <StatusBadge
                key={status}
                status={status}
                count={data.count}
                total={data.total}
                href={`/purchasing/bills?status=${status}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* AP Aging & Top Suppliers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AP Aging Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-teal-electric" />
              <h2 className="text-lg font-semibold text-foreground">AP Aging Summary</h2>
            </div>
            <Link href="/purchasing/aging" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View Details <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {agingBuckets.length > 0 ? (
            <div className="space-y-3">
              {agingBuckets.map((bucket, index) => {
                const percent = agingTotal > 0 ? (bucket.total / agingTotal) * 100 : 0;
                const barColors = [
                  'bg-green-500',
                  'bg-yellow-500',
                  'bg-orange-500',
                  'bg-red-500',
                  'bg-red-700',
                ];
                return (
                  <div key={bucket.bucket}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-muted">{bucket.bucket}</span>
                      <span className="text-foreground font-medium">{formatCurrency(bucket.total)}</span>
                    </div>
                    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', barColors[index] || 'bg-slate-500')}
                        style={{ width: `${Math.max(percent, percent > 0 ? 2 : 0)}%` }}
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
                  <span className="text-foreground font-bold">{formatCurrency(agingTotal)}</span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No aging data available</p>
          )}
        </div>

        {/* Top Suppliers */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-teal-electric" />
              <h2 className="text-lg font-semibold text-foreground">Top Suppliers by Outstanding</h2>
            </div>
            <Link href="/purchasing/suppliers" className="text-teal-electric text-sm hover:text-teal-glow flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          {top_suppliers && top_suppliers.length > 0 ? (
            <div className="space-y-3">
              {top_suppliers.map((supplier, index) => (
                <Link
                  key={supplier.name || index}
                  href={`/purchasing/suppliers?search=${encodeURIComponent(supplier.name || '')}`}
                  className="flex items-center justify-between hover:bg-slate-elevated/50 rounded-lg p-2 -mx-2 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-elevated flex items-center justify-center text-sm font-medium text-foreground">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-foreground text-sm font-medium truncate max-w-[200px]">{supplier.name}</p>
                      <p className="text-slate-muted text-xs">{supplier.bill_count} bills</p>
                    </div>
                  </div>
                  <p className="text-foreground font-medium">{formatCurrency(supplier.outstanding)}</p>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm">No supplier data available</p>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/purchasing/bills" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <FileText className="w-6 h-6 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(summary?.total_bills)}</p>
          <p className="text-slate-muted text-sm">Total Bills</p>
        </Link>
        <Link href="/purchasing/suppliers" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <Users className="w-6 h-6 text-green-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(summary?.supplier_count)}</p>
          <p className="text-slate-muted text-sm">Total Suppliers</p>
        </Link>
        <Link href="/purchasing/bills?status=paid" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <CreditCard className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(summary?.status_breakdown?.paid?.count || 0)}</p>
          <p className="text-slate-muted text-sm">Paid Bills</p>
        </Link>
        <Link href="/purchasing/bills?status=overdue" className="bg-slate-elevated border border-slate-border rounded-lg p-4 text-center hover:border-teal-electric/50 transition-all">
          <ArrowDownRight className="w-6 h-6 text-red-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-foreground">{formatNumber(summary?.status_breakdown?.overdue?.count || 0)}</p>
          <p className="text-slate-muted text-sm">Overdue Bills</p>
        </Link>
      </div>

      {/* Quick lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold text-sm">Recent Bills</h3>
            </div>
            <Link href="/purchasing/bills" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.bills?.length ? (
            <div className="space-y-2">
              {recent.bills.map((bill) => (
                <Link
                  key={bill.id}
                  href={`/purchasing/bills/${bill.id}`}
                  className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2 hover:border-teal-electric/50 transition-all"
                >
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">Bill #{bill.id}</p>
                    <p className="text-xs text-slate-muted">
                      {bill.supplier_name || 'Unknown'} • {formatDate(bill.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(bill.grand_total, bill.currency || currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{bill.status}</p>
                  </div>
                </Link>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Payments</h3>
            </div>
            <Link href="/purchasing/payments" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.payments?.length ? (
            <div className="space-y-2">
              {recent.payments.map((pay) => (
                <div key={pay.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">Payment #{pay.id}</p>
                    <p className="text-xs text-slate-muted">
                      {pay.supplier || 'Unknown'} • {formatDate(pay.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(pay.amount, currency)}</p>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Orders</h3>
            </div>
            <Link href="/purchasing/orders" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.orders?.length ? (
            <div className="space-y-2">
              {recent.orders.map((order) => (
                <div key={order.order_no} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">PO {order.order_no}</p>
                    <p className="text-xs text-slate-muted">
                      {order.supplier || 'Unknown'} • {formatDate(order.date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(order.total, currency)}</p>
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
              <h3 className="text-foreground font-semibold text-sm">Recent Debit Notes</h3>
            </div>
            <Link href="/purchasing/debit-notes" className="text-teal-electric text-xs hover:text-teal-glow">View all</Link>
          </div>
          {recent?.debit_notes?.length ? (
            <div className="space-y-2">
              {recent.debit_notes.map((note) => (
                <div key={note.id} className="flex items-center justify-between bg-slate-elevated/60 border border-slate-border/60 rounded-lg px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-foreground text-sm font-medium">Debit #{note.id}</p>
                    <p className="text-xs text-slate-muted">
                      {note.supplier || 'Unknown'} • {formatDate(note.posting_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-foreground font-mono">{formatCurrency(note.grand_total, currency)}</p>
                    <p className="text-slate-muted text-xs capitalize">{note.status}</p>
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
