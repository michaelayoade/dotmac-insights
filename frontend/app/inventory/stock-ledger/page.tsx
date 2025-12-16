"use client";

import { useState } from "react";
import { useInventoryStockLedger } from "@/hooks/useApi";
import { History, Loader2, AlertCircle, ArrowUp, ArrowDown, Calendar, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export default function StockLedgerPage() {
  const [itemCode, setItemCode] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data, isLoading, error } = useInventoryStockLedger({
    item_code: itemCode || undefined,
    warehouse: warehouse || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit: 100,
  });

  const entries = data?.entries || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Stock Ledger</h1>
        <p className="text-slate-muted text-sm">Complete history of inventory movements</p>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Item code..."
              value={itemCode}
              onChange={(e) => setItemCode(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Warehouse..."
              value={warehouse}
              onChange={(e) => setWarehouse(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading ledger entries...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load ledger: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && entries.length === 0 && (
          <div className="text-center py-12">
            <History className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No ledger entries found</p>
            <p className="text-slate-muted text-sm mt-1">Try adjusting your filters</p>
          </div>
        )}

        {!isLoading && !error && entries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Date</th>
                  <th className="pb-3 font-medium">Item</th>
                  <th className="pb-3 font-medium">Warehouse</th>
                  <th className="pb-3 font-medium text-right">Qty Change</th>
                  <th className="pb-3 font-medium text-right">Balance</th>
                  <th className="pb-3 font-medium text-right">Rate</th>
                  <th className="pb-3 font-medium text-right">Value</th>
                  <th className="pb-3 font-medium">Voucher</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {entries.map((entry) => {
                  const isIncoming = entry.actual_qty > 0;
                  return (
                    <tr key={entry.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3 text-slate-muted">
                        {entry.posting_date ? new Date(entry.posting_date).toLocaleDateString() : "-"}
                      </td>
                      <td className="py-3 text-amber-400 font-mono">{entry.item_code}</td>
                      <td className="py-3 text-white">{entry.warehouse}</td>
                      <td className="py-3 text-right">
                        <div className={cn(
                          "inline-flex items-center gap-1 font-mono",
                          isIncoming ? "text-emerald-400" : "text-red-400"
                        )}>
                          {isIncoming ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                          {Math.abs(entry.actual_qty).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </div>
                      </td>
                      <td className="py-3 text-right font-mono text-white">
                        {entry.qty_after_transaction.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-slate-muted">
                        {(entry.valuation_rate ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-white">
                        {(entry.stock_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-slate-muted text-xs">
                        {entry.voucher_type && entry.voucher_no ? (
                          <span>{entry.voucher_type}: {entry.voucher_no}</span>
                        ) : (
                          <span>-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data && (
          <div className="pt-4 border-t border-slate-border/50 text-sm text-slate-muted">
            Showing {entries.length} of {data.total} entries
          </div>
        )}
      </div>
    </div>
  );
}
