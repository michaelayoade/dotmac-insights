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
import { AccentStatCard } from "@/components/StatCard";
import {
  useAssetsSummary,
  usePendingDepreciation,
  useMaintenanceDue,
  useWarrantyExpiring,
  useInsuranceExpiring,
} from "@/hooks/useApi";
import { Button } from "@/components/ui";
import type {
  AssetSummaryResponse,
  PendingDepreciationEntry,
  MaintenanceDueAsset,
  WarrantyExpiringAsset,
  InsuranceExpiringAsset,
} from "@/lib/api";


function AlertCard<T>({
  title,
  count,
  items,
  href,
  emptyText,
  renderItem,
}: {
  title: string;
  count: number;
  items: T[];
  href: string;
  emptyText: string;
  renderItem: (item: T) => React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-foreground">{title}</h3>
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

  const summaryData: AssetSummaryResponse | undefined = summary;
  const pendingEntries: PendingDepreciationEntry[] = pendingDep?.pending_entries ?? [];
  const maintenanceAssets: MaintenanceDueAsset[] = maintenanceDue?.assets ?? [];
  const warrantyAssets: WarrantyExpiringAsset[] = warrantyExpiring?.assets ?? [];
  const insuranceAssets: InsuranceExpiringAsset[] = insuranceExpiring?.assets ?? [];

  const isLoading = summaryLoading || pendingLoading || maintenanceLoading || warrantyLoading || insuranceLoading;

  const handleRefresh = () => {
    refreshSummary();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Asset Dashboard</h1>
          <p className="text-sm text-slate-muted mt-1">Overview of fixed assets, depreciation, and maintenance</p>
        </div>
        <Button
          onClick={handleRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border/50 rounded-lg text-sm text-slate-muted hover:text-foreground transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <AccentStatCard
          title="Total Assets"
          value={summaryData?.totals?.count ?? 0}
          subtitle={`${summaryData?.by_status?.find((s) => s.status === 'submitted')?.count ?? 0} active`}
          icon={Building2}
          accent="indigo"
          gradient
          href="/assets/list"
        />
        <AccentStatCard
          title="Total Value"
          value={formatCurrency(summaryData?.totals?.purchase_value ?? 0)}
          subtitle="Gross purchase amount"
          icon={Package}
          accent="emerald"
          gradient
        />
        <AccentStatCard
          title="Book Value"
          value={formatCurrency(summaryData?.totals?.book_value ?? 0)}
          subtitle="After depreciation"
          icon={TrendingDown}
          accent="purple"
          gradient
        />
        <AccentStatCard
          title="Accumulated Depreciation"
          value={formatCurrency(summaryData?.totals?.accumulated_depreciation ?? 0)}
          subtitle="Total depreciated"
          icon={Calendar}
          accent="amber"
          gradient
        />
      </div>

      {/* Status Breakdown */}
      {summaryData?.by_status && summaryData.by_status.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Assets by Status</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {summaryData.by_status.map((item) => (
              <div key={item.status} className="bg-slate-elevated rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-foreground">{item.count}</p>
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
          items={pendingEntries}
          href="/assets/depreciation/pending"
          emptyText="No pending depreciation entries"
          renderItem={(item) => (
            <div key={item.asset_id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-foreground">{item.asset_name}</p>
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
          items={maintenanceAssets}
          href="/assets/maintenance"
          emptyText="No maintenance due"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-foreground">{item.asset_name}</p>
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
          items={warrantyAssets}
          href="/assets/maintenance/warranty"
          emptyText="No warranties expiring soon"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-foreground">{item.asset_name}</p>
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
          items={insuranceAssets}
          href="/assets/maintenance/insurance"
          emptyText="No insurance expiring soon"
          renderItem={(item) => (
            <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg">
              <div>
                <p className="text-sm font-medium text-foreground">{item.asset_name}</p>
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
        <h3 className="font-semibold text-foreground mb-4">Quick Actions</h3>
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
