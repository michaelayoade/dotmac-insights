"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useInventoryTransfers, useInventoryTransferMutations } from "@/hooks/useApi";
import {
  ArrowLeft,
  ArrowRightLeft,
  Loader2,
  AlertCircle,
  Calendar,
  Warehouse,
  User,
  CheckCircle,
  XCircle,
  Clock,
  Truck,
  Send,
  Package,
} from "lucide-react";
import { formatStatusLabel, type StatusTone } from "@/lib/status-pill";
import { Button, StatusPill } from '@/components/ui';

function getStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return { label: "Draft", tone: "default" as StatusTone, icon: Clock };
    case "pending_approval":
      return { label: "Pending Approval", tone: "warning" as StatusTone, icon: Clock };
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

export default function TransferDetailPage() {
  const params = useParams();
  const router = useRouter();
  const transferId = Number(params.id);

  const { data, isLoading, error, mutate } = useInventoryTransfers({ limit: 1000 });
  const { submit, approve, reject, execute } = useInventoryTransferMutations();

  const transfer = data?.transfers?.find((t: any) => t.id === transferId);

  const handleAction = async (action: "submit" | "approve" | "reject" | "execute") => {
    try {
      switch (action) {
        case "submit":
          await submit(transferId);
          break;
        case "approve":
          await approve(transferId);
          break;
        case "reject":
          await reject(transferId, "Rejected via UI");
          break;
        case "execute":
          await execute(transferId);
          break;
      }
      mutate();
    } catch (err) {
      console.error(`Failed to ${action} transfer:`, err);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
        <span className="ml-2 text-slate-muted">Loading transfer...</span>
      </div>
    );
  }

  if (!transfer) {
    return (
      <div className="space-y-6">
        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load transfer: {error.message}</span>
          </div>
        )}
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 text-slate-muted mx-auto mb-3" />
          <p className="text-foreground font-medium">Transfer not found</p>
          <Link
            href="/inventory/transfers"
            className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to transfers
          </Link>
        </div>
      </div>
    );
  }

  const statusInfo = getStatusBadge(transfer.status);
  const StatusIcon = statusInfo.icon;

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center gap-2 py-6 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span>Failed to load transfer: {error.message}</span>
        </div>
      )}
      <div className="flex items-center gap-4">
        <Link
          href="/inventory/transfers"
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-foreground">Transfer #{transfer.id}</h1>
              <StatusPill
                label={statusInfo.label}
                tone={statusInfo.tone}
                icon={StatusIcon}
                size="md"
                className="border border-current/30"
              />
            </div>
          <p className="text-slate-muted text-sm">Warehouse transfer request</p>
        </div>
        <div className="flex items-center gap-2">
          {transfer.status === "draft" && (
            <Button
              onClick={() => handleAction("submit")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
            >
              <Send className="w-4 h-4" />
              Submit for Approval
            </Button>
          )}
          {transfer.status === "pending_approval" && (
            <>
              <Button
                onClick={() => handleAction("approve")}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 text-foreground font-semibold hover:bg-emerald-400 transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Approve
              </Button>
              <Button
                onClick={() => handleAction("reject")}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 font-semibold hover:bg-red-500/30 transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </Button>
            </>
          )}
          {transfer.status === "approved" && (
            <Button
              onClick={() => handleAction("execute")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500 text-foreground font-semibold hover:bg-purple-400 transition-colors"
            >
              <Truck className="w-4 h-4" />
              Execute Transfer
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transfer Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-amber-400" />
              Transfer Details
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-slate-muted mb-1">From Warehouse</p>
                <div className="flex items-center gap-2">
                  <Warehouse className="w-4 h-4 text-red-400" />
                  <span className="text-foreground font-medium">{transfer.from_warehouse || "-"}</span>
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">To Warehouse</p>
                <div className="flex items-center gap-2">
                  <Warehouse className="w-4 h-4 text-emerald-400" />
                  <span className="text-foreground font-medium">{transfer.to_warehouse || "-"}</span>
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">Request Date</p>
                <div className="flex items-center gap-2 text-foreground">
                  <Calendar className="w-4 h-4 text-slate-muted" />
                  {transfer.request_date
                    ? new Date(transfer.request_date).toLocaleDateString()
                    : "-"}
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-muted mb-1">Required Date</p>
                <div className="flex items-center gap-2 text-foreground">
                  <Calendar className="w-4 h-4 text-slate-muted" />
                  {transfer.required_date
                    ? new Date(transfer.required_date).toLocaleDateString()
                    : "-"}
                </div>
              </div>
            </div>
            {transfer.remarks && (
              <div className="mt-4 pt-4 border-t border-slate-border">
                <p className="text-sm text-slate-muted mb-1">Remarks</p>
                <p className="text-foreground">{transfer.remarks}</p>
              </div>
            )}
          </div>

          {/* Items */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <Package className="w-5 h-5 text-amber-400" />
              Items
            </h2>
            {transfer.items && transfer.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-border text-slate-muted text-left">
                      <th className="pb-3 font-medium">Item</th>
                      <th className="pb-3 font-medium text-right">Qty</th>
                      <th className="pb-3 font-medium">UoM</th>
                      <th className="pb-3 font-medium text-right">Rate</th>
                      <th className="pb-3 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-border/50">
                    {transfer.items.map((item: any, idx: number) => (
                      <tr key={idx}>
                        <td className="py-3">
                          <span className="text-amber-400 font-mono">{item.item_code}</span>
                          {item.item_name && (
                            <p className="text-slate-muted text-xs mt-0.5">{item.item_name}</p>
                          )}
                        </td>
                        <td className="py-3 text-right font-mono text-foreground">
                          {(item.qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 text-slate-muted">{item.uom || "-"}</td>
                        <td className="py-3 text-right font-mono text-slate-muted">
                          {(item.valuation_rate ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 text-right font-mono text-foreground">
                          {((item.qty ?? 0) * (item.valuation_rate ?? 0)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-slate-border">
                      <td colSpan={3} className="py-3 text-right text-slate-muted font-medium">Total:</td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {(transfer.total_qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-foreground font-semibold">
                        {(transfer.total_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            ) : (
              <p className="text-slate-muted">No items in this transfer</p>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Summary Card */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h3 className="text-sm font-medium text-slate-muted mb-4">Summary</h3>
            <div className="space-y-4">
              <div>
                <p className="text-xs text-slate-muted">Total Quantity</p>
                <p className="text-2xl font-bold text-foreground">
                  {(transfer.total_qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-muted">Total Value</p>
                <p className="text-2xl font-bold text-amber-400">
                  {(transfer.total_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
            </div>
          </div>

          {/* Approval Info */}
          {transfer.approval_status === "approved" && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h3 className="text-sm font-medium text-slate-muted mb-4">Approval Info</h3>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-muted" />
                  <span className="text-foreground">Approved</span>
                </div>
              </div>
            </div>
          )}

          {/* Rejection Info */}
          {transfer.approval_status === "rejected" && transfer.remarks && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
              <h3 className="text-sm font-medium text-red-400 mb-2">Rejection Reason</h3>
              <p className="text-foreground text-sm">{transfer.remarks}</p>
            </div>
          )}

          {/* Timeline */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h3 className="text-sm font-medium text-slate-muted mb-4">Activity</h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-slate-muted mt-2" />
                <div>
                  <p className="text-foreground text-sm">Requested</p>
                  <p className="text-xs text-slate-muted">
                    {transfer.request_date
                      ? new Date(transfer.request_date).toLocaleString()
                      : "-"}
                  </p>
                </div>
              </div>
              {transfer.transfer_date && transfer.transfer_date !== transfer.request_date && (
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-2" />
                  <div>
                    <p className="text-foreground text-sm">Transferred</p>
                    <p className="text-xs text-slate-muted">
                      {new Date(transfer.transfer_date).toLocaleString()}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
