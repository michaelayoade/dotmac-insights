"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Shield,
  RefreshCw,
  AlertTriangle,
  Calendar,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { useWarrantyExpiring } from "@/hooks/useApi";
import type { WarrantyExpiringAsset } from "@/lib/api";
import { Button, FilterCard } from '@/components/ui';

export default function WarrantyExpiringPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, mutate } = useWarrantyExpiring(days);

  const expiringAssets: WarrantyExpiringAsset[] = data?.assets ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Expiring Warranties</h1>
          <p className="text-sm text-slate-muted mt-1">
            Assets with warranties expiring soon
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => mutate()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 bg-slate-elevated hover:bg-slate-border/50 rounded-lg text-sm text-slate-muted hover:text-foreground transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <FilterCard contentClassName="flex flex-wrap items-center gap-4" iconClassName="text-indigo-400">
        <label className="text-sm text-slate-muted">Expiring within:</label>
        <div className="flex items-center gap-2">
          {[7, 14, 30, 60, 90].map((d) => (
            <Button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 py-1.5 text-sm rounded-lg transition-colors",
                days === d
                  ? "bg-indigo-500 text-foreground"
                  : "bg-slate-elevated text-slate-muted hover:text-foreground"
              )}
            >
              {d} days
            </Button>
          ))}
        </div>
      </FilterCard>

      {/* Stats */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-amber-500/20">
            <Shield className="w-5 h-5 text-amber-300" />
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">{expiringAssets.length}</p>
            <p className="text-sm text-slate-muted">warranties expiring in {days} days</p>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-muted" />
          <p className="text-slate-muted">Loading...</p>
        </div>
      ) : expiringAssets.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <Shield className="w-8 h-8 mx-auto mb-3 text-emerald-400" />
          <p className="font-medium text-foreground">No Expiring Warranties</p>
          <p className="text-sm text-slate-muted mt-1">No warranties expiring in the next {days} days</p>
        </div>
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-border bg-slate-elevated/50">
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Asset</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Supplier</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Expiry Date</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Days Left</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Serial No</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {expiringAssets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-slate-elevated/30 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/assets/list/${asset.id}`}
                        className="font-medium text-foreground hover:text-indigo-300 transition-colors"
                      >
                        {asset.asset_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {asset.asset_category || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {asset.supplier || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-slate-muted">
                        <Calendar className="w-3 h-3" />
                        {formatDate(asset.warranty_expiry_date)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          "px-2 py-1 text-xs font-medium rounded-full",
                          (asset.days_remaining ?? 0) <= 7
                            ? "bg-coral-alert/20 text-coral-alert"
                            : (asset.days_remaining ?? 0) <= 14
                            ? "bg-amber-500/20 text-amber-400"
                            : "bg-slate-500/20 text-slate-400"
                        )}
                      >
                        {asset.days_remaining ?? 0} days
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-slate-muted">
                      {asset.serial_no || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
