'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import {
  ArrowLeft,
  Package,
  Pencil,
  Save,
  X,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Warehouse,
  BarChart3,
} from 'lucide-react';
import { inventoryApi, InventoryItemPayload } from '@/lib/api/domains/inventory';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';
import { cn } from '@/lib/utils';

export default function ItemDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [isEditing, setIsEditing] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [form, setForm] = useState<InventoryItemPayload>({});
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const itemRes = useSWR(`inventory-item-${id}`, () => inventoryApi.getItemDetail(id));
  const { isLoading, error, retry } = useSWRStatus(itemRes);
  const item = itemRes.data;

  useEffect(() => {
    if (item) {
      setForm({
        item_code: item.item_code,
        item_name: item.item_name,
        item_group: item.item_group,
        uom: item.stock_uom,
        is_stock_item: item.is_stock_item,
        valuation_rate: item.valuation_rate,
      });
    }
  }, [item]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const target = e.target as HTMLInputElement;
    const { name, value, type } = target;
    const nextValue = type === 'checkbox' ? target.checked : value;
    setForm((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleSave = async () => {
    setSaving(true);
    setActionError(null);
    try {
      await inventoryApi.updateItem(id, {
        ...form,
        valuation_rate: form.valuation_rate ? Number(form.valuation_rate) : undefined,
      });
      setSuccess('Item updated successfully');
      setIsEditing(false);
      itemRes.mutate();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update item');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setActionError(null);
    try {
      await inventoryApi.deleteItem(id);
      router.push('/inventory/items');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete item');
      setDeleteConfirm(false);
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setActionError(null);
    if (item) {
      setForm({
        item_code: item.item_code,
        item_name: item.item_name,
        item_group: item.item_group,
        uom: item.stock_uom,
        is_stock_item: item.is_stock_item,
        valuation_rate: item.valuation_rate,
      });
    }
  };

  return (
    <DashboardShell isLoading={isLoading} error={error} onRetry={retry}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/inventory/items"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Link>
            <div className="flex items-center gap-2">
              <Package className="w-5 h-5 text-amber-500" />
              <h1 className="text-xl font-semibold text-foreground">
                {item?.item_code || 'Item Details'}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <>
                <Link
                  href={`/inventory/valuation/${encodeURIComponent(item?.item_code || '')}`}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted text-sm hover:text-foreground hover:border-slate-border/70"
                >
                  <BarChart3 className="w-4 h-4" />
                  Valuation
                </Link>
                <button
                  onClick={() => setIsEditing(true)}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
                >
                  <Pencil className="w-4 h-4" />
                  Edit
                </button>
                <button
                  onClick={() => setDeleteConfirm(true)}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-coral-alert/10 border border-coral-alert/30 text-coral-alert text-sm hover:bg-coral-alert/20"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-foreground text-sm font-medium hover:bg-teal-glow disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save
                </button>
                <button
                  onClick={cancelEdit}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-slate-muted text-sm hover:bg-slate-border"
                >
                  <X className="w-4 h-4" />
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>

        {/* Delete Confirmation */}
        {deleteConfirm && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-coral-alert" />
                <span className="text-coral-alert font-medium">
                  Are you sure you want to delete this item?
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDelete}
                  className="px-3 py-1.5 rounded-lg bg-coral-alert text-foreground text-sm font-medium hover:bg-coral-alert/80"
                >
                  Yes, Delete
                </button>
                <button
                  onClick={() => setDeleteConfirm(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-elevated text-slate-muted text-sm hover:bg-slate-border"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {actionError && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-coral-alert" />
            <span className="text-sm text-coral-alert">{actionError}</span>
          </div>
        )}
        {success && (
          <div className="bg-emerald-success/10 border border-emerald-success/30 rounded-lg p-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-success" />
            <span className="text-sm text-emerald-success">{success}</span>
          </div>
        )}

        {/* Item Details */}
        {item && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main Info */}
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                <h2 className="text-sm font-medium text-slate-muted mb-4">Basic Information</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Item Code</label>
                    {isEditing ? (
                      <input
                        name="item_code"
                        value={form.item_code || ''}
                        onChange={handleChange}
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                    ) : (
                      <p className="text-foreground font-mono">{item.item_code}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Item Name</label>
                    {isEditing ? (
                      <input
                        name="item_name"
                        value={form.item_name || ''}
                        onChange={handleChange}
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                    ) : (
                      <p className="text-foreground">{item.item_name}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Item Group</label>
                    {isEditing ? (
                      <input
                        name="item_group"
                        value={form.item_group || ''}
                        onChange={handleChange}
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                    ) : (
                      <p className="text-foreground">{item.item_group || '-'}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Unit of Measure</label>
                    {isEditing ? (
                      <input
                        name="uom"
                        value={form.uom || ''}
                        onChange={handleChange}
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                    ) : (
                      <p className="text-foreground">{item.stock_uom || '-'}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Stock Item</label>
                    {isEditing ? (
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          name="is_stock_item"
                          checked={form.is_stock_item || false}
                          onChange={handleChange}
                          className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                        />
                        <span className="text-sm text-slate-muted">Track inventory</span>
                      </label>
                    ) : (
                      <p className="text-foreground">
                        {item.is_stock_item ? (
                          <span className="text-emerald-success">Yes</span>
                        ) : (
                          <span className="text-slate-muted">No</span>
                        )}
                      </p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-muted">Valuation Rate</label>
                    {isEditing ? (
                      <input
                        name="valuation_rate"
                        type="number"
                        step="0.01"
                        value={form.valuation_rate || ''}
                        onChange={handleChange}
                        className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                      />
                    ) : (
                      <p className="text-foreground font-mono">
                        {(item.valuation_rate ?? 0).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Side Info */}
            <div className="space-y-6">
              {/* Stock Summary */}
              <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                <h2 className="text-sm font-medium text-slate-muted mb-4">Stock Summary</h2>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-slate-muted">Total Stock Quantity</p>
                    <p
                      className={cn(
                        'text-2xl font-mono font-bold',
                        (item.total_stock_qty ?? 0) > 0 ? 'text-emerald-success' : 'text-slate-muted'
                      )}
                    >
                      {(item.total_stock_qty ?? 0).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-muted">Total Stock Value</p>
                    <p className="text-xl font-mono text-foreground">
                      {(
                        (item.total_stock_qty ?? 0) * (item.valuation_rate ?? 0)
                      ).toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </p>
                  </div>
                </div>
              </div>

              {/* Stock by Warehouse */}
              {item.stock_by_warehouse && Object.keys(item.stock_by_warehouse).length > 0 && (
                <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                  <h2 className="text-sm font-medium text-slate-muted mb-4 flex items-center gap-2">
                    <Warehouse className="w-4 h-4" />
                    Stock by Warehouse
                  </h2>
                  <div className="space-y-3">
                    {Object.entries(item.stock_by_warehouse).map(([warehouse, qty]) => (
                      <div
                        key={warehouse}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-slate-muted truncate">{warehouse}</span>
                        <span
                          className={cn(
                            'font-mono',
                            (qty as number) > 0 ? 'text-emerald-success' : 'text-slate-muted'
                          )}
                        >
                          {(qty as number).toLocaleString(undefined, {
                            maximumFractionDigits: 2,
                          })}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Quick Links */}
              <div className="bg-slate-card border border-slate-border rounded-xl p-6">
                <h2 className="text-sm font-medium text-slate-muted mb-4">Quick Links</h2>
                <div className="space-y-2">
                  <Link
                    href={`/inventory/stock-ledger?item_code=${encodeURIComponent(item.item_code)}`}
                    className="block text-sm text-teal-electric hover:text-teal-glow"
                  >
                    View Stock Ledger
                  </Link>
                  <Link
                    href={`/inventory/valuation/${encodeURIComponent(item.item_code)}`}
                    className="block text-sm text-teal-electric hover:text-teal-glow"
                  >
                    View Valuation Details
                  </Link>
                  <Link
                    href={`/inventory/batches?item_code=${encodeURIComponent(item.item_code)}`}
                    className="block text-sm text-teal-electric hover:text-teal-glow"
                  >
                    View Batches
                  </Link>
                  <Link
                    href={`/inventory/serials?item_code=${encodeURIComponent(item.item_code)}`}
                    className="block text-sm text-teal-electric hover:text-teal-glow"
                  >
                    View Serial Numbers
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
