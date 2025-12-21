'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  UserX,
  Search,
  Filter,
  Mail,
  MapPin,
  TrendingDown,
  DollarSign,
  Calendar,
  AlertCircle,
  BarChart3,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import useSWR from 'swr';
import { apiFetch, useUnifiedContacts, UnifiedContactsParams, type UnifiedContact } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/lib/design-tokens';

interface ChurnAnalytics {
  period_days: number;
  total_churned: number;
  customers_at_period_start: number;
  churn_rate: number;
  reasons: Array<{ reason: string; count: number }>;
  monthly_trend: Array<{ year: number; month: number; count: number }>;
}

function formatCurrency(value: number | null | undefined, currency = 'NGN'): string {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

export default function ChurnedPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [reasonFilter, setReasonFilter] = useState('');
  const [periodDays, setPeriodDays] = useState(90);

  // Fetch churn analytics for aggregated data
  const { data: analytics, isLoading: analyticsLoading, error: analyticsError } = useSWR<ChurnAnalytics>(
    `/contacts/analytics/churn?period_days=${periodDays}`,
    apiFetch
  );

  const params: UnifiedContactsParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    contact_type: 'churned',
    sort_by: 'created_at',
    sort_order: 'desc',
  };

  const { data, isLoading, error, mutate } = useUnifiedContacts(params);
  const churned = data?.items || [];
  const total = data?.total || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  // Use analytics data for churn reasons
  const churnReasons = useMemo(() => {
    if (!analytics?.reasons) return [];
    return analytics.reasons.map((r, idx) => ({
      name: r.reason || 'Unknown',
      value: r.count,
      color: CHART_COLORS.palette[idx % CHART_COLORS.palette.length],
    }));
  }, [analytics]);

  // Monthly trend data for chart
  const monthlyTrend = useMemo(() => {
    if (!analytics?.monthly_trend) return [];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return analytics.monthly_trend.map((m) => ({
      month: `${months[m.month - 1]} ${m.year}`,
      count: m.count,
    }));
  }, [analytics]);

  // Stats from analytics
  const lostMrr = churned.reduce((sum: number, c: UnifiedContact) => sum + (c.mrr || 0), 0);
  const churnRate = analytics?.churn_rate || 0;

  // Filter by reason if set
  const filteredChurned = reasonFilter
    ? churned.filter((c: UnifiedContact) => (c.churn_reason || 'Unknown') === reasonFilter)
    : churned;

  const columns = [
    {
      key: 'name',
      header: 'Customer',
      render: (item: UnifiedContact) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-red-500/20 border border-red-500/30 flex items-center justify-center">
            <UserX className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <p className="text-white font-medium">{item.name}</p>
            {item.company_name && item.company_name !== item.name && (
              <p className="text-slate-muted text-xs">{item.company_name}</p>
            )}
            {item.email && (
              <span className="flex items-center gap-1 text-xs text-slate-muted mt-0.5">
                <Mail className="w-3 h-3" />
                {item.email}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'churn_reason',
      header: 'Reason',
      render: (item: UnifiedContact) => (
        <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded text-xs">
          {item.churn_reason || 'Unknown'}
        </span>
      ),
    },
    {
      key: 'mrr',
      header: 'Lost MRR',
      align: 'right' as const,
      render: (item: UnifiedContact) => (
        <span className="font-mono text-red-400">{formatCurrency(item.mrr)}</span>
      ),
    },
    {
      key: 'territory',
      header: 'Territory',
      render: (item: UnifiedContact) => (
        item.territory ? (
          <span className="flex items-center gap-1 text-sm text-slate-300">
            <MapPin className="w-3 h-3 text-slate-muted" />
            {item.territory}
          </span>
        ) : <span className="text-slate-muted">-</span>
      ),
    },
    {
      key: 'conversion_date',
      header: 'Customer Since',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-slate-muted">{formatDate(item.conversion_date)}</span>
      ),
    },
    {
      key: 'cancellation_date',
      header: 'Churned On',
      render: (item: UnifiedContact) => (
        <span className="text-sm text-slate-300">{formatDate(item.cancellation_date)}</span>
      ),
    },
  ];

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load churned customers"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Churned Customers"
        subtitle="Analyze customer churn and identify patterns"
        icon={UserX}
        iconClassName="bg-red-500/10 border border-red-500/30"
      />

      {/* Period Selector */}
      <div className="flex items-center gap-2">
        <span className="text-slate-muted text-sm">Period:</span>
        {[30, 90, 180, 365].map((days) => (
          <button
            key={days}
            onClick={() => setPeriodDays(days)}
            className={cn(
              'px-3 py-1 rounded text-sm transition-colors',
              periodDays === days
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                : 'text-slate-muted hover:text-white bg-slate-elevated'
            )}
          >
            {days === 365 ? '1 Year' : `${days} Days`}
          </button>
        ))}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <UserX className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{analytics?.total_churned || total}</p>
              <p className="text-xs text-slate-muted">Churned ({periodDays}d)</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <TrendingDown className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-400">{churnRate}%</p>
              <p className="text-xs text-slate-muted">Churn Rate</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <DollarSign className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-400">{formatCurrency(lostMrr)}</p>
              <p className="text-xs text-slate-muted">Lost MRR</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{churnReasons.length}</p>
              <p className="text-xs text-slate-muted">Churn Reasons</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Churn Reasons Pie */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-red-400" />
            <h3 className="text-white font-semibold">Churn Reasons</h3>
          </div>
          {churnReasons.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={churnReasons}
                  cx="50%"
                  cy="40%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {churnReasons.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: '10px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No churn data
            </div>
          )}
        </div>

        {/* Monthly Trend Bar Chart */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <h3 className="text-white font-semibold">Monthly Trend</h3>
          </div>
          {monthlyTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="month" tick={{ fill: CHART_COLORS.label, fontSize: 10 }} />
                <YAxis tick={{ fill: CHART_COLORS.label, fontSize: 10 }} allowDecimals={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" fill={CHART_COLORS.palette[0]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No trend data
            </div>
          )}
        </div>
      </div>

      {/* Reason Quick Filter */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-red-400" />
          <h3 className="text-white font-semibold">Filter by Reason</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setReasonFilter('')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm transition-colors',
              !reasonFilter ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'text-slate-300 hover:bg-slate-elevated bg-slate-elevated'
            )}
          >
            All ({analytics?.total_churned || total})
          </button>
          {churnReasons.map((reason) => (
            <button
              key={reason.name}
              onClick={() => setReasonFilter(reason.name)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm transition-colors',
                reasonFilter === reason.name ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'text-slate-300 hover:bg-slate-elevated bg-slate-elevated'
              )}
            >
              {reason.name} ({reason.value})
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-red-400" />
          <span className="text-white text-sm font-medium">Search</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search churned customers..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-red-500/50"
            />
          </form>
          {(search || reasonFilter) && (
            <button
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setReasonFilter('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Churned Table */}
      <DataTable
        columns={columns}
        data={filteredChurned}
        keyField="id"
        loading={isLoading}
        emptyMessage="No churned customers found"
        onRowClick={(item) => router.push(`/contacts/${item.id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
