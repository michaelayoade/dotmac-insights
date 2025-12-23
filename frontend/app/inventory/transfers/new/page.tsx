"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  useInventoryWarehouses,
  useInventoryItems,
  useInventoryTransferMutations,
} from "@/hooks/useApi";
import { Button } from '@/components/ui';
import {
  ArrowRightLeft,
  ArrowLeft,
  Plus,
  Trash2,
  Loader2,
  Save,
} from "lucide-react";

interface TransferItem {
  item_code: string;
  item_name: string;
  qty: number;
  uom: string;
  valuation_rate: number;
  batch_no?: string;
  serial_no?: string;
}

export default function NewTransferPage() {
  const router = useRouter();
  const { data: warehousesData, isLoading: warehousesLoading } = useInventoryWarehouses({ limit: 200 });
  const { data: itemsData, isLoading: itemsLoading } = useInventoryItems({ limit: 500 });
  const { create: createTransfer } = useInventoryTransferMutations();

  const [fromWarehouse, setFromWarehouse] = useState("");
  const [toWarehouse, setToWarehouse] = useState("");
  const [requiredDate, setRequiredDate] = useState("");
  const [remarks, setRemarks] = useState("");
  const [items, setItems] = useState<TransferItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const warehouses = warehousesData?.warehouses || [];
  const allItems = itemsData?.items || [];

  const addItem = () => {
    setItems([
      ...items,
      { item_code: "", item_name: "", qty: 1, uom: "Nos", valuation_rate: 0 },
    ]);
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: keyof TransferItem, value: string | number) => {
    const updated = [...items];
    if (field === "item_code") {
      const selected = allItems.find((i: any) => i.item_code === value);
      updated[index] = {
        ...updated[index],
        item_code: value as string,
        item_name: selected?.item_name || "",
        uom: selected?.stock_uom || "Nos",
        valuation_rate: selected?.valuation_rate || 0,
      };
    } else {
      updated[index] = { ...updated[index], [field]: value };
    }
    setItems(updated);
  };

  const totalQty = items.reduce((sum, i) => sum + (i.qty || 0), 0);
  const totalValue = items.reduce((sum, i) => sum + (i.qty || 0) * (i.valuation_rate || 0), 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fromWarehouse || !toWarehouse || items.length === 0) {
      setError("Please fill in warehouses and add at least one item");
      return;
    }
    if (fromWarehouse === toWarehouse) {
      setError("Source and target warehouses must be different");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const payload = {
        from_warehouse: fromWarehouse,
        to_warehouse: toWarehouse,
        required_date: requiredDate || undefined,
        remarks: remarks || undefined,
        items: items.map((i, idx) => ({
          item_code: i.item_code,
          item_name: i.item_name,
          qty: i.qty,
          uom: i.uom,
          valuation_rate: i.valuation_rate,
          amount: i.qty * i.valuation_rate,
          batch_no: i.batch_no,
          serial_no: i.serial_no,
          idx: idx + 1,
        })),
      };
      await createTransfer(payload);
      router.push("/inventory/transfers");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create transfer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/inventory/transfers"
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-foreground">New Transfer Request</h1>
          <p className="text-slate-muted text-sm">Create a stock transfer between warehouses</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
            {error}
          </div>
        )}

        <div className="bg-slate-card border border-slate-border rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-amber-400" />
            Transfer Details
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">From Warehouse *</label>
              <select
                value={fromWarehouse}
                onChange={(e) => setFromWarehouse(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                required
                disabled={warehousesLoading}
              >
                <option value="">Select source warehouse</option>
                {warehouses.map((w: any) => (
                  <option key={w.erpnext_id || w.id} value={w.warehouse_name}>
                    {w.warehouse_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">To Warehouse *</label>
              <select
                value={toWarehouse}
                onChange={(e) => setToWarehouse(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                required
                disabled={warehousesLoading}
              >
                <option value="">Select target warehouse</option>
                {warehouses.map((w: any) => (
                  <option key={w.erpnext_id || w.id} value={w.warehouse_name}>
                    {w.warehouse_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Required Date</label>
              <input
                type="date"
                value={requiredDate}
                onChange={(e) => setRequiredDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Remarks</label>
              <input
                type="text"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Optional notes"
                className="w-full px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Items</h2>
            <Button
              type="button"
              onClick={addItem}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors text-sm"
            >
              <Plus className="w-4 h-4" />
              Add Item
            </Button>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-8 text-slate-muted">
              <p>No items added yet</p>
              <Button
                type="button"
                onClick={addItem}
                className="mt-2 text-amber-400 hover:text-amber-300"
              >
                Add your first item
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-border text-slate-muted text-left">
                    <th className="pb-3 font-medium">Item</th>
                    <th className="pb-3 font-medium w-24">Qty</th>
                    <th className="pb-3 font-medium w-24">UoM</th>
                    <th className="pb-3 font-medium w-32 text-right">Rate</th>
                    <th className="pb-3 font-medium w-32 text-right">Amount</th>
                    <th className="pb-3 w-12"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-border/50">
                  {items.map((item, idx) => (
                    <tr key={idx}>
                      <td className="py-2">
                        <select
                          value={item.item_code}
                          onChange={(e) => updateItem(idx, "item_code", e.target.value)}
                          className="w-full px-2 py-1.5 rounded border border-slate-border bg-slate-elevated text-foreground text-sm"
                          disabled={itemsLoading}
                        >
                          <option value="">Select item</option>
                          {allItems.map((i: any) => (
                            <option key={i.item_code} value={i.item_code}>
                              {i.item_code} - {i.item_name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2">
                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={item.qty}
                          onChange={(e) => updateItem(idx, "qty", parseFloat(e.target.value) || 0)}
                          className="w-full px-2 py-1.5 rounded border border-slate-border bg-slate-elevated text-foreground text-sm text-right"
                        />
                      </td>
                      <td className="py-2">
                        <input
                          type="text"
                          value={item.uom}
                          onChange={(e) => updateItem(idx, "uom", e.target.value)}
                          className="w-full px-2 py-1.5 rounded border border-slate-border bg-slate-elevated text-foreground text-sm"
                        />
                      </td>
                      <td className="py-2 text-right font-mono text-slate-muted">
                        {item.valuation_rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-2 text-right font-mono text-foreground">
                        {(item.qty * item.valuation_rate).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-2">
                        <Button
                          type="button"
                          onClick={() => removeItem(idx)}
                          className="p-1.5 text-red-400 hover:bg-red-500/20 rounded transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-slate-border">
                    <td colSpan={2} className="py-3 text-right text-slate-muted font-medium">
                      Total:
                    </td>
                    <td className="py-3 text-right font-mono text-foreground">
                      {totalQty.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td></td>
                    <td className="py-3 text-right font-mono text-foreground font-semibold">
                      {totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-4">
          <Link
            href="/inventory/transfers"
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
          >
            Cancel
          </Link>
          <Button
            type="submit"
            disabled={saving || items.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Create Transfer
          </Button>
        </div>
      </form>
    </div>
  );
}
