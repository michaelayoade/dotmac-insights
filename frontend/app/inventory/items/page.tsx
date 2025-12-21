"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useInventoryItems } from "@/hooks/useApi";
import { Package, Plus, Search, Loader2, AlertCircle, Warehouse } from "lucide-react";
import { cn } from "@/lib/utils";

export default function InventoryItemsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [hasStock, setHasStock] = useState<boolean | undefined>(undefined);
  const { data, isLoading, error } = useInventoryItems({ search: search || undefined, has_stock: hasStock, limit: 100 });

  const items = data?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Items</h1>
          <p className="text-slate-muted text-sm">Manage inventory items with stock levels</p>
        </div>
        <Link
          href="/inventory/items/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Item
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search items..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-border bg-slate-elevated text-foreground placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setHasStock(hasStock === true ? undefined : true)}
              className={cn(
                "px-3 py-2 rounded-lg border text-sm transition-colors",
                hasStock === true
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                  : "border-slate-border text-slate-muted hover:text-foreground hover:bg-slate-elevated"
              )}
            >
              In Stock Only
            </button>
            <button
              onClick={() => setHasStock(hasStock === false ? undefined : false)}
              className={cn(
                "px-3 py-2 rounded-lg border text-sm transition-colors",
                hasStock === false
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                  : "border-slate-border text-slate-muted hover:text-foreground hover:bg-slate-elevated"
              )}
            >
              Out of Stock
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading items...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load items: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && items.length === 0 && (
          <div className="text-center py-12">
            <Package className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No items found</p>
            <Link
              href="/inventory/items/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create your first item
            </Link>
          </div>
        )}

        {!isLoading && !error && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Item Code</th>
                  <th className="pb-3 font-medium">Item Name</th>
                  <th className="pb-3 font-medium">Group</th>
                  <th className="pb-3 font-medium">UoM</th>
                  <th className="pb-3 font-medium text-right">Total Stock</th>
                  <th className="pb-3 font-medium text-right">Valuation Rate</th>
                  <th className="pb-3 font-medium">Warehouses</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {items.map((item: any) => (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-elevated/50 transition-colors cursor-pointer"
                    onClick={() => router.push(`/inventory/items/${item.id}`)}
                  >
                    <td className="py-3">
                      <Link
                        href={`/inventory/items/${item.id}`}
                        className="text-amber-400 hover:text-amber-300 font-mono"
                      >
                        {item.item_code}
                      </Link>
                    </td>
                    <td className="py-3 text-foreground">{item.item_name}</td>
                    <td className="py-3 text-slate-muted">{item.item_group || "-"}</td>
                    <td className="py-3 text-slate-muted">{item.stock_uom || "-"}</td>
                    <td className="py-3 text-right">
                      <span className={cn(
                        "font-mono",
                        (item.total_stock_qty ?? 0) > 0 ? "text-emerald-400" : "text-slate-muted"
                      )}>
                        {(item.total_stock_qty ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono text-foreground">
                      {(item.valuation_rate ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-3">
                      {item.stock_by_warehouse ? (
                        <div className="flex items-center gap-1">
                          <Warehouse className="w-3 h-3 text-slate-muted" />
                          <span className="text-slate-muted text-xs">
                            {Object.keys(item.stock_by_warehouse).length} locations
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-muted">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && (
          <div className="pt-4 border-t border-slate-border/50 text-sm text-slate-muted">
            Showing {items.length} of {data.total} items
          </div>
        )}
      </div>
    </div>
  );
}
