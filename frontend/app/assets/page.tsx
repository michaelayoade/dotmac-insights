"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Building2,
  TrendingDown,
  Wrench,
  Shield,
  AlertTriangle,
  Package,
  Calendar,
  Clock,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { cn, formatCurrency } from "@/lib/utils";
import {
  useAssetsSummary,
  usePendingDepreciation,
  useMaintenanceDue,
  useWarrantyExpiring,
  useInsuranceExpiring,
} from "@/hooks/useApi";

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color,
  href,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: "indigo" | "emerald" | "amber" | "coral" | "purple";
  href?: string;
}) {
  const colorClasses = {
    indigo: "from-indigo-500 to-purple-400 text-indigo-300",
    emerald: "from-emerald-500 to-teal-400 text-emerald-300",
    amber: "from-amber-500 to-orange-400 text-amber-300",
    coral: "from-coral-alert to-red-400 text-coral-alert",
    purple: "from-purple-500 to-pink-400 text-purple-300",
  };

  const content = (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm text-slate-muted">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="text-xs text-slate-muted">{subtitle}</p>}
        </div>
        <div className={cn("p-3 rounded-xl bg-gradient-to-br", colorClasses[color].split(" ").slice(0, 2).join(" "))}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
}

function AlertCard({
  title,
  count,
  items,
  href,
  emptyText,
  renderItem,
}: {
  title: string;
  count: number;
  items: any[];
  href: string;
  emptyText: string;
  renderItem: (item: any) => React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">{title}</h3>
          {count > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-coral-alert/20 text-coral-alert rounded-full">
              {count}
            </span>
          )}
        </div>
        <Link href={href} className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
          View all <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-muted py-4 text-center">{emptyText}</p>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 5).map(renderItem)}
        </div>
      )}
    </div>
  );
}

export default function AssetsDashboard() {
  const { data: summary, isLoading: summaryLoading, mutate: refreshSummary } = useAssetsSummary();
  const { data: pendingDep, isLoading: pendingLoading } = usePendingDepreciation();
  const { data: maintenanceDue, isLoading: maintenanceLoading } = useMaintenanceDue();
  const { data: warrantyExpiring, isLoading: warrantyLoading } = useWarrantyExpiring(30);
  const { data: insuranceExpiring, isLoading: insuranceLoading } = useInsuranceExpiring(30);

  const isLoading = summaryLoading || pendingLoading || maintenanceLoading || warrantyLoading || insuranceLoading;

  const handleRefresh = () => {
    refreshSummary();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Asset Dashboard</h1>
          <p className="text-sm text-slate-muted mt-1">Overview of fixed assets, depreciation, and maintenance</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border/50 rounded-lg text-sm text-slate-muted hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Assets"
          value={summary?.totals?.count ?? 0}
          subtitle={`${summary?.by_status?.find(s => s.status === 'submitted')?.count ?? 0} active`}
          icon={Building2}
          color="indigo"
          href="/assets/list"
        />
        <StatCard
          title="Total Value"
          value={formatCurrency(summary?.totals?.purchase_value ?? 0)}
          subtitle="Gross purchase amount"
          icon={Package}
          color="emerald"
        />
        <StatCard
          title="Book Value"
          value={formatCurrency(summary?.totals?.book_value ?? 0)}
          subtitle="After depreciation"
          icon={TrendingDown}
          color="purple"
        />
        <StatCard
          title="Accumulated Depreciation"
          value={formatCurrency(summary?.totals?.accumulated_depreciation ?? 0)}
          subtitle="Total depreciated"
          icon={Calendar}
          color="amber"
        />
      </div>

      {/* Status Breakdown */}
      {summary?.by_status && summary.by_status.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-white mb-4">Assets by Status</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {summary.by_status.map((item) => (
              <div key={item.status} className="bg-slate-elevated rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-white">{item.count}</p>
                <p className="text-xs text-slate-muted capitalize">{item.status.replace(/_/g, " ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Depreciation */}
        <AlertCard
          title="Pending Depreciation"
          count={pendingDep?.count ?? 0}
          items={pendingDep?.pending_entries ?? []}
          href="/assets/depreciation/pending"
          emptyText="No pending depreciation entries"
          renderItem={(item) => (
            <div key={item.asset_id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-white">{item.asset_name}</p>
                <p className="text-xs text-slate-muted">{item.schedule_date}</p>
              </div>
              <span className="text-sm font-medium text-amber-300">
                {formatCurrency(item.depreciation_amount)}
              </span>
            </div>
          )}
        />

        {/* Maintenance Due */}
        <AlertCard
          title="Maintenance Due"
          count={maintenanceDue?.count ?? 0}
          items={maintenanceDue?.assets ?? []}
          href="/assets/maintenance"
          emptyText="No maintenance due"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-white">{item.asset_name}</p>
                <p className="text-xs text-slate-muted">{item.location ?? "No location"}</p>
              </div>
              <Wrench className="w-4 h-4 text-amber-300" />
            </div>
          )}
        />

        {/* Warranty Expiring */}
        <AlertCard
          title="Warranty Expiring (30 days)"
          count={warrantyExpiring?.count ?? 0}
          items={warrantyExpiring?.assets ?? []}
          href="/assets/maintenance/warranty"
          emptyText="No warranties expiring soon"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-white">{item.asset_name}</p>
                <p className="text-xs text-slate-muted">Expires: {item.warranty_expiry_date}</p>
              </div>
              <span className="text-xs px-2 py-1 bg-coral-alert/20 text-coral-alert rounded-full">
                {item.days_remaining} days
              </span>
            </div>
          )}
        />

        {/* Insurance Expiring */}
        <AlertCard
          title="Insurance Expiring (30 days)"
          count={insuranceExpiring?.count ?? 0}
          items={insuranceExpiring?.assets ?? []}
          href="/assets/maintenance/insurance"
          emptyText="No insurance expiring soon"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-white">{item.asset_name}</p>
                <p className="text-xs text-slate-muted">Expires: {item.insurance_end_date}</p>
              </div>
              <span className="text-xs px-2 py-1 bg-coral-alert/20 text-coral-alert rounded-full">
                {item.days_remaining} days
              </span>
            </div>
          )}
        />
      </div>

      {/* Quick Actions */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="font-semibold text-white mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Link
            href="/assets/list?status=draft"
            className="flex flex-col items-center gap-2 p-4 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <Clock className="w-6 h-6 text-slate-muted" />
            <span className="text-sm text-slate-muted text-center">Draft Assets</span>
          </Link>
          <Link
            href="/assets/depreciation"
            className="flex flex-col items-center gap-2 p-4 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <TrendingDown className="w-6 h-6 text-slate-muted" />
            <span className="text-sm text-slate-muted text-center">Depreciation</span>
          </Link>
          <Link
            href="/assets/maintenance"
            className="flex flex-col items-center gap-2 p-4 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <Wrench className="w-6 h-6 text-slate-muted" />
            <span className="text-sm text-slate-muted text-center">Maintenance</span>
          </Link>
          <Link
            href="/assets/categories"
            className="flex flex-col items-center gap-2 p-4 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <Package className="w-6 h-6 text-slate-muted" />
            <span className="text-sm text-slate-muted text-center">Categories</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
