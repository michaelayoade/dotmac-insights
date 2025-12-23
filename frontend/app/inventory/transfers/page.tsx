"use client";

import { useState } from "react";
import Link from "next/link";
import { useInventoryTransfers, useInventoryTransferMutations } from "@/hooks/useApi";
import {
  ArrowRightLeft,
  Plus,
  Loader2,
  AlertCircle,
  Calendar,
  CheckCircle,
  XCircle,
  Clock,
  Truck,
  Send,
} from "lucide-react";
import { formatStatusLabel, type StatusTone } from "@/lib/status-pill";
import { Button, FilterCard, FilterSelect, StatusPill, LoadingState } from '@/components/ui';
import { useRequireScope } from "@/lib/auth-context";
import { AccessDenied } from "@/components/AccessDenied";

const STATUS_OPTIONS = [
  { value: "", label: "All Status" },
  { value: "draft", label: "Draft" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "in_transit", label: "In Transit" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return { label: "Draft", tone: "default" as StatusTone, icon: Clock };
    case "pending_approval":
      return { label: "Pending", tone: "warning" as StatusTone, icon: Clock };
    case "approved":
      return { label: "Approved", tone: "info" as StatusTone, icon: CheckCircle };
    case "rejected":
      return { label: "Rejected", tone: "danger" as StatusTone, icon: XCircle };
    case "in_transit":
      return { label: "In Transit", tone: "info" as StatusTone, icon: Truck };
    case "completed":
      return { label: "Completed", tone: "success" as StatusTone, icon: CheckCircle };
    case "cancelled":
      return { label: "Cancelled", tone: "danger" as StatusTone, icon: XCircle };
    default:
      return { label: formatStatusLabel(status || "unknown"), tone: "default" as StatusTone, icon: Clock };
  }
}

export default function TransfersPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope("inventory:read");
  const [status, setStatus] = useState("");
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error, mutate } = useInventoryTransfers(
    {
      status: status || undefined,
      limit: 100,
    },
    { isPaused: () => !canFetch }
  );
  const { submit, approve, reject, execute } = useInventoryTransferMutations();

  const transfers = data?.transfers || [];

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the inventory:read permission to view transfers."
        backHref="/inventory"
        backLabel="Back to Inventory"
      />
    );
  }

  const handleAction = async (id: number, action: "submit" | "approve" | "reject" | "execute") => {
    try {
      switch (action) {
        case "submit":
          await submit(id);
          break;
        case "approve":
          await approve(id);
          break;
        case "reject":
          await reject(id, "Rejected via UI");
          break;
        case "execute":
          await execute(id);
          break;
      }
      mutate();
    } catch (err) {
      console.error(`Failed to ${action} transfer:`, err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Warehouse Transfers</h1>
          <p className="text-slate-muted text-sm">Transfer stock between warehouses with approval workflow</p>
        </div>
        <Link
          href="/inventory/transfers/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Transfer
        </Link>
      </div>

      <FilterCard contentClassName="space-y-4" iconClassName="text-amber-400">
        <div className="flex flex-col md:flex-row gap-4">
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
            <span className="ml-2 text-slate-muted">Loading transfers...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load transfers: {error.message}</span>
          </div>
        )}

        {!isLoading && !error && transfers.length === 0 && (
          <div className="text-center py-12">
            <ArrowRightLeft className="w-12 h-12 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted">No transfers found</p>
            <Link
              href="/inventory/transfers/new"
              className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
            >
              <Plus className="w-4 h-4" />
              Create a transfer request
            </Link>
          </div>
        )}

        {!isLoading && !error && transfers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-border text-slate-muted text-left">
                  <th className="pb-3 font-medium">ID</th>
                  <th className="pb-3 font-medium">From Warehouse</th>
                  <th className="pb-3 font-medium">To Warehouse</th>
                  <th className="pb-3 font-medium">Request Date</th>
                  <th className="pb-3 font-medium text-right">Total Qty</th>
                  <th className="pb-3 font-medium text-right">Value</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border/50">
                {transfers.map((transfer: any) => {
                  const statusInfo = getStatusBadge(transfer.status);
                  const StatusIcon = statusInfo.icon;
                  return (
                    <tr key={transfer.id} className="hover:bg-slate-elevated/50 transition-colors">
                      <td className="py-3">
                        <Link
                          href={`/inventory/transfers/${transfer.id}`}
                          className="text-amber-400 font-mono hover:underline"
                        >
                          #{transfer.id}
                        </Link>
                      </td>
                      <td className="py-3 text-foreground">{transfer.from_warehouse || "-"}</td>
                      <td className="py-3 text-foreground">{transfer.to_warehouse || "-"}</td>
                      <td className="py-3">
                        {transfer.request_date ? (
                          <div className="flex items-center gap-2 text-slate-muted">
                            <Calendar className="w-3 h-3" />
                            {new Date(transfer.request_date).toLocaleDateString()}
                          </div>
                        ) : (
                          <span className="text-slate-muted">-</span>
                        )}
                      </td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {(transfer.total_qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {(transfer.total_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3">
                        <StatusPill
                          label={statusInfo.label}
                          tone={statusInfo.tone}
                          icon={StatusIcon}
                          className="border border-current/30"
                        />
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          {transfer.status === "draft" && (
                            <Button
                              onClick={() => handleAction(transfer.id, "submit")}
                              className="p-1.5 text-amber-400 hover:bg-amber-500/20 rounded transition-colors"
                              title="Submit for approval"
                            >
                              <Send className="w-4 h-4" />
                            </Button>
                          )}
                          {transfer.status === "pending_approval" && (
                            <>
                              <Button
                                onClick={() => handleAction(transfer.id, "approve")}
                                className="p-1.5 text-emerald-400 hover:bg-emerald-500/20 rounded transition-colors"
                                title="Approve"
                              >
                                <CheckCircle className="w-4 h-4" />
                              </Button>
                              <Button
                                onClick={() => handleAction(transfer.id, "reject")}
                                className="p-1.5 text-red-400 hover:bg-red-500/20 rounded transition-colors"
                                title="Reject"
                              >
                                <XCircle className="w-4 h-4" />
                              </Button>
                            </>
                          )}
                          {transfer.status === "approved" && (
                            <Button
                              onClick={() => handleAction(transfer.id, "execute")}
                              className="p-1.5 text-purple-400 hover:bg-purple-500/20 rounded transition-colors"
                              title="Execute transfer"
                            >
                              <Truck className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
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
            Showing {transfers.length} of {data.total} transfers
          </div>
        )}
      </FilterCard>
    </div>
  );
}
