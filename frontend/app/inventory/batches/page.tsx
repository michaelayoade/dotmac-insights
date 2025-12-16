"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventoryBatches } from "@/hooks/useApi";
import {
  Layers,
  Plus,
  Loader2,
  AlertCircle,
  Calendar,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function BatchesPage() {
  const [itemCode, setItemCode] = useState("");
  const [includeDisabled, setIncludeDisabled] = useState(false);
  const { data, isLoading, error } = useInventoryBatches({
    item_code: itemCode || undefined,
    include_disabled: includeDisabled,
    limit: 100,
  });

  const batches = data?.batches || [];

  const isExpiringSoon = (expiryDate: string | null | undefined) => {
    if (!expiryDate) return false;
    const expiry = new Date(expiryDate);
    const now = new Date();
    const daysUntilExpiry = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return daysUntilExpiry <= 30 && daysUntilExpiry > 0;
  };

  const isExpired = (expiryDate: string | null | undefined) => {
    if (!expiryDate) return false;
    return new Date(expiryDate) < new Date();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Batch Tracking</h1>
          <p className="text-slate-muted text-sm">Track items by batch number with expiry dates</p>
        </div>
        <Link
          href="/inventory/batches/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Batch
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <input
            type="text"
            placeholder="Filter by item code..."
            value={itemCode}
            onChange={(e) => setItemCode(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          />
          <label className="flex items-center gap-2 text-slate-muted text-sm">
            <input
              type="checkbox"
              checked={includeDisabled}
              onChange={(e) => setIncludeDisabled(e.target.checked)}
              className="rounded border-slate-border bg-slate-elevated"
            />
            Include disabled batches
          </label>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading batches...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load batches: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && batches.length === 0 && (
          <div className="text-center py-12">
            <Layers className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No batches found</p>
            <Link
              href="/inventory/batches/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create a batch
            </Link>
          </div>
        )}

        {!isLoading && !error && batches.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Batch ID</th>
                  <th className="pb-3 font-medium">Item</th>
                  <th className="pb-3 font-medium">Mfg Date</th>
                  <th className="pb-3 font-medium">Expiry Date</th>
                  <th className="pb-3 font-medium text-right">Qty</th>
                  <th className="pb-3 font-medium">Supplier</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {batches.map((batch) => {
                  const expired = isExpired(batch.expiry_date);
                  const expiringSoon = isExpiringSoon(batch.expiry_date);
                  return (
                    <tr key={batch.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3">
                        <span className="text-amber-400 font-mono">{batch.batch_id}</span>
                      </td>
                      <td className="py-3">
                        <div>
                          <span className="text-white">{batch.item_code}</span>
                          {batch.item_name && (
                            <span className="text-slate-muted ml-2 text-xs">{batch.item_name}</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3">
                        {batch.manufacturing_date ? (
                          <div className="flex items-center gap-2 text-slate-muted">
                            <Calendar className="w-3 h-3" />
                            {new Date(batch.manufacturing_date).toLocaleDateString()}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3">
                        {batch.expiry_date ? (
                          <div className={cn(
                            "flex items-center gap-2",
                            expired ? "text-red-400" : expiringSoon ? "text-amber-400" : "text-slate-muted"
                          )}>
                            {expired ? (
                              <AlertTriangle className="w-3 h-3" />
                            ) : expiringSoon ? (
                              <AlertTriangle className="w-3 h-3" />
                            ) : (
                              <Calendar className="w-3 h-3" />
                            )}
                            {new Date(batch.expiry_date).toLocaleDateString()}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3 text-right font-mono text-white">
                        {(batch.batch_qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-slate-muted">{batch.supplier || "-"}</td>
                      <td className="py-3">
                        {batch.disabled ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-300">
                            Disabled
                          </span>
                        ) : expired ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-300">
                            <AlertTriangle className="w-3 h-3" />
                            Expired
                          </span>
                        ) : expiringSoon ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-300">
                            <AlertTriangle className="w-3 h-3" />
                            Expiring Soon
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300">
                            <CheckCircle className="w-3 h-3" />
                            Active
                          </span>
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
            Showing {batches.length} of {data.total} batches
          </div>
        )}
      </div>
    </div>
  );
}
