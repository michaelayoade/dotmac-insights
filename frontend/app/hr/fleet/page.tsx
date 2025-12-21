'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Car,
  Fuel,
  Shield,
  AlertTriangle,
  Users,
  DollarSign,
  Gauge,
  Search,
  Filter,
  ChevronRight,
  Calendar,
  MapPin,
  CheckCircle2,
  XCircle,
  TrendingUp,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';
import {
  useFleetVehicles,
  useFleetSummary,
  useFleetInsuranceExpiring,
  useFleetMakes,
  useFleetFuelTypes,
} from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn } from '@/lib/utils';
import type { Vehicle } from '@/lib/api/domains/fleet';
import { CHART_COLORS } from '@/lib/design-tokens';

function formatCurrency(value: number | null | undefined, currency = 'NGN'): string {
  if (value === null || value === undefined) return '\u20A60';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function daysUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = date.getTime() - today.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  bgClass?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, colorClass = 'text-teal-electric', bgClass = 'bg-slate-card' }: StatCardProps) {
  return (
    <div className={cn('rounded-xl border border-slate-border p-5', bgClass)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{title}</p>
          <p className={cn('text-2xl font-bold mt-1', colorClass)}>{value}</p>
          {subtitle && <p className="text-slate-muted text-xs mt-1">{subtitle}</p>}
        </div>
        <div className={cn('p-3 rounded-xl bg-slate-elevated')}>
          <Icon className={cn('w-5 h-5', colorClass)} />
        </div>
      </div>
    </div>
  );
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

export default function FleetPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [makeFilter, setMakeFilter] = useState('');
  const [fuelFilter, setFuelFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('');

  const { data: vehiclesData, isLoading, error, mutate } = useFleetVehicles({
    page,
    page_size: pageSize,
    search: search || undefined,
    make: makeFilter || undefined,
    fuel_type: fuelFilter || undefined,
    is_active: activeFilter === '' ? undefined : activeFilter === 'active',
  });

  const { data: summary, isLoading: summaryLoading } = useFleetSummary();
  const { data: expiringInsurance } = useFleetInsuranceExpiring(30) as { data?: Vehicle[] };
  const { data: makes } = useFleetMakes() as { data?: string[] };
  const { data: fuelTypes } = useFleetFuelTypes() as { data?: string[] };

  const vehicles = vehiclesData?.items || [];
  const total = vehiclesData?.total || 0;

  // Prepare pie chart data for fuel types
  const fuelTypeChartData = useMemo(() => {
    if (!summary?.by_fuel_type) return [];
    return Object.entries(summary.by_fuel_type).map(([name, count], idx) => ({
      name: name || 'Unknown',
      value: count,
      color: CHART_COLORS.palette[idx % CHART_COLORS.palette.length],
    }));
  }, [summary]);

  // Prepare pie chart data for makes
  const makeChartData = useMemo(() => {
    if (!summary?.by_make) return [];
    return Object.entries(summary.by_make).slice(0, 5).map(([name, count], idx) => ({
      name: name || 'Unknown',
      value: count,
      color: CHART_COLORS.palette[idx % CHART_COLORS.palette.length],
    }));
  }, [summary]);

  const columns = [
    {
      key: 'license_plate',
      header: 'Vehicle',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-slate-elevated flex items-center justify-center">
            <Car className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <p className="text-white font-semibold">{item.license_plate}</p>
            <p className="text-slate-muted text-xs">
              {[item.make, item.model, item.model_year].filter(Boolean).join(' ') || 'Unknown'}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: 'driver',
      header: 'Driver',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-slate-muted" />
          <span className="text-slate-300">{item.driver_name || '-'}</span>
        </div>
      ),
    },
    {
      key: 'fuel_type',
      header: 'Fuel',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Fuel className="w-4 h-4 text-slate-muted" />
          <span className="text-slate-300">{item.fuel_type || '-'}</span>
        </div>
      ),
    },
    {
      key: 'odometer_value',
      header: 'Odometer',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <span className="font-mono text-white">{formatNumber(item.odometer_value)}</span>
          <span className="text-slate-muted text-xs ml-1">{item.uom || 'km'}</span>
        </div>
      ),
    },
    {
      key: 'insurance',
      header: 'Insurance',
      render: (item: any) => {
        const days = daysUntil(item.insurance_end_date);
        if (days === null) {
          return <span className="text-slate-muted">-</span>;
        }
        const isExpiring = days <= 30 && days >= 0;
        const isExpired = days < 0;
        return (
          <div className="flex items-center gap-2">
            <Shield className={cn(
              'w-4 h-4',
              isExpired ? 'text-red-400' : isExpiring ? 'text-amber-400' : 'text-emerald-400'
            )} />
            <span className={cn(
              'text-xs',
              isExpired ? 'text-red-400' : isExpiring ? 'text-amber-400' : 'text-slate-300'
            )}>
              {isExpired ? `Expired ${Math.abs(days)}d ago` : `${days}d left`}
            </span>
          </div>
        );
      },
    },
    {
      key: 'location',
      header: 'Location',
      render: (item: any) => item.location ? (
        <div className="flex items-center gap-1">
          <MapPin className="w-3 h-3 text-slate-muted" />
          <span className="text-slate-300 text-sm truncate max-w-[120px]">{item.location}</span>
        </div>
      ) : <span className="text-slate-muted">-</span>,
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (item: any) => (
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
          item.is_active
            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
            : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
        )}>
          {item.is_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {item.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
  ];

  if (isLoading && !vehiclesData) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load fleet data"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      {/* Header */}
      <div className="bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-slate-card border border-amber-500/20 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
            <Car className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Fleet Management</h1>
            <p className="text-slate-muted text-sm">Vehicle tracking, insurance, and driver assignments</p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Vehicles"
            value={formatNumber(summary?.total_vehicles)}
            icon={Car}
            colorClass="text-amber-400"
          />
          <StatCard
            title="Active"
            value={formatNumber(summary?.active_vehicles)}
            subtitle={`${summary?.inactive_vehicles || 0} inactive`}
            icon={CheckCircle2}
            colorClass="text-emerald-400"
          />
          <StatCard
            title="Insurance Expiring"
            value={formatNumber(summary?.insurance_expiring_soon)}
            subtitle="Within 30 days"
            icon={AlertTriangle}
            colorClass={summary?.insurance_expiring_soon ? 'text-amber-400' : 'text-slate-muted'}
          />
          <StatCard
            title="Fleet Value"
            value={formatCurrency(summary?.total_value)}
            icon={DollarSign}
            colorClass="text-violet-400"
          />
          <StatCard
            title="Avg Odometer"
            value={`${formatNumber(summary?.avg_odometer)} km`}
            icon={Gauge}
            colorClass="text-cyan-400"
          />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Fuel Type Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Fuel className="w-4 h-4 text-amber-400" />
            <h3 className="text-white font-semibold">By Fuel Type</h3>
          </div>
          {fuelTypeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={fuelTypeChartData}
                  cx="50%"
                  cy="45%"
                  innerRadius={35}
                  outerRadius={60}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {fuelTypeChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: '8px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">
              No fuel type data
            </div>
          )}
        </div>

        {/* Make Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Car className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Top Makes</h3>
          </div>
          {makeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={makeChartData}
                  cx="50%"
                  cy="45%"
                  innerRadius={35}
                  outerRadius={60}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {makeChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: '8px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-muted text-sm">
              No make data
            </div>
          )}
        </div>

        {/* Insurance Expiring Soon */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-400" />
              <h3 className="text-white font-semibold">Insurance Alerts</h3>
            </div>
            {(expiringInsurance?.length || 0) > 0 && (
              <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded-full text-xs font-medium">
                {expiringInsurance?.length} expiring
              </span>
            )}
          </div>
          <div className="space-y-2 max-h-[180px] overflow-y-auto">
            {expiringInsurance && expiringInsurance.length > 0 ? (
              expiringInsurance.slice(0, 5).map((vehicle: Vehicle) => {
                const days = daysUntil(vehicle.insurance_end_date);
                return (
                  <Link
                    key={vehicle.id}
                    href={`/hr/fleet/${vehicle.id}`}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-elevated transition-colors group"
                  >
                    <div className="flex items-center gap-2">
                      <Car className="w-4 h-4 text-slate-muted" />
                      <div>
                        <p className="text-white text-sm font-medium">{vehicle.license_plate}</p>
                        <p className="text-slate-muted text-xs">{vehicle.make} {vehicle.model}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'text-xs font-medium',
                        days !== null && days <= 7 ? 'text-red-400' : 'text-amber-400'
                      )}>
                        {days !== null ? `${days}d` : '-'}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-muted group-hover:text-white transition-colors" />
                    </div>
                  </Link>
                );
              })
            ) : (
              <div className="flex flex-col items-center justify-center h-[160px] text-slate-muted">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
                <p className="text-sm">No insurance alerts</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-amber-400" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search vehicles..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <select
            value={makeFilter}
            onChange={(e) => { setMakeFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            <option value="">All Makes</option>
            {makes?.map((make: string) => (
              <option key={make} value={make}>{make}</option>
            ))}
          </select>
          <select
            value={fuelFilter}
            onChange={(e) => { setFuelFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            <option value="">All Fuel Types</option>
            {fuelTypes?.map((fuel: string) => (
              <option key={fuel} value={fuel}>{fuel}</option>
            ))}
          </select>
          <select
            value={activeFilter}
            onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          {(search || makeFilter || fuelFilter || activeFilter) && (
            <button
              onClick={() => {
                setSearch('');
                setMakeFilter('');
                setFuelFilter('');
                setActiveFilter('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Vehicles Table */}
      <DataTable
        columns={columns}
        data={vehicles}
        keyField="id"
        loading={isLoading}
        emptyMessage="No vehicles found"
        onRowClick={(item) => router.push(`/hr/fleet/${item.id}`)}
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
