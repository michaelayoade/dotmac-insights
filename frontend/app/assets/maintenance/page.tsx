"use client";

import Link from "next/link";
import {
  Wrench,
  RefreshCw,
  CheckCircle,
  MapPin,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { useMaintenanceDue, useAssetMutations } from "@/hooks/useApi";
import type { MaintenanceDueAsset } from "@/lib/api";

export default function MaintenanceDuePage() {
  const { data, isLoading, mutate } = useMaintenanceDue();
  const { completeMaintenance } = useAssetMutations();

  const maintenanceAssets: MaintenanceDueAsset[] = data?.assets ?? [];

  const handleComplete = async (assetId: number) => {
    try {
      await completeMaintenance(assetId);
      mutate();
    } catch (error) {
      console.error("Failed to complete maintenance:", error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Maintenance Due</h1>
          <p className="text-sm text-slate-muted mt-1">
            Assets requiring or currently in maintenance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => mutate()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 bg-slate-elevated hover:bg-slate-border/50 rounded-lg text-sm text-slate-muted hover:text-white transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Assets Requiring Maintenance</p>
          <p className="text-2xl font-bold text-amber-400">{maintenanceAssets.length}</p>
        </div>
        <Link
          href="/assets/maintenance/warranty"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 transition-colors"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-muted">Warranty Expiring</p>
              <p className="text-lg font-bold text-white">Check Alerts</p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-muted" />
          </div>
        </Link>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-muted" />
          <p className="text-slate-muted">Loading maintenance queue...</p>
        </div>
      ) : maintenanceAssets.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <CheckCircle className="w-8 h-8 mx-auto mb-3 text-emerald-400" />
          <p className="font-medium text-white">No Maintenance Due</p>
          <p className="text-sm text-slate-muted mt-1">All assets are in good standing</p>
        </div>
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-border bg-slate-elevated/50">
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Asset</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Location</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Status</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Value</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {maintenanceAssets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-slate-elevated/30 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/assets/list/${asset.id}`}
                        className="font-medium text-white hover:text-indigo-300 transition-colors"
                      >
                        {asset.asset_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {asset.asset_category || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-slate-muted">
                        <MapPin className="w-3 h-3" />
                        {asset.location || "-"}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-amber-500/20 text-amber-400">
                        Maintenance Due
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-white">
                      {formatCurrency(asset.asset_value ?? 0)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleComplete(asset.id)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-lg text-xs font-medium transition-colors"
                        >
                          <CheckCircle className="w-3 h-3" />
                          Complete
                        </button>
                        <Link
                          href={`/assets/list/${asset.id}`}
                          className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          View
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="font-semibold text-white mb-4">Related</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Link
            href="/assets/maintenance/warranty"
            className="flex items-center justify-between p-3 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <span className="text-sm text-slate-muted">Expiring Warranties</span>
            <ArrowRight className="w-4 h-4 text-slate-muted" />
          </Link>
          <Link
            href="/assets/maintenance/insurance"
            className="flex items-center justify-between p-3 bg-slate-elevated hover:bg-slate-border/30 rounded-lg transition-colors"
          >
            <span className="text-sm text-slate-muted">Expiring Insurance</span>
            <ArrowRight className="w-4 h-4 text-slate-muted" />
          </Link>
        </div>
      </div>
    </div>
  );
}
