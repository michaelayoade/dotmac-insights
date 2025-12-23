'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Boxes } from 'lucide-react';
import { useInventoryBatchMutations, useInventoryItems } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewBatchPage() {
  const router = useRouter();
  const { create } = useInventoryBatchMutations();
  const { data: items } = useInventoryItems({ limit: 200 });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [itemId, setItemId] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [quantity, setQuantity] = useState('');
  const [manufacturingDate, setManufacturingDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [lotNumber, setLotNumber] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!itemId) errs.itemId = 'Item is required';
    if (!batchNumber.trim()) errs.batchNumber = 'Batch number is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = {
        item_id: Number(itemId),
        batch_no: batchNumber.trim(),
        qty: quantity ? Number(quantity) : undefined,
        manufacturing_date: manufacturingDate || undefined,
        expiry_date: expiryDate || undefined,
        lot_no: lotNumber.trim() || undefined,
      };
      await create(payload);
      router.push('/inventory/batches');
    } catch (err: any) {
      setError(err?.message || 'Failed to create batch');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/inventory/batches" label="Batches" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Inventory</p>
            <h1 className="text-xl font-semibold text-foreground">New Batch</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="max-w-xl">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Boxes className="w-4 h-4 text-cyan-400" />
            Batch Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Item *</label>
            <select
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50',
                fieldErrors.itemId && 'border-red-500/60'
              )}
            >
              <option value="">Select Item</option>
              {items?.items?.map((item: any) => (
                <option key={item.id} value={item.id}>{item.item_code} - {item.item_name}</option>
              ))}
            </select>
            {fieldErrors.itemId && <p className="text-xs text-red-400">{fieldErrors.itemId}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Batch Number *</label>
              <input
                value={batchNumber}
                onChange={(e) => setBatchNumber(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50',
                  fieldErrors.batchNumber && 'border-red-500/60'
                )}
                placeholder="BATCH-001"
              />
              {fieldErrors.batchNumber && <p className="text-xs text-red-400">{fieldErrors.batchNumber}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Lot Number</label>
              <input
                value={lotNumber}
                onChange={(e) => setLotNumber(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                placeholder="Optional"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Quantity</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              placeholder="0"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Manufacturing Date</label>
              <input
                type="date"
                value={manufacturingDate}
                onChange={(e) => setManufacturingDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Expiry Date</label>
              <input
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.back()}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            loading={submitting}
            className="bg-cyan-500 hover:bg-cyan-600"
          >
            Create Batch
          </Button>
        </div>
      </form>
    </div>
  );
}
