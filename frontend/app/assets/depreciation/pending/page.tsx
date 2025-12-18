"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Clock,
  TrendingDown,
  Calendar,
  RefreshCw,
  ArrowRight,
  CheckCircle,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { usePendingDepreciation } from "@/hooks/useApi";
import type { PendingDepreciationEntry } from "@/lib/api";

export default function PendingDepreciationPage() {
  const today = new Date().toISOString().split("T")[0];
  const [asOfDate, setAsOfDate] = useState(today);

  const { data, isLoading, mutate } = usePendingDepreciation(asOfDate);

  const pendingEntries: PendingDepreciationEntry[] = data?.pending_entries ?? [];
  const totalPending = data?.total_pending_amount ?? 0;

  // Group by asset
  type PendingGroup = { asset_name: string; asset_id: number; entries: PendingDepreciationEntry[] };
  const byAsset = pendingEntries.reduce<Record<number, PendingGroup>>((acc, entry) => {
    const key = entry.asset_id;
    if (!acc[key]) {
      acc[key] = { asset_name: entry.asset_name ?? 'Unknown Asset', asset_id: entry.asset_id, entries: [] };
    }
    acc[key].entries.push(entry);
    return acc;
  }, {} as Record<number, { asset_name: string; asset_id: number; entries: typeof pendingEntries }>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Pending Depreciation</h1>
          <p className="text-sm text-slate-muted mt-1">
            Depreciation entries due as of selected date
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

      {/* Date Filter and Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <label className="block text-sm text-slate-muted mb-2">As of Date</label>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Pending Entries</p>
          <p className="text-2xl font-bold text-amber-400">{pendingEntries.length}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Total Amount</p>
          <p className="text-2xl font-bold text-white">{formatCurrency(totalPending)}</p>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-muted" />
          <p className="text-slate-muted">Loading pending entries...</p>
        </div>
      ) : pendingEntries.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <CheckCircle className="w-8 h-8 mx-auto mb-3 text-emerald-400" />
          <p className="font-medium text-white">All caught up!</p>
          <p className="text-sm text-slate-muted mt-1">No pending depreciation entries as of {formatDate(asOfDate)}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.values(byAsset).map((group) => (
            <div key={group.asset_id} className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-elevated/30 border-b border-slate-border">
                <Link
                  href={`/assets/list/${group.asset_id}`}
                  className="font-medium text-white hover:text-indigo-300 transition-colors"
                >
                  {group.asset_name}
                </Link>
                <span className="text-sm text-amber-400 font-medium">
                  {group.entries.length} pending
                </span>
              </div>
              <div className="divide-y divide-slate-border">
                {group.entries.map((entry, idx) => (
                  <div key={idx} className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 text-sm text-slate-muted">
                        <Calendar className="w-4 h-4" />
                        {formatDate(entry.schedule_date)}
                      </div>
                      <span className="text-sm text-slate-muted">
                        {entry.finance_book || "Default"}
                      </span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-medium text-amber-300">
                        {formatCurrency(entry.depreciation_amount)}
                      </span>
                      <button
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-lg text-xs font-medium transition-colors"
                        title="Book depreciation"
                      >
                        <CheckCircle className="w-3 h-3" />
                        Book
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Actions */}
      {pendingEntries.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-white mb-3">Bulk Actions</h3>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm text-white transition-colors">
              <CheckCircle className="w-4 h-4" />
              Book All Pending
            </button>
            <p className="text-sm text-slate-muted">
              This will create journal entries for all {pendingEntries.length} pending depreciation entries.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
