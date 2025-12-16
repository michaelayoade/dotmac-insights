"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventoryStockEntries } from "@/hooks/useApi";
import { ClipboardList, Plus, Loader2, AlertCircle, ArrowRightLeft, ArrowDownToLine, ArrowUpFromLine, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

const ENTRY_TYPES = [
  { value: "", label: "All Types" },
  { value: "Material Receipt", label: "Material Receipt" },
  { value: "Material Issue", label: "Material Issue" },
  { value: "Material Transfer", label: "Material Transfer" },
  { value: "Manufacture", label: "Manufacture" },
  { value: "Repack", label: "Repack" },
];

const STATUS_OPTIONS = [
  { value: undefined, label: "All Status" },
  { value: 0, label: "Draft" },
  { value: 1, label: "Submitted" },
  { value: 2, label: "Cancelled" },
];

function getEntryIcon(entryType: string) {
  if (entryType?.toLowerCase().includes("receipt")) return ArrowDownToLine;
  if (entryType?.toLowerCase().includes("issue")) return ArrowUpFromLine;
  if (entryType?.toLowerCase().includes("transfer")) return ArrowRightLeft;
  return ClipboardList;
}

function getStatusBadge(docstatus: number | undefined) {
  switch (docstatus) {
    case 0:
      return { label: "Draft", className: "bg-slate-500/20 text-slate-300" };
    case 1:
      return { label: "Submitted", className: "bg-emerald-500/20 text-emerald-300" };
    case 2:
      return { label: "Cancelled", className: "bg-red-500/20 text-red-300" };
    default:
      return { label: "Unknown", className: "bg-slate-500/20 text-slate-300" };
  }
}

export default function StockEntriesPage() {
  const [entryType, setEntryType] = useState("");
  const [docstatus, setDocstatus] = useState<number | undefined>(undefined);
  const { data, isLoading, error } = useInventoryStockEntries({
    stock_entry_type: entryType || undefined,
    docstatus,
    limit: 100,
  });

  const entries = data?.entries || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Stock Entries</h1>
          <p className="text-slate-muted text-sm">View and manage stock transactions</p>
        </div>
        <Link
          href="/inventory/stock-entries/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Entry
        </Link>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <select
            value={entryType}
            onChange={(e) => setEntryType(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            {ENTRY_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
          <select
            value={docstatus ?? ""}
            onChange={(e) => setDocstatus(e.target.value === "" ? undefined : Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.label} value={opt.value ?? ""}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading entries...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load stock entries: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && entries.length === 0 && (
          <div className="text-center py-12">
            <ClipboardList className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No stock entries found</p>
            <Link
              href="/inventory/stock-entries/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create a stock entry
            </Link>
          </div>
        )}

        {!isLoading && !error && entries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">ID</th>
                  <th className="pb-3 font-medium">Type</th>
                  <th className="pb-3 font-medium">Posting Date</th>
                  <th className="pb-3 font-medium">From</th>
                  <th className="pb-3 font-medium">To</th>
                  <th className="pb-3 font-medium text-right">Total Amount</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {entries.map((entry) => {
                  const Icon = getEntryIcon(entry.stock_entry_type);
                  const status = getStatusBadge(entry.docstatus);
                  return (
                    <tr key={entry.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3">
                        <span className="text-amber-400 font-mono">
                          {entry.erpnext_id || `#${entry.id}`}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 text-slate-muted" />
                          <span className="text-white">{entry.stock_entry_type}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        {entry.posting_date ? (
                          <div className="flex items-center gap-2 text-slate-muted">
                            <Calendar className="w-3 h-3" />
                            {new Date(entry.posting_date).toLocaleDateString()}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3 text-slate-muted">
                        {entry.from_warehouse || "-"}
                      </td>
                      <td className="py-3 text-slate-muted">
                        {entry.to_warehouse || "-"}
                      </td>
                      <td className="py-3 text-right font-mono text-white">
                        {(entry.total_amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3">
                        <span className={cn("px-2 py-0.5 rounded-full text-xs", status.className)}>
                          {status.label}
                        </span>
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
