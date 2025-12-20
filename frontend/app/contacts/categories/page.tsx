'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  FolderOpen,
  Building2,
  Home,
  Landmark,
  Heart,
  Users,
  DollarSign,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';
import useSWR from 'swr';
import { apiFetch } from '@/hooks/useApi';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/lib/design-tokens';

interface CategoryData {
  total: number;
  mrr: number;
  by_type: Record<string, number>;
}

interface CategoriesResponse {
  by_category: Record<string, CategoryData>;
}

const categoryConfig: Record<string, { icon: typeof Building2; color: string; label: string }> = {
  residential: { icon: Home, color: 'blue', label: 'Residential' },
  business: { icon: Building2, color: 'violet', label: 'Business' },
  enterprise: { icon: Landmark, color: 'amber', label: 'Enterprise' },
  government: { icon: Landmark, color: 'emerald', label: 'Government' },
  non_profit: { icon: Heart, color: 'rose', label: 'Non-Profit' },
};

function formatCurrency(value: number | null | undefined, currency = 'NGN'): string {
  if (value === null || value === undefined) return '\u20A60';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

export default function CategoriesPage() {
  const { data, isLoading, error, mutate } = useSWR<CategoriesResponse>(
    '/contacts/analytics/by-category',
    apiFetch
  );

  const categories = data?.by_category || {};
  const categoryList = Object.entries(categories).map(([key, value]) => ({
    key,
    ...value,
    config: categoryConfig[key] || { icon: FolderOpen, color: 'slate', label: key },
  }));

  // Stats
  const totalContacts = categoryList.reduce((sum, c) => sum + c.total, 0);
  const totalMrr = categoryList.reduce((sum, c) => sum + c.mrr, 0);

  // Pie chart data
  const pieData = categoryList.map((cat, idx) => ({
    name: cat.config.label,
    value: cat.total,
    color: CHART_COLORS.palette[idx % CHART_COLORS.palette.length],
  }));

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load categories"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Categories"
        subtitle="Contact distribution by category"
        icon={FolderOpen}
        iconClassName="bg-amber-500/10 border border-amber-500/30"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <FolderOpen className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{categoryList.length}</p>
              <p className="text-xs text-slate-muted">Categories</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Users className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{totalContacts}</p>
              <p className="text-xs text-slate-muted">Total Contacts</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <DollarSign className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{formatCurrency(totalMrr)}</p>
              <p className="text-xs text-slate-muted">Total MRR</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <BarChart3 className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">
                {categoryList.length > 0 ? formatCurrency(totalMrr / categoryList.length) : '-'}
              </p>
              <p className="text-xs text-slate-muted">Avg MRR/Category</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Distribution Pie */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Contact Distribution</h3>
          </div>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
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
                  wrapperStyle={{ paddingTop: '10px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-slate-muted text-sm">
              No category data
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <FolderOpen className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">Category Breakdown</h3>
          </div>
          <div className="space-y-3">
            {categoryList.map((cat) => {
              const Icon = cat.config.icon;
              const percentage = totalContacts > 0 ? Math.round((cat.total / totalContacts) * 100) : 0;
              return (
                <div key={cat.key} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className={`w-4 h-4 text-${cat.config.color}-400`} />
                      <span className="text-sm text-white">{cat.config.label}</span>
                    </div>
                    <span className="text-sm text-slate-muted">{cat.total} ({percentage}%)</span>
                  </div>
                  <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
                    <div
                      className={`h-full bg-${cat.config.color}-500 transition-all duration-500`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Category Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {categoryList.map((cat) => {
          const Icon = cat.config.icon;
          const bgColor = `bg-${cat.config.color}-500/20`;
          const borderColor = `border-${cat.config.color}-500/30`;
          const textColor = `text-${cat.config.color}-400`;

          return (
            <Link
              key={cat.key}
              href={`/contacts?category=${cat.key}`}
              className="bg-slate-card rounded-xl border border-slate-border p-5 hover:border-slate-muted transition-colors group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className={cn('p-3 rounded-xl', bgColor, borderColor, 'border')}>
                  <Icon className={cn('w-6 h-6', textColor)} />
                </div>
                <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-white transition-colors" />
              </div>
              <h3 className="text-white font-semibold text-lg mb-1">{cat.config.label}</h3>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-muted">
                  <span className="text-white font-semibold">{cat.total}</span> contacts
                </span>
                <span className="text-slate-muted">
                  <span className={cn('font-semibold', textColor)}>{formatCurrency(cat.mrr)}</span> MRR
                </span>
              </div>
              {cat.by_type && Object.keys(cat.by_type).length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-border">
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(cat.by_type).map(([type, count]) => (
                      <span key={type} className="px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                        {type}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
