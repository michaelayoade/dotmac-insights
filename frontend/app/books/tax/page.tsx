'use client';

import Link from 'next/link';
import { useTaxDashboard, useUpcomingFilings, useOverdueFilings } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';
import {
  BadgePercent,
  Percent,
  Receipt,
  Users,
  Building2,
  Calendar,
  AlertTriangle,
  Clock,
  ChevronRight,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function TaxDashboardPage() {
  const { data: dashboard, isLoading, error } = useTaxDashboard();
  const { data: upcoming } = useUpcomingFilings({ days: 30 });
  const { data: overdue } = useOverdueFilings();

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load tax dashboard</p>
      </div>
    );
  }

  const taxCards = [
    {
      title: 'VAT',
      href: '/books/tax/vat',
      icon: Percent,
      color: 'text-blue-400 bg-blue-500/10',
      stats: dashboard?.vat_summary ? [
        { label: 'Output VAT', value: formatCurrency(dashboard.vat_summary.output_vat, 'NGN') },
        { label: 'Input VAT', value: formatCurrency(dashboard.vat_summary.input_vat, 'NGN') },
        { label: 'Net VAT', value: formatCurrency(dashboard.vat_summary.net_vat, 'NGN'), highlight: true },
      ] : [],
    },
    {
      title: 'WHT',
      href: '/books/tax/wht',
      icon: Receipt,
      color: 'text-amber-400 bg-amber-500/10',
      stats: dashboard?.wht_summary ? [
        { label: 'Total Deducted', value: formatCurrency(dashboard.wht_summary.total_deducted, 'NGN') },
        { label: 'Pending Remittance', value: formatCurrency(dashboard.wht_summary.pending_remittance, 'NGN'), highlight: true },
        { label: 'Transactions', value: dashboard.wht_summary.transactions_count.toString() },
      ] : [],
    },
    {
      title: 'PAYE',
      href: '/books/tax/paye',
      icon: Users,
      color: 'text-emerald-400 bg-emerald-500/10',
      stats: dashboard?.paye_summary ? [
        { label: 'Total PAYE', value: formatCurrency(dashboard.paye_summary.total_paye, 'NGN') },
        { label: 'Employees', value: dashboard.paye_summary.employees_count.toString() },
        { label: 'Avg Tax Rate', value: `${(dashboard.paye_summary.avg_tax_rate * 100).toFixed(1)}%` },
      ] : [],
    },
    {
      title: 'CIT',
      href: '/books/tax/cit',
      icon: Building2,
      color: 'text-purple-400 bg-purple-500/10',
      stats: dashboard?.cit_summary ? [
        { label: 'Estimated Liability', value: formatCurrency(dashboard.cit_summary.estimated_liability, 'NGN'), highlight: true },
        { label: 'Year', value: dashboard.cit_summary.year.toString() },
        { label: 'Company Size', value: dashboard.cit_summary.company_size },
      ] : [],
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BadgePercent className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-white">Tax Dashboard</h1>
        </div>
        <p className="text-sm text-slate-muted">Period: {dashboard?.period || 'Loading...'}</p>
      </div>

      {/* Overdue Alert */}
      {overdue && overdue.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <h3 className="text-red-400 font-semibold">Overdue Filings</h3>
          </div>
          <div className="space-y-2">
            {overdue.slice(0, 3).map((filing, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <span className="text-white">{filing.tax_type} - {filing.period}</span>
                <span className="text-red-400">
                  {Math.abs(filing.days_until_due)} days overdue
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tax Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {taxCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.title}
              href={card.href}
              className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-teal-electric/40 transition-colors group"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', card.color)}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-white font-semibold">{card.title}</h3>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-teal-electric transition-colors" />
              </div>
              {isLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {card.stats.map((stat, idx) => (
                    <div key={idx} className="flex items-center justify-between text-sm">
                      <span className="text-slate-muted">{stat.label}</span>
                      <span className={cn('font-mono', stat.highlight ? 'text-teal-electric font-semibold' : 'text-white')}>
                        {stat.value}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {/* Upcoming Deadlines */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-teal-electric" />
            <h3 className="text-white font-semibold">Upcoming Deadlines</h3>
          </div>
          <Link
            href="/books/tax/filing"
            className="text-sm text-teal-electric hover:text-teal-electric/80 flex items-center gap-1"
          >
            View All <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
        {upcoming && upcoming.length > 0 ? (
          <div className="space-y-3">
            {upcoming.slice(0, 5).map((filing, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-slate-elevated rounded-lg border border-slate-border/50"
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center',
                    filing.days_until_due <= 7 ? 'bg-amber-500/10 text-amber-400' : 'bg-slate-border/30 text-slate-muted'
                  )}>
                    <Clock className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-white text-sm font-medium">{filing.tax_type} - {filing.period}</p>
                    <p className="text-slate-muted text-xs">{filing.description}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={cn(
                    'text-sm font-medium',
                    filing.days_until_due <= 7 ? 'text-amber-400' : 'text-white'
                  )}>
                    {formatDate(filing.deadline)}
                  </p>
                  <p className="text-xs text-slate-muted">
                    {filing.days_until_due === 0 ? 'Due today' : `${filing.days_until_due} days`}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-muted text-sm text-center py-4">No upcoming deadlines</p>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link
          href="/books/tax/vat"
          className="flex items-center gap-2 p-3 bg-slate-elevated rounded-lg border border-slate-border/50 text-sm text-slate-muted hover:text-white hover:border-slate-border transition-colors"
        >
          <TrendingUp className="w-4 h-4 text-blue-400" />
          Record VAT Output
        </Link>
        <Link
          href="/books/tax/wht"
          className="flex items-center gap-2 p-3 bg-slate-elevated rounded-lg border border-slate-border/50 text-sm text-slate-muted hover:text-white hover:border-slate-border transition-colors"
        >
          <TrendingDown className="w-4 h-4 text-amber-400" />
          Deduct WHT
        </Link>
        <Link
          href="/books/tax/paye"
          className="flex items-center gap-2 p-3 bg-slate-elevated rounded-lg border border-slate-border/50 text-sm text-slate-muted hover:text-white hover:border-slate-border transition-colors"
        >
          <Users className="w-4 h-4 text-emerald-400" />
          Calculate PAYE
        </Link>
        <Link
          href="/books/tax/settings"
          className="flex items-center gap-2 p-3 bg-slate-elevated rounded-lg border border-slate-border/50 text-sm text-slate-muted hover:text-white hover:border-slate-border transition-colors"
        >
          <Building2 className="w-4 h-4 text-purple-400" />
          Tax Settings
        </Link>
      </div>
    </div>
  );
}
