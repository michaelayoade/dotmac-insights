'use client';

import { Radio, Users, DollarSign, Headphones, TrendingDown, AlertCircle, MapPin } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import { Badge } from '@/components/Badge';
import { PopChart } from '@/components/Charts';
import { DataTable } from '@/components/DataTable';
import { usePopPerformance, useOverview } from '@/hooks/useApi';
import { formatCurrency, formatNumber, formatPercent, cn } from '@/lib/utils';

export default function POPsPage() {
  const { data: pops, isLoading } = usePopPerformance();
  const { data: overview } = useOverview();

  const currency = pops?.[0]?.currency || 'NGN';

  // Calculate aggregated stats
  const totalMRR = pops?.reduce((sum, p) => sum + p.mrr, 0) || 0;
  const totalCustomers = pops?.reduce((sum, p) => sum + p.active_customers, 0) || 0;
  const totalTickets = pops?.reduce((sum, p) => sum + p.open_tickets, 0) || 0;
  const avgChurnRate = pops?.length
    ? pops.reduce((sum, p) => sum + p.churn_rate, 0) / pops.length
    : 0;

  // Find problem POPs (high churn or many tickets)
  const problemPops = pops?.filter(p => p.churn_rate > 5 || p.open_tickets > 5) || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-white">POP Performance</h1>
        <p className="text-slate-muted mt-1">
          Network locations and their key metrics
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Total POPs"
          value={pops?.length || 0}
          subtitle="Active network locations"
          icon={Radio}
          loading={isLoading}
        />
        <StatCard
          title="Total MRR"
          value={formatCurrency(totalMRR, currency)}
          subtitle="Across all POPs"
          icon={DollarSign}
          variant="success"
          loading={isLoading}
          animateValue={false}
        />
        <StatCard
          title="Avg Churn Rate"
          value={formatPercent(avgChurnRate)}
          subtitle="Average across POPs"
          icon={TrendingDown}
          variant={avgChurnRate > 5 ? 'danger' : avgChurnRate > 3 ? 'warning' : 'default'}
          loading={isLoading}
          animateValue={false}
        />
        <StatCard
          title="Open Tickets"
          value={totalTickets}
          subtitle="Across all POPs"
          icon={Headphones}
          variant={totalTickets > 20 ? 'warning' : 'default'}
          loading={isLoading}
        />
      </div>

      {/* Problem POPs Alert */}
      {problemPops.length > 0 && (
        <Card className="border-amber-warn/30 bg-amber-warn/5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber-warn/20 flex items-center justify-center shrink-0">
              <AlertCircle className="w-5 h-5 text-amber-warn" />
            </div>
            <div>
              <h3 className="font-semibold text-amber-warn">Attention Required</h3>
              <p className="text-slate-muted text-sm mt-1">
                {problemPops.length} POP{problemPops.length !== 1 ? 's' : ''} need attention:{' '}
                {problemPops.map(p => p.name).join(', ')}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Top POPs by MRR */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Revenue by POP</CardTitle>
              <CardDescription>Monthly recurring revenue per location</CardDescription>
            </div>
          </CardHeader>
          {pops ? (
            <PopChart data={pops} height={320} />
          ) : (
            <div className="h-[320px] skeleton rounded-lg" />
          )}
        </Card>

        {/* POP Cards Grid */}
        <div className="grid grid-cols-2 gap-4 content-start">
          {(pops || []).slice(0, 6).map((pop, index) => (
            <Card
              key={pop.id}
              className={cn(
                'relative overflow-hidden',
                pop.churn_rate > 5 && 'border-coral-alert/30',
                pop.open_tickets > 5 && 'border-amber-warn/30'
              )}
              hover
            >
              {/* Rank badge */}
              <div className="absolute top-3 right-3">
                <span className="w-6 h-6 rounded-full bg-slate-elevated flex items-center justify-center text-xs font-mono text-slate-muted">
                  #{index + 1}
                </span>
              </div>

              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-teal-electric/10 flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-teal-electric" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">{pop.name}</h4>
                  {pop.city && (
                    <p className="text-slate-muted text-xs">{pop.city}</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-muted">MRR</span>
                  <span className="font-mono text-teal-electric">{formatCurrency(pop.mrr, currency)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-muted">Customers</span>
                  <span className="font-mono text-white">{pop.active_customers}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-muted">Churn</span>
                  <span className={cn(
                    'font-mono',
                    pop.churn_rate > 5 ? 'text-coral-alert' : pop.churn_rate > 2 ? 'text-amber-warn' : 'text-slate-muted'
                  )}>
                    {formatPercent(pop.churn_rate)}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Full POP Table */}
      <Card padding="none">
        <div className="p-6 border-b border-slate-border">
          <CardTitle>All POPs</CardTitle>
          <CardDescription>Complete performance breakdown by location</CardDescription>
        </div>
        <DataTable
          columns={[
            {
              key: 'name',
              header: 'POP',
              sortable: true,
              render: (item) => (
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-elevated flex items-center justify-center">
                    <Radio className="w-4 h-4 text-teal-electric" />
                  </div>
                  <div>
                    <p className="text-white font-medium font-body">{item.name as string}</p>
                    <p className="text-slate-muted text-xs">{item.city || item.code || '—'}</p>
                  </div>
                </div>
              ),
            },
            {
              key: 'active_customers',
              header: 'Active',
              sortable: true,
              align: 'right',
              render: (item) => (
                <div className="text-right">
                  <p className="text-white font-mono">{item.active_customers}</p>
                  <p className="text-slate-muted text-xs">{item.total_customers} total</p>
                </div>
              ),
            },
            {
              key: 'mrr',
              header: 'MRR',
              sortable: true,
              align: 'right',
              render: (item) => (
                <span className="text-teal-electric font-mono">
                  {formatCurrency(item.mrr as number, currency)}
                </span>
              ),
            },
            {
              key: 'churn_rate',
              header: 'Churn Rate',
              sortable: true,
              align: 'right',
              render: (item) => {
                const rate = item.churn_rate as number;
                return (
                  <div className="flex items-center justify-end gap-2">
                    <span className={cn(
                      'font-mono',
                      rate > 5 ? 'text-coral-alert' : rate > 2 ? 'text-amber-warn' : 'text-slate-muted'
                    )}>
                      {formatPercent(rate)}
                    </span>
                    {rate > 5 && (
                      <Badge variant="danger" size="sm">High</Badge>
                    )}
                  </div>
                );
              },
            },
            {
              key: 'churned_customers',
              header: 'Churned',
              sortable: true,
              align: 'right',
              render: (item) => (
                <span className={cn(
                  'font-mono',
                  (item.churned_customers as number) > 10 ? 'text-coral-alert' : 'text-slate-muted'
                )}>
                  {item.churned_customers}
                </span>
              ),
            },
            {
              key: 'open_tickets',
              header: 'Tickets',
              sortable: true,
              align: 'right',
              render: (item) => {
                const tickets = item.open_tickets as number;
                return (
                  <div className="flex items-center justify-end gap-2">
                    <span className={cn(
                      'font-mono',
                      tickets > 5 ? 'text-amber-warn' : 'text-slate-muted'
                    )}>
                      {tickets}
                    </span>
                    {tickets > 5 && (
                      <Badge variant="warning" size="sm">High</Badge>
                    )}
                  </div>
                );
              },
            },
            {
              key: 'outstanding',
              header: 'Outstanding',
              sortable: true,
              align: 'right',
              render: (item) => (
                <span className={cn(
                  'font-mono',
                  (item.outstanding as number) > 0 ? 'text-amber-warn' : 'text-slate-muted'
                )}>
                  {formatCurrency(item.outstanding as number, currency)}
                </span>
              ),
            },
          ]}
          data={(pops || []) as Record<string, unknown>[]}
          keyField="id"
          loading={isLoading}
          emptyMessage="No POPs found"
        />
      </Card>
    </div>
  );
}
