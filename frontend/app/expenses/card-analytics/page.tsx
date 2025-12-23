'use client';

import { useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  BarChart3,
  CreditCard,
  TrendingUp,
  TrendingDown,
  Receipt,
  Users,
  Target,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ShoppingBag,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';
import {
  useCardAnalyticsOverview,
  useCardSpendTrend,
  useCardTopMerchants,
  useCardByCategory,
  useCardUtilization,
  useCardStatusBreakdown,
  useCardTopSpenders,
  useCardReconciliationTrend,
  useCardStatementSummary,
} from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/lib/design-tokens';
import { LoadingState, Button, FilterCard, FilterSelect } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const STATUS_COLORS: Record<string, string> = {
  matched: CHART_COLORS.success,
  unmatched: CHART_COLORS.warning,
  imported: CHART_COLORS.axis,
  disputed: CHART_COLORS.danger,
  excluded: CHART_COLORS.grid,
  personal: CHART_COLORS.palette[2],
};
const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

// =============================================================================
// UTILITY COMPONENTS
// =============================================================================

function ChartCard({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-4 h-4 text-violet-400" />}
        <div>
          <h3 className="text-foreground font-semibold">{title}</h3>
          {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function ReconciliationGauge({ rate }: { rate: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (rate / 100) * circumference;
  const color = rate >= 80 ? CHART_COLORS.success : rate >= 50 ? CHART_COLORS.warning : CHART_COLORS.danger;

  return (
    <div className="relative w-28 h-28 mx-auto">
      <svg className="w-full h-full -rotate-90">
        <circle cx="56" cy="56" r={radius} fill="none" stroke={CHART_COLORS.grid} strokeWidth="8" />
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-foreground">{rate.toFixed(0)}%</span>
        <span className="text-[10px] text-slate-muted">Reconciled</span>
      </div>
    </div>
  );
}

function ProgressBar({ value, max, color = 'bg-violet-500' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function CardAnalyticsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const [months, setMonths] = useState(6);
  const [days, setDays] = useState(30);

  const canFetch = !authLoading && !missingScope;
  // Fetch all analytics data
  const { data: overview, isLoading: overviewLoading } = useCardAnalyticsOverview({ months }, { isPaused: () => !canFetch });
  const { data: spendTrend } = useCardSpendTrend({ months }, { isPaused: () => !canFetch });
  const { data: topMerchants } = useCardTopMerchants({ days, limit: 10 }, { isPaused: () => !canFetch });
  const { data: categoryData } = useCardByCategory({ days }, { isPaused: () => !canFetch });
  const { data: utilization } = useCardUtilization({ days }, { isPaused: () => !canFetch });
  const { data: statusBreakdown } = useCardStatusBreakdown({ days }, { isPaused: () => !canFetch });
  const { data: topSpenders } = useCardTopSpenders({ days, limit: 10 }, { isPaused: () => !canFetch });
  const { data: reconciliationTrend } = useCardReconciliationTrend({ months }, { isPaused: () => !canFetch });
  const { data: statementSummary } = useCardStatementSummary({ isPaused: () => !canFetch });

  // Calculate trends
  const latestSpend = spendTrend?.[spendTrend.length - 1];
  const prevSpend = spendTrend?.[spendTrend.length - 2];
  const spendTrendPct = latestSpend && prevSpend && prevSpend.total_spend > 0
    ? ((latestSpend.total_spend - prevSpend.total_spend) / prevSpend.total_spend) * 100
    : 0;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view card analytics."
        backHref="/expenses"
        backLabel="Back to Expenses"
      />
    );
  }

  // Prepare pie chart data for status breakdown
  const pieData = statusBreakdown?.by_status.map((item) => ({
    name: item.status,
    value: item.count,
    color: STATUS_COLORS[item.status] || CHART_COLORS.axis,
  })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Card Analytics</h1>
            <p className="text-slate-muted text-sm">Spend patterns, reconciliation & utilization</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <FilterCard title="Time Range" contentClassName="flex flex-wrap gap-4 items-center" iconClassName="text-violet-400">
        <div>
          <label className="text-xs text-slate-muted mb-1 block">Trend Months</label>
          <FilterSelect
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
          >
            <option value={3}>3 months</option>
            <option value={6}>6 months</option>
            <option value={12}>12 months</option>
          </FilterSelect>
        </div>
        <div>
          <label className="text-xs text-slate-muted mb-1 block">Breakdown Days</label>
          <FilterSelect
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
          </FilterSelect>
        </div>
      </FilterCard>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Spend"
          value={`${((overview?.spend.total || 0) / 1000).toFixed(0)}K`}
          subtitle={`${months} months`}
          icon={CreditCard}
          colorClass="text-violet-400"
          loading={overviewLoading}
          trend={spendTrendPct ? { value: spendTrendPct < 0 ? 1 : -1, label: `${Math.abs(spendTrendPct).toFixed(1)}%` } : undefined}
          href="/expenses/transactions"
        />
        <StatCard
          title="Active Cards"
          value={overview?.cards.active ?? 0}
          subtitle={`${overview?.cards.suspended ?? 0} suspended`}
          icon={CreditCard}
          colorClass="text-emerald-400"
          loading={overviewLoading}
          href="/expenses/cards"
        />
        <StatCard
          title="Transactions"
          value={overview?.transactions.total ?? 0}
          subtitle={`${months} months`}
          icon={Receipt}
          colorClass="text-blue-400"
          loading={overviewLoading}
          href="/expenses/transactions"
        />
        <StatCard
          title="Reconciliation"
          value={`${overview?.transactions.reconciliation_rate ?? 0}%`}
          subtitle={`${overview?.transactions.unmatched ?? 0} unmatched`}
          icon={CheckCircle2}
          colorClass={
            (overview?.transactions.reconciliation_rate ?? 0) >= 80
              ? 'text-emerald-400'
              : (overview?.transactions.reconciliation_rate ?? 0) >= 50
              ? 'text-amber-400'
              : 'text-rose-400'
          }
          loading={overviewLoading}
          href="/expenses/transactions?status=unmatched"
        />
        <StatCard
          title="Disputed"
          value={overview?.transactions.disputed ?? 0}
          subtitle={`${overview?.transactions.personal ?? 0} personal`}
          icon={AlertTriangle}
          colorClass="text-rose-400"
          loading={overviewLoading}
          href="/expenses/transactions?status=disputed"
        />
      </div>

      {/* Reconciliation & Status Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Reconciliation Gauge */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Reconciliation Rate</h3>
          </div>
          <ReconciliationGauge rate={overview?.transactions.reconciliation_rate ?? 0} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-center">
            <div>
              <p className="text-xs text-slate-muted">Matched</p>
              <p className="text-lg font-bold text-emerald-400">{overview?.transactions.matched ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-slate-muted">Unmatched</p>
              <p className="text-lg font-bold text-amber-400">{overview?.transactions.unmatched ?? 0}</p>
            </div>
          </div>
        </div>

        {/* Reconciliation Trend */}
        <ChartCard title="Reconciliation Trend" subtitle="Monthly rate" icon={TrendingUp}>
          {reconciliationTrend?.length ? (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={reconciliationTrend}>
                <defs>
                  <linearGradient id="reconGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.success} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.success} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="period" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} />
                <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} domain={[0, 100]} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => `${value.toFixed(1)}%`} />
                <Line
                  type="monotone"
                  dataKey="reconciliation_rate"
                  stroke={CHART_COLORS.success}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.success, r: 4 }}
                  name="Rate"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[160px] flex items-center justify-center text-slate-muted text-sm">No data</div>
          )}
        </ChartCard>

        {/* Status Pie Chart */}
        <ChartCard title="Transaction Status" subtitle={`${days} days`} icon={Receipt}>
          {pieData.length ? (
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={60}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[160px] flex items-center justify-center text-slate-muted text-sm">No data</div>
          )}
        </ChartCard>
      </div>

      {/* Spend Trend */}
      <ChartCard title="Spend Trend" subtitle={`${months} months of card spend`} icon={TrendingUp}>
        {spendTrend?.length ? (
          <div className="space-y-4">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={spendTrend}>
                <defs>
                  <linearGradient id="spendGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.palette[2]} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.palette[2]} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="matchedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.success} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.success} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="period" stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} />
                <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => value.toLocaleString()} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                />
                <Area
                  type="monotone"
                  dataKey="total_spend"
                  stroke={CHART_COLORS.palette[2]}
                  strokeWidth={2}
                  fill="url(#spendGradient)"
                  name="Total Spend"
                />
                <Area
                  type="monotone"
                  dataKey="matched_spend"
                  stroke={CHART_COLORS.success}
                  strokeWidth={2}
                  fill="url(#matchedGradient)"
                  name="Matched"
                />
              </AreaChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {spendTrend.slice(-6).map((v) => (
                <div key={v.period} className="bg-slate-elevated rounded-lg p-2 text-center">
                  <p className="text-[10px] text-slate-muted">{v.period}</p>
                  <p className="text-sm font-bold text-foreground">{(v.total_spend / 1000).toFixed(0)}K</p>
                  <p className="text-[10px] text-emerald-400">{v.reconciliation_rate}% rec</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="h-[240px] flex items-center justify-center text-slate-muted text-sm">No spend data</div>
        )}
      </ChartCard>

      {/* Top Merchants & Categories */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Merchants */}
        <ChartCard title={`Top Merchants (${days}d)`} subtitle="By total spend" icon={ShoppingBag}>
          {topMerchants?.merchants.length ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={topMerchants.merchants.slice(0, 6)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                  <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                  <YAxis
                    type="category"
                    dataKey="merchant"
                    stroke={CHART_COLORS.axis}
                    tick={{ fontSize: 10 }}
                    width={100}
                    tickFormatter={(value) => (value || 'Unknown').substring(0, 15)}
                  />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => value.toLocaleString()} />
                  <Bar dataKey="total_spend" fill={CHART_COLORS.palette[2]} radius={[0, 4, 4, 0]} name="Spend" />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {topMerchants.merchants.slice(0, 4).map((m, idx) => (
                  <div key={m.merchant} className="flex items-center justify-between text-xs bg-slate-elevated rounded px-2 py-1">
                    <span className="text-slate-muted truncate">{idx + 1}. {m.merchant}</span>
                    <span className="text-violet-400 font-mono">{m.percentage}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">No merchant data</div>
          )}
        </ChartCard>

        {/* Categories */}
        <ChartCard title={`By Category (${days}d)`} subtitle="Merchant category codes" icon={BarChart3}>
          {categoryData?.categories.length ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={categoryData.categories.slice(0, 6)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                  <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                  <YAxis
                    type="category"
                    dataKey="category_name"
                    stroke={CHART_COLORS.axis}
                    tick={{ fontSize: 10 }}
                    width={100}
                    tickFormatter={(value) => (value || 'Other').substring(0, 15)}
                  />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value: number) => value.toLocaleString()} />
                  <Bar dataKey="total_spend" fill={CHART_COLORS.warning} radius={[0, 4, 4, 0]} name="Spend" />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {categoryData.categories.slice(0, 4).map((c) => (
                  <div key={c.mcc_code} className="flex items-center justify-between text-xs bg-slate-elevated rounded px-2 py-1">
                    <span className="text-slate-muted truncate">{c.category_name}</span>
                    <span className="text-amber-400 font-mono">{c.percentage}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">No category data</div>
          )}
        </ChartCard>
      </div>

      {/* Card Utilization & Top Spenders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Card Utilization */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <CreditCard className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Card Utilization ({days}d)</h3>
          </div>
          {utilization?.length ? (
            <div className="space-y-3">
              {utilization.slice(0, 8).map((card) => (
                <div key={card.card_id} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-foreground truncate max-w-[200px]">
                      {card.card_name} <span className="text-slate-muted">****{card.card_last4}</span>
                    </span>
                    <span className={cn(
                      'font-mono',
                      card.utilization_pct >= 80 ? 'text-rose-400' : card.utilization_pct >= 50 ? 'text-amber-400' : 'text-emerald-400'
                    )}>
                      {card.utilization_pct}%
                    </span>
                  </div>
                  <ProgressBar
                    value={card.spend}
                    max={card.credit_limit}
                    color={card.utilization_pct >= 80 ? 'bg-rose-500' : card.utilization_pct >= 50 ? 'bg-amber-500' : 'bg-emerald-500'}
                  />
                  <div className="flex justify-between text-[10px] text-slate-muted">
                    <span>{card.spend.toLocaleString()} spent</span>
                    <span>{card.remaining.toLocaleString()} remaining</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-muted text-sm text-center py-8">No utilization data</p>
          )}
        </div>

        {/* Top Spenders */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-cyan-400" />
            <h3 className="text-foreground font-semibold">Top Spenders ({days}d)</h3>
          </div>
          {topSpenders?.spenders.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-muted text-left">
                    <th className="pb-2">Card</th>
                    <th className="pb-2 text-right">Txns</th>
                    <th className="pb-2 text-right">Spend</th>
                  </tr>
                </thead>
                <tbody>
                  {topSpenders.spenders.slice(0, 10).map((spender, idx) => (
                    <tr key={spender.card_id} className="border-t border-slate-border/40">
                      <td className="py-2 text-foreground truncate max-w-[160px]">
                        <span className="text-slate-muted mr-2">{idx + 1}.</span>
                        {spender.card_name}
                      </td>
                      <td className="py-2 text-right font-mono text-slate-muted">{spender.transaction_count}</td>
                      <td className="py-2 text-right font-mono text-violet-400">{spender.total_spend.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-muted text-sm text-center py-8">No spender data</p>
          )}
        </div>
      </div>

      {/* Statement Summary */}
      {statementSummary && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Receipt className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Statement Summary</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">{statementSummary.statements.total}</p>
              <p className="text-xs text-slate-muted">Total Statements</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-sky-400">{statementSummary.statements.open}</p>
              <p className="text-xs text-slate-muted">Open</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-400">{statementSummary.statements.reconciled}</p>
              <p className="text-xs text-slate-muted">Reconciled</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-400">{statementSummary.statements.closed}</p>
              <p className="text-xs text-slate-muted">Closed</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">{statementSummary.aggregates.total_transactions}</p>
              <p className="text-xs text-slate-muted">Total Txns</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-400">{statementSummary.aggregates.total_matched}</p>
              <p className="text-xs text-slate-muted">Matched</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{statementSummary.aggregates.total_unmatched}</p>
              <p className="text-xs text-slate-muted">Unmatched</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
