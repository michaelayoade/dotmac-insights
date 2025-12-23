"use client";

import Link from "next/link";
import { useInventoryStockSummary, useInventoryItems, useInventoryStockEntries, useInventoryReorderAlerts } from "@/hooks/useApi";
import {
  Boxes,
  Package,
  Warehouse,
  ClipboardList,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  Loader2,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LoadingState } from "@/components/ui";
import { useRequireScope } from "@/lib/auth-context";
import { AccessDenied } from "@/components/AccessDenied";

export default function InventoryDashboard() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope("inventory:read");
  const canFetch = !authLoading && !missingScope;

  const { data: summaryData, isLoading: summaryLoading } = useInventoryStockSummary(
    undefined,
    { isPaused: () => !canFetch }
  );
  const { data: itemsData, isLoading: itemsLoading } = useInventoryItems(
    { has_stock: true, limit: 5 },
    { isPaused: () => !canFetch }
  );
  const { data: entriesData, isLoading: entriesLoading } = useInventoryStockEntries(
    { limit: 5 },
    { isPaused: () => !canFetch }
  );
  const { data: alertsData, isLoading: alertsLoading } = useInventoryReorderAlerts(
    { limit: 10 },
    { isPaused: () => !canFetch }
  );

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the inventory:read permission to view the inventory dashboard."
        backHref="/"
        backLabel="Back to Home"
      />
    );
  }

  const totalValue = summaryData?.total_value ?? 0;
  const totalItems = summaryData?.total_items ?? 0;
  const recentItems = itemsData?.items || [];
  const recentEntries = entriesData?.entries || [];

  const quickActions = [
    { label: "New Item", href: "/inventory/items/new", icon: Package, color: "text-amber-400 bg-amber-500/10" },
    { label: "New Warehouse", href: "/inventory/warehouses/new", icon: Warehouse, color: "text-blue-400 bg-blue-500/10" },
    { label: "Stock Entry", href: "/inventory/stock-entries/new", icon: ClipboardList, color: "text-emerald-400 bg-emerald-500/10" },
    { label: "Valuation Report", href: "/inventory/valuation", icon: TrendingUp, color: "text-purple-400 bg-purple-500/10" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Inventory Dashboard</h1>
        <p className="text-slate-muted text-sm">Overview of stock, warehouses, and movements</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-muted">Total Stock Value</p>
              {summaryLoading ? (
                <Loader2 className="w-4 h-4 text-amber-500 animate-spin mt-2" />
              ) : (
                <p className="text-2xl font-bold text-foreground mt-1">
                  {totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              )}
            </div>
            <div className="p-3 rounded-xl bg-amber-500/10">
              <Boxes className="w-6 h-6 text-amber-400" />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-muted">Items in Stock</p>
              {summaryLoading ? (
                <Loader2 className="w-4 h-4 text-blue-500 animate-spin mt-2" />
              ) : (
                <p className="text-2xl font-bold text-foreground mt-1">{totalItems}</p>
              )}
            </div>
            <div className="p-3 rounded-xl bg-blue-500/10">
              <Package className="w-6 h-6 text-blue-400" />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-muted">Recent Entries</p>
              {entriesLoading ? (
                <Loader2 className="w-4 h-4 text-emerald-500 animate-spin mt-2" />
              ) : (
                <p className="text-2xl font-bold text-foreground mt-1">{entriesData?.total ?? 0}</p>
              )}
            </div>
            <div className="p-3 rounded-xl bg-emerald-500/10">
              <ClipboardList className="w-6 h-6 text-emerald-400" />
            </div>
          </div>
        </div>

        <Link href="/inventory/reorder" className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-red-500/50 transition-colors block">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-muted">Low Stock Alerts</p>
              {alertsLoading ? (
                <Loader2 className="w-4 h-4 text-red-500 animate-spin mt-2" />
              ) : (
                <>
                  <p className={cn("text-2xl font-bold mt-1", (alertsData?.total ?? 0) > 0 ? "text-red-400" : "text-foreground")}>
                    {alertsData?.total ?? 0}
                  </p>
                  {(alertsData?.total ?? 0) > 0 && (
                    <p className="text-xs text-red-400">Items need reorder</p>
                  )}
                </>
              )}
            </div>
            <div className="p-3 rounded-xl bg-red-500/10">
              <AlertTriangle className={cn("w-6 h-6", (alertsData?.total ?? 0) > 0 ? "text-red-400" : "text-slate-muted")} />
            </div>
          </div>
        </Link>
      </div>

      {/* Quick Actions */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h2 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.href}
                href={action.href}
                className={cn(
                  "flex flex-col items-center p-4 rounded-xl border border-slate-border hover:border-amber-500/50 transition-colors",
                  action.color
                )}
              >
                <Icon className="w-6 h-6 mb-2" />
                <span className="text-sm font-medium text-foreground">{action.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Items by Stock */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">Items with Stock</h2>
            <Link
              href="/inventory/items"
              className="inline-flex items-center gap-1 text-sm text-amber-400 hover:text-amber-300"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {itemsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
            </div>
          ) : recentItems.length > 0 ? (
            <div className="space-y-2">
              {recentItems.map((item: any) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between py-2 border-b border-slate-border/50 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.item_name}</p>
                    <p className="text-xs text-slate-muted font-mono">{item.item_code}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-emerald-400">
                      {(item.total_stock_qty ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </p>
                    <p className="text-xs text-slate-muted">{item.stock_uom || "units"}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Package className="w-8 h-8 text-slate-muted mx-auto mb-2" />
              <p className="text-sm text-slate-muted">No items in stock</p>
              <Link
                href="/inventory/items/new"
                className="inline-flex items-center gap-1 mt-2 text-sm text-amber-400 hover:text-amber-300"
              >
                <Plus className="w-3 h-3" /> Add first item
              </Link>
            </div>
          )}
        </div>

        {/* Recent Stock Entries */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">Recent Entries</h2>
            <Link
              href="/inventory/stock-entries"
              className="inline-flex items-center gap-1 text-sm text-amber-400 hover:text-amber-300"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {entriesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
            </div>
          ) : recentEntries.length > 0 ? (
            <div className="space-y-2">
              {recentEntries.map((entry: any) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between py-2 border-b border-slate-border/50 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{entry.stock_entry_type}</p>
                    <p className="text-xs text-slate-muted">
                      {entry.posting_date
                        ? new Date(entry.posting_date).toLocaleDateString()
                        : "No date"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-foreground">
                      {(entry.total_amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    <p className={cn(
                      "text-xs",
                      entry.docstatus === 1 ? "text-emerald-400" : "text-slate-muted"
                    )}>
                      {entry.docstatus === 0 ? "Draft" : entry.docstatus === 1 ? "Submitted" : "Cancelled"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <ClipboardList className="w-8 h-8 text-slate-muted mx-auto mb-2" />
              <p className="text-sm text-slate-muted">No recent entries</p>
              <Link
                href="/inventory/stock-entries/new"
                className="inline-flex items-center gap-1 mt-2 text-sm text-amber-400 hover:text-amber-300"
              >
                <Plus className="w-3 h-3" /> Create entry
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
