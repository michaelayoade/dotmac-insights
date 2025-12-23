'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useInventoryStockEntryDetail, useInventoryMutations } from '@/hooks/useApi';
import {
  ArrowLeft,
  ArrowRightLeft,
  Loader2,
  AlertCircle,
  Calendar,
  Warehouse,
  CheckCircle,
  XCircle,
  Clock,
  Package,
  FileText,
  Trash2,
  BookOpen,
} from 'lucide-react';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

interface StockEntryItem {
  id: number;
  item_code: string;
  item_name?: string;
  description?: string;
  uom: string;
  qty: number;
  s_warehouse?: string | null;
  t_warehouse?: string | null;
  basic_rate?: number;
  basic_amount?: number;
  valuation_rate?: number;
  amount?: number;
  batch_no?: string | null;
  serial_no?: string | null;
}

interface StockEntryDetail {
  id: number;
  erpnext_id?: string | null;
  stock_entry_type: string;
  purpose?: string | null;
  posting_date?: string | null;
  posting_time?: string | null;
  from_warehouse?: string | null;
  to_warehouse?: string | null;
  company?: string | null;
  total_incoming_value?: number;
  total_outgoing_value?: number;
  value_difference?: number;
  total_amount?: number;
  docstatus?: number;
  is_opening?: boolean;
  is_return?: boolean;
  remarks?: string | null;
  work_order?: string | null;
  purchase_order?: string | null;
  sales_order?: string | null;
  delivery_note?: string | null;
  purchase_receipt?: string | null;
  last_synced_at?: string | null;
  items?: StockEntryItem[];
}

function getDocStatusBadge(docstatus: number | undefined) {
  switch (docstatus) {
    case 0:
      return { label: 'Draft', tone: 'warning' as StatusTone, icon: Clock };
    case 1:
      return { label: 'Submitted', tone: 'success' as StatusTone, icon: CheckCircle };
    case 2:
      return { label: 'Cancelled', tone: 'danger' as StatusTone, icon: XCircle };
    default:
      return { label: 'Unknown', tone: 'default' as StatusTone, icon: Clock };
  }
}

function getEntryTypeBadge(entryType: string) {
  const type = entryType?.toLowerCase().replace(/_/g, ' ') || 'unknown';
  switch (entryType?.toLowerCase()) {
    case 'material_receipt':
    case 'material receipt':
      return { label: 'Material Receipt', tone: 'success' as StatusTone };
    case 'material_issue':
    case 'material issue':
      return { label: 'Material Issue', tone: 'danger' as StatusTone };
    case 'material_transfer':
    case 'material transfer':
      return { label: 'Material Transfer', tone: 'info' as StatusTone };
    case 'manufacture':
      return { label: 'Manufacture', tone: 'info' as StatusTone };
    case 'repack':
      return { label: 'Repack', tone: 'info' as StatusTone };
    default:
      return { label: formatStatusLabel(type), tone: 'default' as StatusTone };
  }
}

export default function StockEntryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const entryId = params.id as string;

  const { isLoading: authLoading, missingScope } = useRequireScope('inventory:read');
  const { data: entry, isLoading, error, mutate } = useInventoryStockEntryDetail(entryId);
  const { updateStockEntry, deleteStockEntry, postToGL } = useInventoryMutations();

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Permission guard
  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
        <span className="ml-2 text-slate-muted">Checking permissions...</span>
      </div>
    );
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the inventory:read permission to view stock entries."
        backHref="/inventory/stock-entries"
        backLabel="Back to Stock Entries"
      />
    );
  }

  const handleSubmit = async () => {
    setActionLoading('submit');
    setActionError(null);
    try {
      await updateStockEntry(entryId, { docstatus: 1 });
      mutate();
    } catch (err: any) {
      setActionError(err?.message || 'Failed to submit entry');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this stock entry? This action cannot be undone.')) {
      return;
    }
    setActionLoading('cancel');
    setActionError(null);
    try {
      await updateStockEntry(entryId, { docstatus: 2 });
      mutate();
    } catch (err: any) {
      setActionError(err?.message || 'Failed to cancel entry');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this stock entry? This action cannot be undone.')) {
      return;
    }
    setActionLoading('delete');
    setActionError(null);
    try {
      await deleteStockEntry(entryId);
      router.push('/inventory/stock-entries');
    } catch (err: any) {
      setActionError(err?.message || 'Failed to delete entry');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePostToGL = async () => {
    setActionLoading('post');
    setActionError(null);
    try {
      await postToGL(entryId);
      mutate();
    } catch (err: any) {
      setActionError(err?.message || 'Failed to post to GL');
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
        <span className="ml-2 text-slate-muted">Loading stock entry...</span>
      </div>
    );
  }

  if (!entry) {
    return (
      <div className="space-y-6">
        {error && (
          <div className="flex items-center gap-2 py-6 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load stock entry: {error.message}</span>
          </div>
        )}
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 text-slate-muted mx-auto mb-3" />
          <p className="text-foreground font-medium">Stock entry not found</p>
          <Link
            href="/inventory/stock-entries"
            className="inline-flex items-center gap-2 mt-4 text-amber-400 hover:text-amber-300"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to stock entries
          </Link>
        </div>
      </div>
    );
  }

  const typedEntry = entry as StockEntryDetail;
  const statusInfo = getDocStatusBadge(typedEntry.docstatus);
  const typeInfo = getEntryTypeBadge(typedEntry.stock_entry_type);
  const StatusIcon = statusInfo.icon;
  const items = typedEntry.items || [];

  return (
    <div className="space-y-6">
      {(error || actionError) && (
        <div className="flex items-center gap-2 py-3 px-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span>{actionError || error?.message}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/inventory/stock-entries"
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground">
              Stock Entry #{typedEntry.id}
            </h1>
            <StatusPill
              label={statusInfo.label}
              tone={statusInfo.tone}
              icon={StatusIcon}
              size="md"
              className="border border-current/30"
            />
            <StatusPill
              label={typeInfo.label}
              tone={typeInfo.tone}
              size="md"
            />
          </div>
          <p className="text-slate-muted text-sm">
            {typedEntry.erpnext_id && (
              <span className="font-mono">{typedEntry.erpnext_id}</span>
            )}
            {typedEntry.purpose && (
              <span> &middot; {typedEntry.purpose}</span>
            )}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {typedEntry.docstatus === 0 && (
            <>
              <Button
                onClick={handleSubmit}
                disabled={!!actionLoading}
                loading={actionLoading === 'submit'}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 text-foreground font-semibold hover:bg-emerald-400 transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Submit
              </Button>
              <Button
                onClick={handleDelete}
                disabled={!!actionLoading}
                loading={actionLoading === 'delete'}
                variant="secondary"
                className="inline-flex items-center gap-2 text-red-400 hover:bg-red-500/20"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </Button>
            </>
          )}
          {typedEntry.docstatus === 1 && (
            <>
              <Button
                onClick={handlePostToGL}
                disabled={!!actionLoading}
                loading={actionLoading === 'post'}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500 text-foreground font-semibold hover:bg-purple-400 transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                Post to GL
              </Button>
              <Button
                onClick={handleCancel}
                disabled={!!actionLoading}
                loading={actionLoading === 'cancel'}
                variant="secondary"
                className="inline-flex items-center gap-2 text-red-400 hover:bg-red-500/20"
              >
                <XCircle className="w-4 h-4" />
                Cancel
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Entry Details */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-amber-400" />
              Entry Details
            </h2>
            <div className="grid grid-cols-2 gap-6">
              {typedEntry.from_warehouse && (
                <div>
                  <p className="text-sm text-slate-muted mb-1">Source Warehouse</p>
                  <div className="flex items-center gap-2">
                    <Warehouse className="w-4 h-4 text-red-400" />
                    <span className="text-foreground font-medium">{typedEntry.from_warehouse}</span>
                  </div>
                </div>
              )}
              {typedEntry.to_warehouse && (
                <div>
                  <p className="text-sm text-slate-muted mb-1">Target Warehouse</p>
                  <div className="flex items-center gap-2">
                    <Warehouse className="w-4 h-4 text-emerald-400" />
                    <span className="text-foreground font-medium">{typedEntry.to_warehouse}</span>
                  </div>
                </div>
              )}
              <div>
                <p className="text-sm text-slate-muted mb-1">Posting Date</p>
                <div className="flex items-center gap-2 text-foreground">
                  <Calendar className="w-4 h-4 text-slate-muted" />
                  {typedEntry.posting_date
                    ? new Date(typedEntry.posting_date).toLocaleDateString()
                    : '-'}
                  {typedEntry.posting_time && (
                    <span className="text-slate-muted text-sm">{typedEntry.posting_time}</span>
                  )}
                </div>
              </div>
              {typedEntry.company && (
                <div>
                  <p className="text-sm text-slate-muted mb-1">Company</p>
                  <span className="text-foreground">{typedEntry.company}</span>
                </div>
              )}
            </div>
            {typedEntry.remarks && (
              <div className="mt-4 pt-4 border-t border-slate-border">
                <p className="text-sm text-slate-muted mb-1">Remarks</p>
                <p className="text-foreground">{typedEntry.remarks}</p>
              </div>
            )}
          </div>

          {/* Items Table */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <Package className="w-5 h-5 text-amber-400" />
              Items ({items.length})
            </h2>
            {items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-border text-slate-muted text-left">
                      <th className="pb-3 font-medium">Item</th>
                      <th className="pb-3 font-medium text-right">Qty</th>
                      <th className="pb-3 font-medium">UoM</th>
                      <th className="pb-3 font-medium">Source</th>
                      <th className="pb-3 font-medium">Target</th>
                      <th className="pb-3 font-medium text-right">Rate</th>
                      <th className="pb-3 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-border/50">
                    {items.map((item) => (
                      <tr key={item.id}>
                        <td className="py-3">
                          <Link
                            href={`/inventory/items?search=${item.item_code}`}
                            className="text-amber-400 font-mono hover:underline"
                          >
                            {item.item_code}
                          </Link>
                          {item.item_name && (
                            <p className="text-slate-muted text-xs mt-0.5">{item.item_name}</p>
                          )}
                        </td>
                        <td className="py-3 text-right font-mono text-foreground">
                          {(item.qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 text-slate-muted">{item.uom || '-'}</td>
                        <td className="py-3 text-slate-muted text-xs">{item.s_warehouse || '-'}</td>
                        <td className="py-3 text-slate-muted text-xs">{item.t_warehouse || '-'}</td>
                        <td className="py-3 text-right font-mono text-slate-muted">
                          {(item.valuation_rate ?? item.basic_rate ?? 0).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                        <td className="py-3 text-right font-mono text-foreground">
                          {(item.amount ?? item.basic_amount ?? 0).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-slate-border">
                      <td colSpan={5} className="py-3 text-right text-slate-muted font-medium">
                        Total:
                      </td>
                      <td className="py-3 text-right font-mono text-foreground">
                        {items
                          .reduce((sum, item) => sum + (item.qty ?? 0), 0)
                          .toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 text-right font-mono text-foreground font-semibold">
                        {(typedEntry.total_amount ?? 0).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                        })}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            ) : (
              <p className="text-slate-muted">No items in this stock entry</p>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Summary Card */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h3 className="text-sm font-medium text-slate-muted mb-4">Value Summary</h3>
            <div className="space-y-4">
              <div>
                <p className="text-xs text-slate-muted">Total Incoming Value</p>
                <p className="text-xl font-bold text-emerald-400">
                  {(typedEntry.total_incoming_value ?? 0).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-muted">Total Outgoing Value</p>
                <p className="text-xl font-bold text-red-400">
                  {(typedEntry.total_outgoing_value ?? 0).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </p>
              </div>
              <div className="pt-3 border-t border-slate-border">
                <p className="text-xs text-slate-muted">Value Difference</p>
                <p className="text-xl font-bold text-amber-400">
                  {(typedEntry.value_difference ?? 0).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-muted">Total Amount</p>
                <p className="text-2xl font-bold text-foreground">
                  {(typedEntry.total_amount ?? 0).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </p>
              </div>
            </div>
          </div>

          {/* Reference Documents */}
          {(typedEntry.work_order ||
            typedEntry.purchase_order ||
            typedEntry.sales_order ||
            typedEntry.delivery_note ||
            typedEntry.purchase_receipt) && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h3 className="text-sm font-medium text-slate-muted mb-4 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Related Documents
              </h3>
              <div className="space-y-3">
                {typedEntry.work_order && (
                  <div>
                    <p className="text-xs text-slate-muted">Work Order</p>
                    <p className="text-foreground font-mono">{typedEntry.work_order}</p>
                  </div>
                )}
                {typedEntry.purchase_order && (
                  <div>
                    <p className="text-xs text-slate-muted">Purchase Order</p>
                    <Link
                      href={`/purchasing/orders?search=${typedEntry.purchase_order}`}
                      className="text-amber-400 font-mono hover:underline"
                    >
                      {typedEntry.purchase_order}
                    </Link>
                  </div>
                )}
                {typedEntry.sales_order && (
                  <div>
                    <p className="text-xs text-slate-muted">Sales Order</p>
                    <Link
                      href={`/sales/orders?search=${typedEntry.sales_order}`}
                      className="text-amber-400 font-mono hover:underline"
                    >
                      {typedEntry.sales_order}
                    </Link>
                  </div>
                )}
                {typedEntry.delivery_note && (
                  <div>
                    <p className="text-xs text-slate-muted">Delivery Note</p>
                    <p className="text-foreground font-mono">{typedEntry.delivery_note}</p>
                  </div>
                )}
                {typedEntry.purchase_receipt && (
                  <div>
                    <p className="text-xs text-slate-muted">Purchase Receipt</p>
                    <p className="text-foreground font-mono">{typedEntry.purchase_receipt}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Flags */}
          {(typedEntry.is_opening || typedEntry.is_return) && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h3 className="text-sm font-medium text-slate-muted mb-4">Flags</h3>
              <div className="space-y-2">
                {typedEntry.is_opening && (
                  <span className="inline-flex items-center px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-xs">
                    Opening Entry
                  </span>
                )}
                {typedEntry.is_return && (
                  <span className="inline-flex items-center px-2 py-1 rounded bg-orange-500/20 text-orange-400 text-xs">
                    Return Entry
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Sync Info */}
          {typedEntry.last_synced_at && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h3 className="text-sm font-medium text-slate-muted mb-2">Sync Status</h3>
              <p className="text-xs text-slate-muted">
                Last synced: {new Date(typedEntry.last_synced_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
