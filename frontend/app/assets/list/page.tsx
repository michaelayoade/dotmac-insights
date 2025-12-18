"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search,
  Filter,
  Building2,
  MapPin,
  Calendar,
  TrendingDown,
  MoreVertical,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Plus,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { useAssets, useAssetMutations } from "@/hooks/useApi";
import type { Asset } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "submitted", label: "Submitted" },
  { value: "partially_depreciated", label: "Partially Depreciated" },
  { value: "fully_depreciated", label: "Fully Depreciated" },
  { value: "sold", label: "Sold" },
  { value: "scrapped", label: "Scrapped" },
  { value: "in_maintenance", label: "In Maintenance" },
  { value: "out_of_order", label: "Out of Order" },
];

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-500/20 text-slate-400",
  submitted: "bg-blue-500/20 text-blue-400",
  partially_depreciated: "bg-amber-500/20 text-amber-400",
  fully_depreciated: "bg-emerald-500/20 text-emerald-400",
  sold: "bg-purple-500/20 text-purple-400",
  scrapped: "bg-coral-alert/20 text-coral-alert",
  in_maintenance: "bg-orange-500/20 text-orange-400",
  out_of_order: "bg-red-500/20 text-red-400",
};

export default function AssetsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");

  const params = useMemo(() => {
    const p: Record<string, any> = { page, page_size: pageSize };
    if (search) p.search = search;
    if (statusFilter) p.status = statusFilter;
    if (categoryFilter) p.category = categoryFilter;
    if (locationFilter) p.location = locationFilter;
    return p;
  }, [page, pageSize, search, statusFilter, categoryFilter, locationFilter]);

  const { data, isLoading, mutate } = useAssets(params);
  const { submitAsset, scrapAsset } = useAssetMutations();

  const assets: Asset[] = data?.assets ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleSubmit = async (id: number) => {
    try {
      await submitAsset(id);
      mutate();
    } catch (error) {
      console.error("Failed to submit asset:", error);
    }
  };

  const handleScrap = async (id: number) => {
    if (!confirm("Are you sure you want to scrap this asset? This action cannot be undone.")) return;
    try {
      await scrapAsset(id);
      mutate();
    } catch (error) {
      console.error("Failed to scrap asset:", error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">All Assets</h1>
          <p className="text-sm text-slate-muted mt-1">
            {total} asset{total !== 1 ? "s" : ""} in register
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
            href="/assets/list/new"
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-sm text-white transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Asset
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search assets..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Category..."
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
          <input
            type="text"
            placeholder="Location..."
            value={locationFilter}
            onChange={(e) => { setLocationFilter(e.target.value); setPage(1); }}
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
        </div>
      </div>

      {/* Assets Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border bg-slate-elevated/50">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Asset</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Category</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Location</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Purchase</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Value</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Status</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-muted">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                    Loading assets...
                  </td>
                </tr>
              ) : assets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-muted">
                    No assets found
                  </td>
                </tr>
              ) : (
                assets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-slate-elevated/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-indigo-500/20">
                          <Building2 className="w-4 h-4 text-indigo-300" />
                        </div>
                        <div>
                          <Link
                            href={`/assets/list/${asset.id}`}
                            className="font-medium text-white hover:text-indigo-300 transition-colors"
                          >
                            {asset.asset_name}
                          </Link>
                          {asset.item_code && (
                            <p className="text-xs text-slate-muted">{asset.item_code}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {asset.asset_category || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-slate-muted">
                        <MapPin className="w-3 h-3" />
                        {asset.location || "-"}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-slate-muted">
                        <Calendar className="w-3 h-3" />
                        {asset.purchase_date ? formatDate(asset.purchase_date) : "-"}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div>
                        <p className="text-sm font-medium text-white">
                          {formatCurrency(asset.asset_value ?? 0)}
                        </p>
                        <p className="text-xs text-slate-muted">
                          Gross: {formatCurrency(asset.gross_purchase_amount ?? 0)}
                        </p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        "px-2 py-1 text-xs font-medium rounded-full capitalize",
                        STATUS_COLORS[asset.status ?? 'draft'] ?? "bg-slate-500/20 text-slate-400"
                      )}>
                        {asset.status?.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          href={`/assets/list/${asset.id}`}
                          className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
                          title="View"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        {asset.status === "draft" && (
                          <button
                            onClick={() => handleSubmit(asset.id)}
                            className="p-2 text-slate-muted hover:text-emerald-400 hover:bg-slate-elevated rounded-lg transition-colors"
                            title="Submit"
                          >
                            <CheckCircle className="w-4 h-4" />
                          </button>
                        )}
                        {asset.status && ["submitted", "partially_depreciated", "in_maintenance"].includes(asset.status) && (
                          <button
                            onClick={() => handleScrap(asset.id)}
                            className="p-2 text-slate-muted hover:text-coral-alert hover:bg-slate-elevated rounded-lg transition-colors"
                            title="Scrap"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
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
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-slate-muted">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
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
