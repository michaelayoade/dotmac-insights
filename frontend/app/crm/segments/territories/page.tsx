'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  MapPin,
  DollarSign,
  Users,
  TrendingUp,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import useSWR from 'swr';
import { apiFetch } from '@/hooks/useApi';
import { ErrorDisplay } from '@/components/insights/shared';
import { LoadingState, PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/lib/design-tokens';
import { FilterInput } from '@/components/ui';
import { formatCurrency } from '@/lib/formatters';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

interface TerritoryData {
  territory: string;
  count: number;
  mrr: number;
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

export default function CRMTerritoriesPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const router = useRouter();
  const [search, setSearch] = useState('');
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error, mutate } = useSWR<{ territories: TerritoryData[] }>(
    canFetch ? '/contacts/analytics/by-territory?limit=50' : null,
    apiFetch
  );

  const territories = data?.territories || [];

  // Filter by search
  const filteredTerritories = territories.filter((t) =>
    t.territory.toLowerCase().includes(search.toLowerCase())
  );

  // Stats
  const totalContacts = territories.reduce((sum, t) => sum + t.count, 0);
  const totalMrr = territories.reduce((sum, t) => sum + t.mrr, 0);
  const avgPerTerritory = territories.length > 0 ? Math.round(totalContacts / territories.length) : 0;

  // Chart data (top 10)
  const chartData = filteredTerritories.slice(0, 10).map((t) => ({
    name: t.territory.length > 15 ? t.territory.substring(0, 15) + '...' : t.territory,
    contacts: t.count,
    mrr: t.mrr,
  }));

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view territories."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load territories"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Territories"
        subtitle="Contact distribution by geographic region"
        icon={MapPin}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <MapPin className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{territories.length}</p>
              <p className="text-xs text-slate-muted">Territories</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Users className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{totalContacts}</p>
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
              <p className="text-2xl font-bold text-foreground">{formatCurrency(totalMrr)}</p>
              <p className="text-xs text-slate-muted">Total MRR</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <TrendingUp className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{avgPerTerritory}</p>
              <p className="text-xs text-slate-muted">Avg per Territory</p>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-5">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-4 h-4 text-emerald-400" />
          <h3 className="text-foreground font-semibold">Top Territories by Contacts</h3>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
              <XAxis type="number" stroke={CHART_COLORS.axis} fontSize={12} />
              <YAxis type="category" dataKey="name" stroke={CHART_COLORS.axis} fontSize={12} width={100} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="contacts" fill={CHART_COLORS.palette[0]} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[300px] flex items-center justify-center text-slate-muted text-sm">
            No territory data
          </div>
        )}
      </div>

      {/* Search and List */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-4 mb-4">
          <FilterInput
            type="text"
            placeholder="Search territories..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 max-w-md"
          />
        </div>

        <div className="divide-y divide-slate-border">
          {filteredTerritories.map((territory) => (
            <Link
              key={territory.territory}
              href={`/crm/contacts/all?territory=${encodeURIComponent(territory.territory)}`}
              className="flex items-center justify-between py-3 hover:bg-slate-elevated/50 px-2 rounded-lg transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-foreground font-medium">{territory.territory}</p>
                  <p className="text-sm text-slate-muted">{territory.count} contacts</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-foreground font-mono">{formatCurrency(territory.mrr)}</p>
                  <p className="text-xs text-slate-muted">MRR</p>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-emerald-400 transition-colors" />
              </div>
            </Link>
          ))}
          {filteredTerritories.length === 0 && (
            <div className="py-8 text-center text-slate-muted">
              {search ? 'No territories match your search' : 'No territories found'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
