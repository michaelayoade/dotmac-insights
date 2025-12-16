"use client";

import { useInventoryStockSummary } from "@/hooks/useApi";
import { BarChart3, Loader2, AlertCircle, Warehouse } from "lucide-react";
import { cn } from "@/lib/utils";

export default function StockSummaryPage() {
  const { data, isLoading, error } = useInventoryStockSummary();

  const items = data?.items || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Stock Summary</h1>
        <p className="text-slate-muted text-sm">Overview of stock levels across all items and warehouses</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-muted">Total Stock Value</p>
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-amber-500 animate-spin mt-2" />
          ) : (
            <p className="text-2xl font-bold text-white mt-1">
              {(data?.total_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-muted">Total Items</p>
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin mt-2" />
          ) : (
            <p className="text-2xl font-bold text-white mt-1">{data?.total_items ?? 0}</p>
          )}
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-muted">Total Qty</p>
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-emerald-500 animate-spin mt-2" />
          ) : (
            <p className="text-2xl font-bold text-white mt-1">
              {(data?.total_qty ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </p>
          )}
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading summary...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load summary: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && items.length === 0 && (
          <div className="text-center py-12">
            <BarChart3 className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No stock data available</p>
          </div>
        )}

        {!isLoading && !error && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Item Code</th>
                  <th className="pb-3 font-medium">Item Name</th>
                  <th className="pb-3 font-medium text-right">Qty</th>
                  <th className="pb-3 font-medium text-right">Valuation Rate</th>
                  <th className="pb-3 font-medium text-right">Total Value</th>
                  <th className="pb-3 font-medium">Warehouse</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {items.map((item, idx) => (
                  <tr key={`${item.item_code}-${item.warehouse}-${idx}`} className="hover:bg-slate-elevated/50 transition-colors">
                    <td className="py-3 text-amber-400 font-mono">{item.item_code}</td>
                    <td className="py-3 text-white">{item.item_name || "-"}</td>
                    <td className="py-3 text-right">
                      <span className={cn(
                        "font-mono",
                        (item.actual_qty ?? 0) > 0 ? "text-emerald-400" : "text-slate-muted"
                      )}>
                        {(item.actual_qty ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono text-slate-muted">
                      {(item.valuation_rate ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 text-right font-mono text-white">
                      {(item.stock_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-3">
                      <div className="flex items-center gap-1 text-slate-muted">
                        <Warehouse className="w-3 h-3" />
                        <span className="text-xs">{item.warehouse || "-"}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
