'use client';

import Link from 'next/link';
import { useFilingCalendar, useUpcomingFilings, useOverdueFilings } from '@/hooks/useApi';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import {
  Calendar,
  ArrowLeft,
  Clock,
  CheckCircle2,
  XCircle,
  Filter,
  AlertTriangle,
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

function formatDateLong(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

const TAX_TYPE_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  VAT: { bg: 'bg-blue-500/10', text: 'text-blue-400', icon: 'bg-blue-500/20' },
  WHT: { bg: 'bg-amber-500/10', text: 'text-amber-400', icon: 'bg-amber-500/20' },
  PAYE: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', icon: 'bg-emerald-500/20' },
  CIT: { bg: 'bg-purple-500/10', text: 'text-purple-400', icon: 'bg-purple-500/20' },
  STAMP_DUTY: { bg: 'bg-pink-500/10', text: 'text-pink-400', icon: 'bg-pink-500/20' },
  CAPITAL_GAINS: { bg: 'bg-cyan-500/10', text: 'text-cyan-400', icon: 'bg-cyan-500/20' },
};

export default function FilingCalendarPage() {
  const [filters, setFilters] = usePersistentState<{
    taxType: string;
    status: string;
    year: number;
  }>('books.tax.filing.filters', {
    taxType: '',
    status: '',
    year: new Date().getFullYear(),
  });
  const { taxType: taxTypeFilter, status: statusFilter, year } = filters;
  const updateFilters = (next: Partial<typeof filters>) =>
    setFilters((prev) => ({ ...prev, ...next }));

  const { data: calendar, isLoading, error, mutate } = useFilingCalendar({
    year,
    tax_type: taxTypeFilter || undefined,
  });
  const { data: upcoming } = useUpcomingFilings({ days: 60 });
  const { data: overdue } = useOverdueFilings();

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message="Failed to load filing calendar."
        error={error as Error}
        onRetry={() => mutate()}
      />
    );
  }

  // Group filings by month
  const filingsByMonth: Record<string, any[]> = {};
  (calendar?.filings || []).forEach((filing: any) => {
    const month = filing.deadline?.slice(0, 7) || 'Unknown';
    if (!filingsByMonth[month]) filingsByMonth[month] = [];
    filingsByMonth[month].push(filing);
  });

  // Filter by status if selected
  const filterFilings = (filings: any[]) => {
    if (!statusFilter) return filings;
    return filings.filter(f => {
      if (statusFilter === 'overdue') return f.days_until_due < 0 && f.status !== 'FILED';
      if (statusFilter === 'upcoming') return f.days_until_due >= 0 && f.days_until_due <= 30 && f.status !== 'FILED';
      if (statusFilter === 'filed') return f.status === 'FILED';
      return true;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/tax"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Tax
          </Link>
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-white">Filing Calendar</h1>
          </div>
        </div>
      </div>

      {/* Overdue Alert */}
      {overdue && overdue.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5 text-red-400" />
            <h3 className="text-red-400 font-semibold">Overdue Filings ({overdue.length})</h3>
          </div>
          <div className="space-y-2">
            {overdue.map((filing: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-red-500/5 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'px-2 py-1 rounded text-xs font-medium',
                    TAX_TYPE_COLORS[filing.tax_type]?.bg || 'bg-slate-border/30',
                    TAX_TYPE_COLORS[filing.tax_type]?.text || 'text-slate-muted'
                  )}>
                    {filing.tax_type}
                  </span>
                  <div>
                    <p className="text-white text-sm font-medium">{filing.period}</p>
                    <p className="text-slate-muted text-xs">{filing.description}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-red-400 text-sm font-medium">{Math.abs(filing.days_until_due)} days overdue</p>
                  <p className="text-slate-muted text-xs">Due: {formatDate(filing.deadline)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upcoming Summary */}
      {upcoming && upcoming.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5 text-amber-400" />
            <h3 className="text-amber-400 font-semibold">Upcoming (Next 60 Days)</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {upcoming.slice(0, 6).map((filing: any, idx: number) => (
              <div key={idx} className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg border border-slate-border/50">
                <div className={cn(
                  'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                  TAX_TYPE_COLORS[filing.tax_type]?.icon || 'bg-slate-border/30'
                )}>
                  <Clock className={cn('w-5 h-5', TAX_TYPE_COLORS[filing.tax_type]?.text || 'text-slate-muted')} />
                </div>
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium truncate">{filing.tax_type} - {filing.period}</p>
                  <p className={cn(
                    'text-xs',
                    filing.days_until_due <= 7 ? 'text-amber-400' : 'text-slate-muted'
                  )}>
                    {filing.days_until_due === 0 ? 'Due today' : `${filing.days_until_due} days`}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-muted" />
          <span className="text-sm text-slate-muted">Filters:</span>
        </div>
        <select
          value={year}
          onChange={(e) => updateFilters({ year: Number(e.target.value) })}
          className="input-field max-w-[120px]"
        >
          {[...Array(3)].map((_, i) => {
            const y = new Date().getFullYear() + 1 - i;
            return <option key={y} value={y}>{y}</option>;
          })}
        </select>
        <select
          value={taxTypeFilter}
          onChange={(e) => updateFilters({ taxType: e.target.value })}
          className="input-field max-w-[140px]"
        >
          <option value="">All Tax Types</option>
          <option value="VAT">VAT</option>
          <option value="WHT">WHT</option>
          <option value="PAYE">PAYE</option>
          <option value="CIT">CIT</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => updateFilters({ status: e.target.value })}
          className="input-field max-w-[140px]"
        >
          <option value="">All Statuses</option>
          <option value="overdue">Overdue</option>
          <option value="upcoming">Upcoming (30 days)</option>
          <option value="filed">Filed</option>
        </select>
      </div>

      {/* Calendar View by Month */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-card border border-slate-border rounded-xl p-4">
              <div className="h-6 w-32 bg-slate-elevated rounded animate-pulse mb-4" />
              <div className="space-y-3">
                {[1, 2].map((j) => (
                  <div key={j} className="h-16 bg-slate-elevated rounded animate-pulse" />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        (() => {
          const sortedFilings = Object.entries(filingsByMonth)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([month, filings]) => [month, filterFilings(filings)] as const)
            .filter(([, filtered]) => filtered.length > 0);

          if (sortedFilings.length === 0) {
            return (
              <div className="bg-slate-card border border-slate-border rounded-xl p-6 text-center space-y-3">
                <div className="mx-auto w-12 h-12 rounded-full bg-slate-elevated flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-amber-400" />
                </div>
                <div>
                  <p className="text-white font-semibold">No filings match these filters</p>
                  <p className="text-slate-muted text-sm">Adjust the year, tax type, or status to see the calendar.</p>
                </div>
              </div>
            );
          }

          return (
            <div className="space-y-6">
              {sortedFilings.map(([month, filteredFilings]) => {
                const monthDate = new Date(month + '-01');
                const monthName = monthDate.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

                return (
                  <div key={month} className="bg-slate-card border border-slate-border rounded-xl p-4">
                    <h3 className="text-white font-semibold mb-4">{monthName}</h3>
                    <div className="space-y-3">
                      {filteredFilings.map((filing: any, idx: number) => (
                        <div
                          key={idx}
                          className={cn(
                            'flex items-center justify-between p-4 rounded-lg border',
                            filing.status === 'FILED'
                              ? 'bg-emerald-500/5 border-emerald-500/30'
                              : filing.days_until_due < 0
                              ? 'bg-red-500/5 border-red-500/30'
                              : filing.days_until_due <= 7
                              ? 'bg-amber-500/5 border-amber-500/30'
                              : 'bg-slate-elevated border-slate-border/50'
                          )}
                        >
                          <div className="flex items-center gap-4">
                            <div className={cn(
                              'w-12 h-12 rounded-lg flex items-center justify-center shrink-0',
                              TAX_TYPE_COLORS[filing.tax_type]?.icon || 'bg-slate-border/30'
                            )}>
                              {filing.status === 'FILED' ? (
                                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                              ) : filing.days_until_due < 0 ? (
                                <XCircle className="w-6 h-6 text-red-400" />
                              ) : (
                                <Clock className={cn('w-6 h-6', TAX_TYPE_COLORS[filing.tax_type]?.text || 'text-slate-muted')} />
                              )}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className={cn(
                                  'px-2 py-0.5 rounded text-xs font-medium',
                                  TAX_TYPE_COLORS[filing.tax_type]?.bg || 'bg-slate-border/30',
                                  TAX_TYPE_COLORS[filing.tax_type]?.text || 'text-slate-muted'
                                )}>
                                  {filing.tax_type}
                                </span>
                                <span className="text-white font-medium">{filing.period}</span>
                              </div>
                              <p className="text-slate-muted text-sm mt-1">{filing.description}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-white text-sm font-medium">{formatDateLong(filing.deadline)}</p>
                            <p className={cn(
                              'text-sm',
                              filing.status === 'FILED'
                                ? 'text-emerald-400'
                                : filing.days_until_due < 0
                                ? 'text-red-400'
                                : filing.days_until_due <= 7
                                ? 'text-amber-400'
                                : 'text-slate-muted'
                            )}>
                              {filing.status === 'FILED'
                                ? 'Filed'
                                : filing.days_until_due < 0
                                ? `${Math.abs(filing.days_until_due)} days overdue`
                                : filing.days_until_due === 0
                                ? 'Due today'
                                : `${filing.days_until_due} days remaining`}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })()
      )}

      {/* Filing Schedule Reference */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-teal-electric" />
          Standard Filing Schedule
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 bg-slate-elevated rounded-lg">
              <span className="text-blue-400 text-sm">VAT</span>
              <span className="text-slate-muted text-sm">21st of following month</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-slate-elevated rounded-lg">
              <span className="text-amber-400 text-sm">WHT</span>
              <span className="text-slate-muted text-sm">21st of following month</span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 bg-slate-elevated rounded-lg">
              <span className="text-emerald-400 text-sm">PAYE</span>
              <span className="text-slate-muted text-sm">10th of following month</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-slate-elevated rounded-lg">
              <span className="text-purple-400 text-sm">CIT</span>
              <span className="text-slate-muted text-sm">6 months after year-end</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
