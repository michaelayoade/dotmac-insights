"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  Calendar,
  TrendingDown,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Filter,
  Download,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { useDepreciationSchedule } from "@/hooks/useApi";

export default function DepreciationSchedulePage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [financeBook, setFinanceBook] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [bookedOnly, setBookedOnly] = useState<boolean | undefined>(undefined);

  const params = useMemo(() => {
    const p: Record<string, any> = { page, page_size: pageSize };
    if (financeBook) p.finance_book = financeBook;
    if (startDate) p.start_date = startDate;
    if (endDate) p.end_date = endDate;
    if (bookedOnly !== undefined) p.booked_only = bookedOnly;
    return p;
  }, [page, pageSize, financeBook, startDate, endDate, bookedOnly]);

  const { data, isLoading, mutate } = useDepreciationSchedule(params);

  const entries = data?.schedules ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  // Summary stats
  const totalDepreciation = entries.reduce((sum, e) => sum + (e.depreciation_amount || 0), 0);
  const bookedCount = entries.filter((e) => e.depreciation_booked).length;
  const pendingCount = entries.filter((e) => !e.depreciation_booked).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Depreciation Schedule</h1>
          <p className="text-sm text-slate-muted mt-1">
            View and manage asset depreciation entries
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
          <Link
            href="/assets/depreciation/pending"
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 rounded-lg text-sm text-white transition-colors"
          >
            <TrendingDown className="w-4 h-4" />
            Pending
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Total Entries</p>
          <p className="text-2xl font-bold text-white">{total}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Booked</p>
          <p className="text-2xl font-bold text-emerald-400">{bookedCount}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-sm text-slate-muted">Pending</p>
          <p className="text-2xl font-bold text-amber-400">{pendingCount}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <input
            type="text"
            placeholder="Finance book..."
            value={financeBook}
            onChange={(e) => { setFinanceBook(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
          <select
            value={bookedOnly === undefined ? "" : bookedOnly ? "booked" : "pending"}
            onChange={(e) => {
              const val = e.target.value;
              setBookedOnly(val === "" ? undefined : val === "booked");
              setPage(1);
            }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            <option value="">All Status</option>
            <option value="booked">Booked Only</option>
            <option value="pending">Pending Only</option>
          </select>
          <button
            onClick={() => {
              setFinanceBook("");
              setStartDate("");
              setEndDate("");
              setBookedOnly(undefined);
              setPage(1);
            }}
            className="px-4 py-2 text-sm text-slate-muted hover:text-white transition-colors"
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Schedule Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border bg-slate-elevated/50">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Asset</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Date</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Finance Book</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Depreciation</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Accumulated</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Journal Entry</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-muted">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                    Loading schedule...
                  </td>
                </tr>
              ) : entries.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-muted">
                    No depreciation entries found
                  </td>
                </tr>
              ) : (
                entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-elevated/30 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/assets/list/${entry.asset_id}`}
                        className="text-sm font-medium text-white hover:text-indigo-300 transition-colors"
                      >
                        {entry.asset_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 text-sm text-slate-muted">
                        <Calendar className="w-3 h-3" />
                        {formatDate(entry.schedule_date)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {entry.finance_book || "Default"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-medium text-amber-300">
                        {formatCurrency(entry.depreciation_amount)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-slate-muted">
                      {formatCurrency(entry.accumulated_depreciation_amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {entry.journal_entry || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "px-2 py-1 text-xs font-medium rounded-full",
                          entry.depreciation_booked
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-amber-500/20 text-amber-400"
                        )}
                      >
                        {entry.depreciation_booked ? "Booked" : "Pending"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-border">
            <p className="text-sm text-slate-muted">
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-slate-muted">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
