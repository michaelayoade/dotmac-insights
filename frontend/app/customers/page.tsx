'use client';

import { useMemo, useState, useEffect } from 'react';
import {
  Search,
  Mail,
  Phone,
  Calendar,
  Users,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Activity,
  MapPin,
  Ticket,
  ShieldAlert,
  ShieldQuestion,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Badge, StatusBadge } from '@/components/Badge';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useCustomers,
  useCustomer,
  useCustomer360,
  useCustomerDashboard,
  useCustomerUsage,
} from '@/hooks/useApi';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

type StatusOption = 'all' | 'active' | 'blocked' | 'inactive' | 'new';

function renderRiskBadges(
  billingHealth: {
    days_until_blocking?: number;
    overdue_invoices?: number;
    deposit_balance?: number;
  } | undefined,
  status: string
) {
  const badges: React.ReactNode[] = [];
  const days = billingHealth?.days_until_blocking;
  const overdue = billingHealth?.overdue_invoices || 0;
  const deposit = billingHealth?.deposit_balance;

  if (status === 'blocked') {
    badges.push(
      <Badge key="blocked" variant="danger" size="sm">
        🚫 Blocked
      </Badge>
    );
  }

  if (typeof days === 'number' && days <= 3) {
    badges.push(
      <Badge key="blocking-3" variant="danger" size="sm">
        🔴 Blocking in {days}d
      </Badge>
    );
  } else if (typeof days === 'number' && days <= 7) {
    badges.push(
      <Badge key="blocking-7" variant="warning" size="sm">
        🟠 Blocking in {days}d
      </Badge>
    );
  }

  if (overdue > 0) {
    badges.push(
      <Badge key="overdue" variant="warning" size="sm">
        💰 Overdue
      </Badge>
    );
  }

  if (typeof deposit === 'number' && deposit < 0) {
    badges.push(
      <Badge key="deposit" variant="warning" size="sm">
        ⚠️ Low Balance
      </Badge>
    );
  }

  return badges;
}

function MetricCard({
  label,
  value,
  subValue,
  icon: Icon,
  trend,
  trendLabel,
  variant = 'default'
}: {
  label: string;
  value: string | number;
  subValue?: string;
  icon: React.ElementType;
  trend?: number;
  trendLabel?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const variantStyles = {
    default: 'text-white',
    success: 'text-teal-electric',
    warning: 'text-amber-warn',
    danger: 'text-coral-alert',
  };

  return (
    <div className="bg-slate-card/50 backdrop-blur-sm border border-slate-border rounded-xl p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-xs uppercase tracking-wide">{label}</p>
          <p className={cn('text-2xl font-bold font-mono mt-1', variantStyles[variant])}>
            {value}
          </p>
          {subValue && (
            <p className="text-slate-muted text-xs mt-0.5">{subValue}</p>
          )}
        </div>
        <div className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center',
          variant === 'success' ? 'bg-teal-electric/10' :
          variant === 'warning' ? 'bg-amber-warn/10' :
          variant === 'danger' ? 'bg-coral-alert/10' :
          'bg-slate-elevated'
        )}>
          <Icon className={cn(
            'w-5 h-5',
            variant === 'success' ? 'text-teal-electric' :
            variant === 'warning' ? 'text-amber-warn' :
            variant === 'danger' ? 'text-coral-alert' :
            'text-slate-muted'
          )} />
        </div>
      </div>
      {trend !== undefined && (
        <div className="flex items-center gap-1 mt-2">
          {trend >= 0 ? (
            <TrendingUp className="w-3 h-3 text-teal-electric" />
          ) : (
            <TrendingDown className="w-3 h-3 text-coral-alert" />
          )}
          <span className={cn(
            'text-xs font-medium',
            trend >= 0 ? 'text-teal-electric' : 'text-coral-alert'
          )}>
            {trend >= 0 ? '+' : ''}{trend.toFixed(1)}
          </span>
          {trendLabel && (
            <span className="text-slate-muted text-xs">{trendLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}

export default function CustomersPage() {
  // Allow either explore:read (spec) or customers:read (legacy/nav) to view the page
  const { hasAccess: canViewCustomers, isLoading: authLoading } = useRequireScope(['explore:read', 'customers:read']);
  const { hasAccess: hasAnalytics } = useRequireScope('analytics:read');

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusOption>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [cohortFilter, setCohortFilter] = useState<string>('');
  const [cityFilter, setCityFilter] = useState<string>('');
  const [baseStationFilter, setBaseStationFilter] = useState<string>('');
  const [signupStart, setSignupStart] = useState<string>('');
  const [signupEnd, setSignupEnd] = useState<string>('');
  const [searchInput, setSearchInput] = useState('');
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [detailTab, setDetailTab] = useState<'profile' | 'finance' | 'services' | 'network' | 'support' | 'projects' | 'crm' | 'timeline'>('profile');

  const { data: dashboard, isLoading: dashboardLoading } = useCustomerDashboard(hasAnalytics);

  const { data, isLoading } = useCustomers({
    search: search || undefined,
    status: statusFilter === 'all' ? undefined : statusFilter,
    customer_type: typeFilter === 'all' ? undefined : typeFilter,
    cohort: cohortFilter || undefined,
    city: cityFilter || undefined,
    base_station: baseStationFilter || undefined,
    signup_start: signupStart || undefined,
    signup_end: signupEnd || undefined,
    limit,
    offset,
  });

  const items = data?.items || [];
  const total = data?.total || 0;

  const { data: selectedCustomer } = useCustomer(selectedCustomerId);
  const { data: customer360, isLoading: c360Loading } = useCustomer360(selectedCustomerId);
  const { data: usageData, isLoading: usageLoading } = useCustomerUsage(selectedCustomerId);

  // Debounce search input updates to avoid excessive fetches
  useEffect(() => {
    const timeout = setTimeout(() => {
      setSearch(searchInput);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  const resetFilters = () => {
    setSearch('');
    setStatusFilter('all');
    setTypeFilter('all');
    setCohortFilter('');
    setCityFilter('');
    setBaseStationFilter('');
    setSignupStart('');
    setSignupEnd('');
    setSearch('');
    setSearchInput('');
    setOffset(0);
    setLimit(20);
  };

  const recentInvoices = useMemo(() => {
    if (customer360?.finance?.recent_invoices?.length) {
      return customer360.finance.recent_invoices;
    }
    return selectedCustomer?.recent_invoices || [];
  }, [customer360?.finance?.recent_invoices, selectedCustomer?.recent_invoices]);

  const derivedOverdue = useMemo(() => {
    if (!recentInvoices || recentInvoices.length === 0) {
      return { count: 0, amount: 0 };
    }

    const overdueInvoices = recentInvoices.filter((inv: any) => {
      const status = String((inv as any).status || '').toLowerCase();
      const overdueDays = (inv as any).days_overdue;
      return status === 'overdue' || status === 'unpaid' || status === 'pending' || status === 'partially_paid' || (typeof overdueDays === 'number' && overdueDays > 0);
    });

    const amount = overdueInvoices.reduce((sum: number, inv: any) => {
      const total = Number((inv as any).total_amount ?? (inv as any).total ?? 0);
      const paid = Number((inv as any).amount_paid ?? 0);
      return sum + Math.max(total - paid, 0);
    }, 0);

    return { count: overdueInvoices.length, amount };
  }, [recentInvoices]);

  const mrrFromSubscriptions = useMemo(() => {
    if (!selectedCustomer?.subscriptions) return 0;
    return selectedCustomer.subscriptions
      .filter((sub: any) => (sub.status || '').toLowerCase() === 'active')
      .reduce((sum: number, sub: any) => sum + Number(sub.price || 0), 0);
  }, [selectedCustomer?.subscriptions]);

  const financeSummary = useMemo(() => {
    const summary = customer360?.finance?.summary;
    const metrics = selectedCustomer?.metrics;

    const totalInvoiced = summary?.total_invoiced
      ?? selectedCustomer?.invoiced_total
      ?? metrics?.total_invoiced
      ?? 0;

    const totalPaid = summary?.total_paid
      ?? selectedCustomer?.paid_total
      ?? metrics?.total_paid
      ?? 0;

    const outstanding = summary?.outstanding_balance
      ?? selectedCustomer?.outstanding_balance
      ?? metrics?.outstanding
      ?? Math.max(totalInvoiced - totalPaid, 0);

    return {
      mrr: summary?.mrr ?? selectedCustomer?.mrr ?? mrrFromSubscriptions,
      totalInvoiced,
      totalPaid,
      outstanding,
      overdueInvoices: summary?.overdue_invoices ?? derivedOverdue.count,
      overdueAmount: summary?.overdue_amount ?? derivedOverdue.amount,
      creditNotes: summary?.credit_notes ?? 0,
      creditNoteTotal: summary?.credit_note_total ?? 0,
    };
  }, [customer360?.finance?.summary, selectedCustomer, mrrFromSubscriptions, derivedOverdue]);

  const outstandingDisplay = Math.max(financeSummary.outstanding || 0, 0);

  if (authLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric" />
      </div>
    );
  }

  if (!canViewCustomers) {
    return <AccessDenied />;
  }

  const overview = dashboard?.overview || {
    total_customers: dashboard?.total_customers ?? 0,
    by_status: dashboard?.by_status ?? { active: 0, blocked: 0, inactive: 0, new: 0 },
    growth_30d: dashboard?.activity_30d ?? { new_signups: 0, churned: 0, net_change: 0 },
    total_mrr: (dashboard as any)?.total_mrr,
  };
  const finance = dashboard?.finance || {
    revenue: { total_mrr: overview.total_mrr },
    invoices: {},
    billing_health: dashboard?.billing_health,
  };
  const statusBreakdown = overview?.by_status || { active: 0, blocked: 0, inactive: 0, new: 0 };
  const statusByNewSpec = {
    active: statusBreakdown.active || 0,
    blocked: (statusBreakdown as any)?.blocked ?? 0,
    inactive: (statusBreakdown as any)?.inactive ?? 0,
    new: (statusBreakdown as any)?.new ?? 0,
    churned: (statusBreakdown as any)?.churned ?? 0,
  };
  const activity = overview?.growth_30d || { new_signups: 0, churned: 0, net_change: 0 };
  const billingHealth =
    finance?.billing_health ||
    (dashboard as any)?.finance?.billing_health ||
    (dashboard as any)?.billing_health ||
    (dashboard as any)?.overview?.billing_health ||
    {};
  const invoiceStats: any = finance?.invoices || {};
  const blockingIn3 =
    billingHealth?.blocking_in_3_days ??
    billingHealth?.blocking_3d ??
    billingHealth?.blocking_today ??
    billingHealth?.blocking_in_three_days ??
    billingHealth?.blocking_in_three;
  const blockingIn7 =
    billingHealth?.blocking_in_7_days ??
    billingHealth?.blocking_7d ??
    billingHealth?.blocking_in_seven_days ??
    billingHealth?.blocking_in_seven;
  const mrrAtRisk7 =
    billingHealth?.mrr_at_risk_7d ??
    billingHealth?.mrr_at_risk ??
    billingHealth?.mrr_at_risk_7_days ??
    billingHealth?.mrr_at_risk_7days;
  const negativeDeposit =
    billingHealth?.negative_deposit ??
    billingHealth?.negative_deposits;
  const health = {
    with_overdue_invoices:
      invoiceStats.overdue_count ??
      invoiceStats.overdue_customers ??
      billingHealth?.overdue_invoices ??
      billingHealth?.overdue_customers ??
      (dashboard as any)?.health?.with_overdue_invoices ??
      0,
    with_open_tickets: dashboard?.support?.customers_with_open_tickets ?? dashboard?.support?.tickets?.open ?? 0,
  };
  const hasBillingHealth = [blockingIn3, blockingIn7, mrrAtRisk7, negativeDeposit].some(
    (v) => v !== undefined && v !== null
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Customers</h1>
          <p className="text-slate-muted mt-1">
            Manage and analyze your customer base
          </p>
        </div>
        {hasAnalytics && dashboard && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-elevated rounded-lg">
              <Activity className="w-4 h-4 text-teal-electric" />
              <span className="text-sm text-white font-medium">
                {overview.total_customers}
              </span>
              <span className="text-xs text-slate-muted">total</span>
            </div>
          </div>
        )}
      </div>

      {/* Dashboard Metrics */}
        {hasAnalytics && dashboard && !dashboardLoading && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricCard
              label="Total Customers"
            value={(overview.total_customers || 0).toLocaleString()}
            subValue={`${statusByNewSpec.active.toLocaleString()} active`}
            icon={Users}
          />
            <MetricCard
              label="Active"
              value={statusByNewSpec.active.toLocaleString()}
              subValue={`Blocked ${statusByNewSpec.blocked.toLocaleString()} / Inactive ${statusByNewSpec.inactive.toLocaleString()}`}
              icon={Activity}
              variant="success"
            />
            {overview.total_mrr !== undefined && (
              <MetricCard
                label="Total MRR"
                value={formatCurrency(overview.total_mrr, 'NGN')}
                subValue="All customers"
                icon={TrendingUp}
                variant="success"
              />
            )}
            <MetricCard
              label="New Customers"
              value={statusByNewSpec.new.toLocaleString()}
              subValue="Currently marked as new"
              icon={TrendingUp}
            variant="success"
          />
          <MetricCard
            label="Blocked"
            value={statusByNewSpec.blocked.toLocaleString()}
            subValue="Customers needing review"
            icon={AlertTriangle}
            variant={statusByNewSpec.blocked > 0 ? 'warning' : 'default'}
          />
          <MetricCard
            label="New Signups (30d)"
            value={activity.new_signups}
            trend={activity.net_change}
            trendLabel="Net change"
            icon={TrendingUp}
            variant="success"
          />
          <MetricCard
            label="Churned (30d)"
            value={activity.churned}
            icon={TrendingDown}
            variant={activity.churned > 0 ? 'danger' : 'default'}
          />
          {hasBillingHealth && (
            <>
              {blockingIn3 !== undefined && blockingIn3 !== null && (
                <MetricCard
                  label="Blocking in 3 Days"
                  value={blockingIn3.toLocaleString()}
                  subValue="Accounts near suspension"
                  icon={AlertTriangle}
                  variant={blockingIn3 > 0 ? 'warning' : 'default'}
                />
              )}
              {mrrAtRisk7 !== undefined && mrrAtRisk7 !== null && (
                <MetricCard
                  label="MRR at Risk (7d)"
                  value={formatCurrency(mrrAtRisk7)}
                  subValue={`${blockingIn7 ?? 0} customers blocking in 7d`}
                  icon={TrendingDown}
                  variant={mrrAtRisk7 > 0 ? 'warning' : 'default'}
                />
              )}
            </>
          )}
          <MetricCard
            label="Overdue Invoices"
            value={health.with_overdue_invoices}
            subValue="Customers with overdue balances"
            icon={AlertTriangle}
            variant={health.with_overdue_invoices > 0 ? 'warning' : 'default'}
          />
          <MetricCard
            label="Open Tickets"
            value={health.with_open_tickets}
            subValue="Customers needing support"
            icon={Ticket}
            variant={health.with_open_tickets > 0 ? 'warning' : 'default'}
          />
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main Content */}
        <div className="flex-1 space-y-4">
          {/* Filters */}
          <Card padding="sm">
            <div className="flex flex-col md:flex-row gap-4">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                <input
                  type="text"
                  placeholder="Search by name, email, phone..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50 transition-colors"
                />
              </div>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as StatusOption);
                  setOffset(0);
                }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50 w-[160px]"
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="blocked">Blocked</option>
                <option value="inactive">Inactive</option>
                <option value="new">New</option>
              </select>

              {/* Type Filter */}
              <select
                value={typeFilter}
                onChange={(e) => {
                  setTypeFilter(e.target.value);
                  setOffset(0);
                }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50 w-[160px]"
              >
                <option value="all">All Types</option>
                <option value="residential">Residential</option>
                <option value="business">Business</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            {/* Advanced filters */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-3">
              <input
                type="text"
                value={cohortFilter}
                onChange={(e) => { setCohortFilter(e.target.value); setOffset(0); }}
                placeholder="Cohort (YYYY-MM)"
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50"
              />
              <input
                type="text"
                value={cityFilter}
                onChange={(e) => { setCityFilter(e.target.value); setOffset(0); }}
                placeholder="City"
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50"
              />
              <input
                type="text"
                value={baseStationFilter}
                onChange={(e) => { setBaseStationFilter(e.target.value); setOffset(0); }}
                placeholder="Base Station"
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50"
              />
              <input
                type="date"
                value={signupStart}
                onChange={(e) => { setSignupStart(e.target.value); setOffset(0); }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50"
              />
              <input
                type="date"
                value={signupEnd}
                onChange={(e) => { setSignupEnd(e.target.value); setOffset(0); }}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50"
              />
            </div>

            <div className="flex justify-between items-center pt-4">
              <button
                onClick={resetFilters}
                className="text-sm text-slate-muted hover:text-white transition-colors"
              >
                Clear all filters
              </button>
              <div className="text-xs text-slate-muted">
                Cohorts, city, base station, and date range will reset too.
              </div>
            </div>
          </Card>

          {/* Results count */}
        <div className="flex items-center justify-between">
          <p className="text-slate-muted text-sm">
            {total.toLocaleString()} customer{total !== 1 ? 's' : ''} found
          </p>
          {hasBillingHealth && (
            <div className="flex items-center gap-3 text-xs text-slate-muted">
              {blockingIn3 !== undefined && blockingIn3 !== null && blockingIn3 > 0 && (
                <span className="px-2 py-1 bg-amber-warn/10 text-amber-warn rounded-lg border border-amber-warn/30">
                  Blocking 3d: {blockingIn3}
                </span>
              )}
              {blockingIn7 !== undefined && blockingIn7 !== null && blockingIn7 > 0 && (
                <span className="px-2 py-1 bg-amber-warn/10 text-amber-warn rounded-lg border border-amber-warn/30">
                  Blocking 7d: {blockingIn7}
                </span>
              )}
              {negativeDeposit !== undefined && negativeDeposit !== null && negativeDeposit > 0 && (
                <span className="px-2 py-1 bg-coral-alert/10 text-coral-alert rounded-lg border border-coral-alert/30">
                  Negative deposit: {negativeDeposit}
                </span>
              )}
            </div>
          )}
        </div>

          {/* Customer Table */}
          <Card padding="none">
            <DataTable
              columns={[
                {
                  key: 'name',
                  header: 'Customer',
                  sortable: true,
                  render: (item) => (
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-slate-elevated flex items-center justify-center text-teal-electric font-medium font-mono text-sm">
                        {(item.name as string).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-white font-medium font-body">{item.name as string}</p>
                        <p className="text-slate-muted text-xs">
                          {(item.city || item.state) ? `${item.city || ''}${item.city && item.state ? ', ' : ''}${item.state || ''}` : 'Location unknown'}
                        </p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {renderRiskBadges(item.billing_health as any, item.status as string)}
                        </div>
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'email',
                  header: 'Contact',
                  sortable: true,
                  render: (item) => (
                    <div className="space-y-0.5">
                      {item.email ? (
                        <p className="text-slate-muted text-sm">{item.email as string}</p>
                      ) : null}
                      {item.phone ? (
                        <p className="text-slate-muted text-sm">{item.phone as string}</p>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  sortable: true,
                  render: (item) => <StatusBadge status={item.status as string} />,
                },
                {
                  key: 'customer_type',
                  header: 'Type',
                  sortable: true,
                  render: (item) => (
                    <span className="text-slate-muted capitalize">{item.customer_type as string}</span>
                  ),
                },
                {
                  key: 'mrr',
                  header: 'MRR',
                  align: 'right',
                  sortable: true,
                  render: (item) => (
                    <span className="text-slate-muted font-mono">{formatCurrency((item.mrr as number) || 0)}</span>
                  ),
                },
                {
                  key: 'signup_date',
                  header: 'Signup',
                  sortable: true,
                  render: (item) => (
                    <span className="text-slate-muted text-sm">{formatDate(item.signup_date as string)}</span>
                  ),
                },
              ]}
              data={items as unknown as Record<string, unknown>[]}
              keyField="id"
              loading={isLoading}
              emptyMessage="No customers found"
              onRowClick={(item) => setSelectedCustomerId(item.id as number)}
            />
            <Pagination
              total={total}
              limit={limit}
              offset={offset}
              onPageChange={setOffset}
              onLimitChange={setLimit}
              limitOptions={[20, 50, 100]}
            />
          </Card>
        </div>

        {/* Customer Detail Sidebar */}
        {selectedCustomer && (
          <div className="lg:w-[440px]">
            <Card className="sticky top-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-display font-semibold text-white">Customer View</h3>
                  <p className="text-slate-muted text-xs">Full 360 payload</p>
                </div>
                <button
                  onClick={() => { setSelectedCustomerId(null); setDetailTab('profile'); }}
                  className="text-slate-muted hover:text-white transition-colors text-xl leading-none"
                  aria-label="Close details"
                >
                  ×
                </button>
              </div>

              {/* Customer Header */}
              <div className="flex items-start gap-4 mb-4 pb-4 border-b border-slate-border">
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center text-slate-deep font-bold text-xl">
                  {selectedCustomer.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-white font-semibold truncate">{selectedCustomer.name}</h4>
                  <p className="text-slate-muted text-sm truncate">
                    {customer360?.profile?.base_station || selectedCustomer.city || selectedCustomer.state || 'Location unknown'}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <StatusBadge status={selectedCustomer.status} />
                    <span className="text-xs text-slate-muted capitalize">{selectedCustomer.customer_type}</span>
                    {customer360?.profile?.account_number && (
                      <Badge variant="default" size="sm">Acct: {customer360.profile.account_number}</Badge>
                    )}
                    {customer360?.profile?.billing_type && (
                      <Badge variant="default" size="sm">{customer360.profile.billing_type}</Badge>
                    )}
                  </div>
                    {customer360?.profile?.labels && customer360.profile.labels.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {customer360.profile.labels.map((label: string) => (
                        <span key={label} className="px-2 py-1 bg-slate-elevated text-xs text-slate-muted rounded-md border border-slate-border">
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Tabs */}
              <div className="flex flex-wrap gap-2 mb-4">
                {[
                  { key: 'profile', label: 'Profile' },
                  { key: 'sales', label: 'Sales' },
                  { key: 'services', label: 'Services' },
                  { key: 'network', label: 'Network' },
                  { key: 'support', label: 'Support' },
                  { key: 'projects', label: 'Projects' },
                  { key: 'crm', label: 'CRM' },
                  { key: 'timeline', label: 'Timeline' },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setDetailTab(tab.key as typeof detailTab)}
                    className={cn(
                      'px-3 py-1.5 text-xs rounded-md border transition-colors',
                      detailTab === tab.key
                        ? 'border-teal-electric/50 bg-teal-electric/10 text-white'
                        : 'border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70'
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
                {/* Profile */}
                {detailTab === 'profile' && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      {selectedCustomer.email && (
                        <div className="flex items-center gap-3 text-sm">
                          <Mail className="w-4 h-4 text-slate-muted" />
                          <span className="text-white">{selectedCustomer.email}</span>
                        </div>
                      )}
                      {customer360?.profile?.billing_email && (
                        <div className="flex items-center gap-3 text-sm">
                          <Mail className="w-4 h-4 text-slate-muted" />
                          <span className="text-slate-muted">Billing: {customer360.profile.billing_email}</span>
                        </div>
                      )}
                      {selectedCustomer.phone && (
                        <div className="flex items-center gap-3 text-sm">
                          <Phone className="w-4 h-4 text-slate-muted" />
                          <span className="text-white">{selectedCustomer.phone}</span>
                        </div>
                      )}
                      {customer360?.profile?.address && (
                        <div className="flex items-start gap-3 text-sm">
                          <MapPin className="w-4 h-4 text-slate-muted mt-0.5" />
                          <div className="text-slate-muted">
                            <p className="text-white">{customer360.profile.address}</p>
                            {customer360.profile.address_2 && <p>{customer360.profile.address_2}</p>}
                            <p>{[customer360.profile.city, customer360.profile.state, (customer360.profile as any).country].filter(Boolean).join(', ')}</p>
                          </div>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-2 text-xs text-slate-muted">
                        <span>Signup: {customer360?.profile?.dates?.signup ? formatDate(customer360.profile.dates.signup) : '—'}</span>
                        <span>Activation: {customer360?.profile?.dates?.activation ? formatDate(customer360.profile.dates.activation) : '—'}</span>
                        <span>Last online: {customer360?.profile?.dates?.last_online ? formatDate(customer360.profile.dates.last_online) : '—'}</span>
                        <span>Tenure: {customer360?.profile?.tenure_days ? `${customer360.profile.tenure_days} days` : '—'}</span>
                      </div>
                      {customer360?.profile?.external_ids && (
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(customer360.profile.external_ids).map(([key, val]) =>
                            val ? (
                              <Badge key={key} variant="default" size="sm" className="uppercase">
                                {key}: {String(val)}
                              </Badge>
                            ) : null
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {detailTab === 'finance' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <MetricCard label="MRR" value={formatCurrency(financeSummary.mrr || 0)} icon={TrendingUp} />
                      <MetricCard
                        label="Outstanding"
                        value={formatCurrency(outstandingDisplay)}
                        icon={AlertTriangle}
                        variant={outstandingDisplay > 0 ? 'warning' : 'success'}
                      />
                      <MetricCard label="Total Invoiced" value={formatCurrency(financeSummary.totalInvoiced)} icon={TrendingUp} />
                      <MetricCard label="Total Paid" value={formatCurrency(financeSummary.totalPaid)} icon={TrendingUp} variant="success" />
                      <MetricCard label="Overdue Invoices" value={(financeSummary.overdueInvoices || 0).toString()} subValue={formatCurrency(financeSummary.overdueAmount || 0)} icon={AlertTriangle} variant={(financeSummary.overdueInvoices || 0) > 0 ? 'warning' : 'default'} />
                      <MetricCard label="Credit Notes" value={(financeSummary.creditNotes || 0).toString()} subValue={formatCurrency(financeSummary.creditNoteTotal || 0)} icon={Activity} />
                    </div>

                    {customer360?.finance?.billing_health && (
                      <div className="bg-slate-elevated/70 rounded-lg p-3 border border-slate-border/60 text-sm text-slate-muted">
                        <p className="text-xs uppercase text-slate-muted mb-2">Billing Health</p>
                        <div className="grid grid-cols-2 gap-2 text-white font-mono">
                          <span>Blocking in: {customer360.finance.billing_health.days_until_blocking ?? '—'} days</span>
                          <span>Deposit: {formatCurrency(customer360.finance.billing_health.deposit_balance ?? 0)}</span>
                          <span>Blocking date: {customer360.finance.billing_health.blocking_date ? formatDate(customer360.finance.billing_health.blocking_date) : '—'}</span>
                          <span>Pay/month: {formatCurrency(customer360.finance.billing_health.payment_per_month ?? 0)}</span>
                        </div>
                      </div>
                    )}

                    {recentInvoices.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Recent Invoices</p>
                        <div className="space-y-2">
                          {recentInvoices.slice(0, 4).map((inv: any) => (
                            <div key={inv.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div>
                                <p className="text-white font-mono">{inv.invoice_number || `#${inv.id}`}</p>
                                <p className="text-xs text-slate-muted">{inv.due_date ? formatDate(inv.due_date) : 'No due date'}</p>
                              </div>
                              <div className="text-right">
                                <p className="text-teal-electric font-mono">{formatCurrency((inv as any).total_amount ?? (inv as any).total ?? 0)}</p>
                                <StatusBadge status={inv.status} size="sm" />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {customer360?.finance?.recent_payments && customer360.finance.recent_payments.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Recent Payments</p>
                        <div className="space-y-2">
                          {customer360.finance.recent_payments.slice(0, 3).map((pay: any) => (
                            <div key={pay.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div className="text-white font-mono">{formatCurrency(pay.amount)}</div>
                              <div className="text-right text-xs text-slate-muted">
                                <div>{pay.payment_method || '—'}</div>
                                <div>{pay.payment_date ? formatDate(pay.payment_date) : '—'}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Services */}
                {detailTab === 'services' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <MetricCard label="Total Subs" value={(customer360?.services?.summary?.total_subscriptions ?? selectedCustomer.subscriptions?.length ?? 0).toString()} icon={Activity} />
                      <MetricCard label="Active Subs" value={(customer360?.services?.summary?.active_subscriptions ?? selectedCustomer.subscriptions?.filter((s: any) => s.status === 'active').length ?? 0).toString()} icon={TrendingUp} variant="success" />
                      <MetricCard label="Services MRR" value={formatCurrency(customer360?.services?.summary?.total_mrr ?? selectedCustomer.mrr ?? mrrFromSubscriptions)} icon={TrendingUp} />
                      <MetricCard label="Usage 30d" value={`${customer360?.services?.usage_30d?.total_gb ?? usageData?.totals?.total_gb ?? 0} GB`} icon={Activity} />
                    </div>

                    {customer360?.services?.subscriptions && customer360.services.subscriptions.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Subscriptions</p>
                        <div className="space-y-2">
                          {customer360.services.subscriptions.map((sub: any) => (
                            <div key={sub.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div>
                                <p className="text-white font-medium">{sub.plan_name}</p>
                                <p className="text-xs text-slate-muted">
                                  {sub.start_date ? formatDate(sub.start_date) : 'Start N/A'}
                                  {sub.end_date ? ` → ${formatDate(sub.end_date)}` : ''}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-teal-electric font-mono">{formatCurrency(sub.price)}</p>
                                <StatusBadge status={sub.status} size="sm" />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {usageData && (
                      <div className="bg-slate-elevated/70 rounded-lg p-3 text-xs text-slate-muted">
                        <p className="text-xs uppercase mb-2">Usage (last 30d)</p>
                        <div className="flex justify-between text-white font-mono">
                          <span>Down: {usageData.totals?.download_gb?.toFixed(1)} GB</span>
                          <span>Up: {usageData.totals?.upload_gb?.toFixed(1)} GB</span>
                          <span>Total: {usageData.totals?.total_gb?.toFixed(1)} GB</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Network */}
                {detailTab === 'network' && (
                  <div className="space-y-3">
                    {customer360?.network?.summary && (
                      <div className="grid grid-cols-3 gap-3">
                        <MetricCard label="IPs" value={(customer360.network.summary.total_ips ?? 0).toString()} icon={Activity} />
                        <MetricCard label="Active IPs" value={(customer360.network.summary.active_ips ?? 0).toString()} icon={Activity} variant="success" />
                        <MetricCard label="Routers" value={(customer360.network.summary.routers_count ?? 0).toString()} icon={Activity} />
                      </div>
                    )}
                    {customer360?.network?.ip_addresses && customer360.network.ip_addresses.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">IP Addresses</p>
                        <div className="space-y-2">
                          {customer360.network.ip_addresses.map((ip: any) => (
                            <div key={ip.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div className="text-white font-mono">{ip.ip}</div>
                              <div className="text-xs text-slate-muted text-right">
                                <div>{ip.hostname || '—'}</div>
                                <div>{ip.status}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {customer360?.network?.routers && customer360.network.routers.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Routers</p>
                        <div className="space-y-2">
                          {customer360.network.routers.map((r: any) => (
                            <div key={r.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div>
                                <p className="text-white font-medium">{r.name}</p>
                                <p className="text-xs text-slate-muted">{r.model} • {r.location || 'Unknown location'}</p>
                              </div>
                              <StatusBadge status={r.status} size="sm" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Support */}
                {detailTab === 'support' && (
                  <div className="space-y-3">
                    {customer360?.support?.summary && (
                      <div className="grid grid-cols-2 gap-3">
                        <MetricCard label="Total Tickets" value={(customer360.support.summary.total_tickets ?? 0).toString()} icon={Activity} />
                        <MetricCard label="Open" value={(customer360.support.summary.open_tickets ?? 0).toString()} icon={AlertTriangle} variant={(customer360.support.summary.open_tickets ?? 0) > 0 ? 'warning' : 'default'} />
                      </div>
                    )}
                    {customer360?.support?.tickets && customer360.support.tickets.length > 0 && (
                      <div className="space-y-2">
                        {customer360.support.tickets.slice(0, 5).map((t: any) => (
                          <div key={t.id} className="bg-slate-card/60 rounded-lg px-3 py-2 text-sm flex items-start justify-between">
                            <div className="min-w-0">
                              <p className="text-white font-medium truncate">{t.subject}</p>
                              <p className="text-xs text-slate-muted">{t.priority} • {formatDate(t.created_at)}</p>
                            </div>
                            <StatusBadge status={t.status} size="sm" />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Projects */}
                {detailTab === 'projects' && (
                  <div className="space-y-3">
                    {customer360?.projects?.summary && (
                      <div className="grid grid-cols-3 gap-3">
                        <MetricCard label="Total" value={(customer360.projects.summary.total_projects ?? 0).toString()} icon={Activity} />
                        <MetricCard label="Active" value={(customer360.projects.summary.active_projects ?? 0).toString()} icon={Activity} />
                        <MetricCard label="Completed" value={(customer360.projects.summary.completed_projects ?? 0).toString()} icon={TrendingUp} variant="success" />
                      </div>
                    )}
                    {customer360?.projects?.projects && customer360.projects.projects.length > 0 && (
                      <div className="space-y-2">
                        {customer360.projects.projects.slice(0, 5).map((p: any) => (
                          <div key={p.id} className="bg-slate-card/60 rounded-lg px-3 py-2 text-sm flex items-start justify-between">
                            <div className="min-w-0">
                              <p className="text-white font-medium truncate">{p.name}</p>
                              <p className="text-xs text-slate-muted">{p.type} • {p.priority}</p>
                              <p className="text-xs text-slate-muted">
                                {p.expected_start ? formatDate(p.expected_start) : '—'} → {p.expected_end ? formatDate(p.expected_end) : '—'}
                              </p>
                            </div>
                            <StatusBadge status={p.status} size="sm" />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* CRM */}
                {detailTab === 'crm' && (
                  <div className="space-y-3">
                    {customer360?.crm?.summary && (
                      <div className="grid grid-cols-2 gap-3">
                        <MetricCard label="Conversations" value={(customer360.crm.summary.total_conversations ?? 0).toString()} icon={Activity} />
                        <MetricCard label="Notes" value={(customer360.crm.summary.total_notes ?? 0).toString()} icon={Activity} />
                      </div>
                    )}
                    {customer360?.crm?.conversations && customer360.crm.conversations.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Conversations</p>
                        <div className="space-y-2">
                          {customer360.crm.conversations.slice(0, 4).map((c: any) => (
                            <div key={c.id} className="flex items-center justify-between bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <div>
                                <p className="text-white capitalize">{c.channel}</p>
                                <p className="text-xs text-slate-muted">{c.status} • {c.assignee || 'Unassigned'}</p>
                              </div>
                              <Badge variant="default" size="sm">{c.message_count} msgs</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {customer360?.crm?.notes && customer360.crm.notes.length > 0 && (
                      <div>
                        <p className="text-xs uppercase text-slate-muted mb-2">Notes</p>
                        <div className="space-y-2">
                          {customer360.crm.notes.slice(0, 4).map((n: any) => (
                            <div key={n.id} className="bg-slate-card/60 rounded-lg px-3 py-2 text-sm">
                              <p className="text-white font-medium">{n.title || n.type || 'Note'}</p>
                              <p className="text-xs text-slate-muted">{n.comment || 'No comment'}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Timeline */}
                {detailTab === 'timeline' && (
                  <div className="space-y-2">
                    {customer360?.timeline && customer360.timeline.length > 0 ? (
                      customer360.timeline.slice(0, 10).map((event: any, idx: number) => (
                        <div key={`${event.type}-${idx}`} className="bg-slate-card/60 rounded-lg px-3 py-2 text-sm flex items-start justify-between">
                          <div className="min-w-0">
                            <p className="text-white font-medium capitalize">{event.type}: {event.title}</p>
                            <p className="text-xs text-slate-muted">{event.description || 'No description'}</p>
                          </div>
                          <div className="text-xs text-slate-muted text-right">
                            <div>{event.status}</div>
                            <div>{event.date ? formatDate(event.date) : '—'}</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-slate-muted">No timeline events.</div>
                    )}
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
