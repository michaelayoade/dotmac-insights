"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventorySerials } from "@/hooks/useApi";
import {
  Hash,
  Plus,
  Loader2,
  AlertCircle,
  Package,
  Warehouse,
  User,
  CheckCircle,
  Truck,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { formatStatusLabel, type StatusTone } from "@/lib/status-pill";
import { FilterCard, FilterInput, FilterSelect, StatusPill, LoadingState } from "@/components/ui";
import { useRequireScope } from "@/lib/auth-context";
import { AccessDenied } from "@/components/AccessDenied";

const STATUS_OPTIONS = [
  { value: "", label: "All Status" },
  { value: "active", label: "Active" },
  { value: "delivered", label: "Delivered" },
  { value: "returned", label: "Returned" },
  { value: "inactive", label: "Inactive" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return { label: "Active", tone: "success" as StatusTone, icon: CheckCircle };
    case "delivered":
      return { label: "Delivered", tone: "info" as StatusTone, icon: Truck };
    case "returned":
      return { label: "Returned", tone: "warning" as StatusTone, icon: RotateCcw };
    case "inactive":
      return { label: "Inactive", tone: "default" as StatusTone, icon: XCircle };
    default:
      return { label: formatStatusLabel(status || "unknown"), tone: "default" as StatusTone, icon: Hash };
  }
}

export default function SerialsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope("inventory:read");
  const [itemCode, setItemCode] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [status, setStatus] = useState("");
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error } = useInventorySerials(
    {
      item_code: itemCode || undefined,
      warehouse: warehouse || undefined,
      status: status || undefined,
      limit: 100,
    },
    { isPaused: () => !canFetch }
  );

  const serials = data?.serials || [];

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the inventory:read permission to view serial numbers."
        backHref="/inventory"
        backLabel="Back to Inventory"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Serial Number Tracking</h1>
          <p className="text-slate-muted text-sm">Track individual items by unique serial numbers</p>
        </div>
        <Link
          href="/inventory/serials/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Serial
        </Link>
      </div>

      <FilterCard contentClassName="space-y-4" iconClassName="text-amber-400">
        <div className="flex flex-col md:flex-row gap-4">
          <FilterInput
            type="text"
            placeholder="Filter by item code..."
            value={itemCode}
            onChange={(e) => setItemCode(e.target.value)}
            className="focus:ring-2 focus:ring-amber-500/50"
          />
          <FilterInput
            type="text"
            placeholder="Filter by warehouse..."
            value={warehouse}
            onChange={(e) => setWarehouse(e.target.value)}
            className="focus:ring-2 focus:ring-amber-500/50"
          />
          <FilterSelect
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="focus:ring-2 focus:ring-amber-500/50"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </FilterSelect>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            <span className="ml-2 text-slate-muted">Loading serial numbers...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load serial numbers: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && serials.length === 0 && (
          <div className="text-center py-12">
            <Hash className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No serial numbers found</p>
            <Link
              href="/inventory/serials/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create a serial number
            </Link>
          </div>
        )}

        {!isLoading && !error && serials.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">Serial No</th>
                  <th className="pb-3 font-medium">Item</th>
                  <th className="pb-3 font-medium">Warehouse</th>
                  <th className="pb-3 font-medium">Batch</th>
                  <th className="pb-3 font-medium">Customer</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {serials.map((serial: any) => {
                  const statusInfo = getStatusBadge(serial.status);
                  const StatusIcon = statusInfo.icon;
                  return (
                    <tr key={serial.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3">
                        <span className="text-amber-400 font-mono">{serial.serial_no}</span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Package className="w-4 h-4 text-slate-muted" />
                          <div>
                            <span className="text-foreground">{serial.item_code}</span>
                            {serial.item_name && (
                              <span className="text-slate-muted ml-2 text-xs">{serial.item_name}</span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3">
                        {serial.warehouse ? (
                          <div className="flex items-center gap-2 text-slate-muted">
                            <Warehouse className="w-3 h-3" />
                            {serial.warehouse}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3 text-slate-muted font-mono text-xs">
                        {serial.batch_no || "-"}
                      </td>
                      <td className="py-3">
                        {serial.customer ? (
                          <div className="flex items-center gap-2 text-slate-muted">
                            <User className="w-3 h-3" />
                            {serial.customer}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3">
                        <StatusPill
                          label={statusInfo.label}
                          tone={statusInfo.tone}
                          icon={StatusIcon}
                          className="border border-current/30"
                        />
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
            Showing {serials.length} of {data.total} serial numbers
          </div>
        )}
      </FilterCard>
    </div>
  );
}
