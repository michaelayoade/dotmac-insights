"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventoryReorderAlerts } from "@/hooks/useApi";
import {
  AlertTriangle,
  Bell,
  Loader2,
  AlertCircle,
  Package,
  Warehouse,
  ShoppingCart,
  TrendingDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function ReorderPage() {
  const { data, isLoading, error } = useInventoryReorderAlerts({ limit: 100 });

  const alerts = data?.alerts || [];

  const getStockLevel = (currentQty: number, reorderLevel: number, safetyStock: number) => {
    if (currentQty <= safetyStock) {
      return { label: "Critical", className: "bg-red-500/20 text-red-300", icon: AlertTriangle };
    }
    if (currentQty <= reorderLevel) {
      return { label: "Low", className: "bg-amber-500/20 text-amber-300", icon: TrendingDown };
    }
    return { label: "Normal", className: "bg-emerald-500/20 text-emerald-300", icon: Package };
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Reorder Alerts</h1>
        <p className="text-slate-muted text-sm">Items below reorder level that need restocking</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/20">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a: any) => (a.current_stock ?? 0) <= (a.safety_stock ?? 0)).length}
              </p>
              <p className="text-xs text-slate-muted">Critical (below safety stock)</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20">
              <TrendingDown className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a: any) => (a.current_stock ?? 0) > (a.safety_stock ?? 0)).length}
              </p>
              <p className="text-xs text-slate-muted">Low (below reorder level)</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-elevated">
              <Package className="w-5 h-5 text-slate-muted" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{alerts.length}</p>
              <p className="text-xs text-slate-muted">Total items needing reorder</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading reorder alerts...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load reorder alerts: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && alerts.length === 0 && (
          <div className="text-center py-12">
            <Bell className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-foreground font-medium">All stock levels are healthy!</p>
            <p className="text-slate-muted text-sm mt-1">No items are below their reorder level</p>
          </div>
        )}

        {!isLoading && !error && alerts.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Item</th>
                  <th className="pb-3 font-medium">Warehouse</th>
                  <th className="pb-3 font-medium text-right">Current Qty</th>
                  <th className="pb-3 font-medium text-right">Reorder Level</th>
                  <th className="pb-3 font-medium text-right">Safety Stock</th>
                  <th className="pb-3 font-medium text-right">Reorder Qty</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {alerts.map((alert: any, idx: number) => {
                  const stockLevel = getStockLevel(
                    alert.current_stock ?? 0,
                    alert.reorder_level ?? 0,
                    alert.safety_stock ?? 0
                  );
                  const StatusIcon = stockLevel.icon;
                  return (
                    <tr key={`${alert.item_code}-${idx}`} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3">
                        <div>
                          <span className="text-amber-400 font-mono">{alert.item_code}</span>
                          {alert.item_name && (
                            <p className="text-slate-muted text-xs mt-0.5">{alert.item_name}</p>
                          )}
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2 text-slate-muted">
                          <Warehouse className="w-3 h-3" />
                          {alert.item_group || "All"}
                        </div>
                      </td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {(alert.current_stock ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-slate-muted">
                        {(alert.reorder_level ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-slate-muted">
                        {(alert.safety_stock ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {(alert.reorder_qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3">
                        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs", stockLevel.className)}>
                          <StatusIcon className="w-3 h-3" />
                          {stockLevel.label}
                        </span>
                      </td>
                      <td className="py-3">
                        <Link
                          href={`/books/accounts-payable/purchase-orders/new?item=${alert.item_code}&qty=${alert.reorder_qty || 1}`}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-amber-400 hover:bg-amber-500/20 rounded transition-colors"
                        >
                          <ShoppingCart className="w-3 h-3" />
                          Order
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
          <Bell className="w-4 h-4 text-amber-400" />
          How reorder alerts work
        </h3>
        <ul className="space-y-2 text-sm text-slate-muted">
          <li>1. Set <strong>reorder level</strong> and <strong>reorder qty</strong> on each item in Items</li>
          <li>2. System monitors stock levels across all warehouses</li>
          <li>3. Items appear here when actual qty falls below reorder level</li>
          <li>4. Click "Order" to create a purchase order for restocking</li>
        </ul>
      </div>
    </div>
  );
}
