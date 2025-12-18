"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventoryWarehouses } from "@/hooks/useApi";
import { Warehouse, Plus, Search, Loader2, AlertCircle, Building2, FolderTree } from "lucide-react";
import { cn } from "@/lib/utils";

export default function InventoryWarehousesPage() {
  const [includeDisabled, setIncludeDisabled] = useState(false);
  const [isGroupFilter, setIsGroupFilter] = useState<boolean | undefined>(undefined);
  const { data, isLoading, error } = useInventoryWarehouses({
    include_disabled: includeDisabled,
    is_group: isGroupFilter,
    limit: 100,
  });

  const warehouses = data?.warehouses || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Warehouses</h1>
          <p className="text-slate-muted text-sm">Manage storage locations</p>
        </div>
        <Link
          href="/inventory/warehouses/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Warehouse
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsGroupFilter(isGroupFilter === true ? undefined : true)}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors",
                isGroupFilter === true
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                  : "border-slate-border text-slate-muted hover:text-white hover:bg-slate-elevated"
              )}
            >
              <FolderTree className="w-4 h-4" />
              Groups Only
            </button>
            <button
              onClick={() => setIsGroupFilter(isGroupFilter === false ? undefined : false)}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors",
                isGroupFilter === false
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                  : "border-slate-border text-slate-muted hover:text-white hover:bg-slate-elevated"
              )}
            >
              <Warehouse className="w-4 h-4" />
              Leaf Only
            </button>
            <button
              onClick={() => setIncludeDisabled(!includeDisabled)}
              className={cn(
                "px-3 py-2 rounded-lg border text-sm transition-colors",
                includeDisabled
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                  : "border-slate-border text-slate-muted hover:text-white hover:bg-slate-elevated"
              )}
            >
              Include Disabled
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading warehouses...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load warehouses: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && warehouses.length === 0 && (
          <div className="text-center py-12">
            <Warehouse className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No warehouses found</p>
            <Link
              href="/inventory/warehouses/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create your first warehouse
            </Link>
          </div>
        )}

        {!isLoading && !error && warehouses.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Warehouse Name</th>
                  <th className="pb-3 font-medium">Parent</th>
                  <th className="pb-3 font-medium">Type</th>
                  <th className="pb-3 font-medium">Company</th>
                  <th className="pb-3 font-medium">Account</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {warehouses.map((wh: any) => (
                  <tr key={wh.id} className="hover:bg-slate-elevated/50 transition-colors">
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        {wh.is_group ? (
                          <FolderTree className="w-4 h-4 text-amber-400" />
                        ) : (
                          <Warehouse className="w-4 h-4 text-slate-muted" />
                        )}
                        <span className="text-white font-medium">{wh.warehouse_name}</span>
                      </div>
                    </td>
                    <td className="py-3 text-slate-muted">{wh.parent_warehouse || "-"}</td>
                    <td className="py-3">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-xs",
                        wh.is_group
                          ? "bg-blue-500/20 text-blue-300"
                          : "bg-slate-elevated text-slate-muted"
                      )}>
                        {wh.is_group ? "Group" : "Storage"}
                      </span>
                    </td>
                    <td className="py-3 text-slate-muted">{wh.company || "-"}</td>
                    <td className="py-3 text-slate-muted font-mono text-xs">{wh.account || "-"}</td>
                    <td className="py-3">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-xs",
                        wh.disabled
                          ? "bg-red-500/20 text-red-300"
                          : "bg-emerald-500/20 text-emerald-300"
                      )}>
                        {wh.disabled ? "Disabled" : "Active"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && (
          <div className="pt-4 border-t border-slate-border/50 text-sm text-slate-muted">
            Showing {warehouses.length} of {data.total} warehouses
          </div>
        )}
      </div>
    </div>
  );
}
