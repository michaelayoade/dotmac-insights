'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Barcode } from 'lucide-react';
import { useInventorySerialMutations, useInventoryItems } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewSerialPage() {
  const router = useRouter();
  const { create } = useInventorySerialMutations();
  const { data: items } = useInventoryItems({ limit: 200 });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [itemId, setItemId] = useState('');
  const [serialNumber, setSerialNumber] = useState('');
  const [status, setStatus] = useState('active');
  const [warrantyExpiry, setWarrantyExpiry] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!itemId) errs.itemId = 'Item is required';
    if (!serialNumber.trim()) errs.serialNumber = 'Serial number is required';
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
        serial_no: serialNumber.trim(),
        status,
        warranty_expiry_date: warrantyExpiry || undefined,
        purchase_date: purchaseDate || undefined,
      };
      await create(payload);
      router.push('/inventory/serials');
    } catch (err: any) {
      setError(err?.message || 'Failed to create serial');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/inventory/serials" label="Serials" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Inventory</p>
            <h1 className="text-xl font-semibold text-foreground">New Serial Number</h1>
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
            <Barcode className="w-4 h-4 text-purple-400" />
            Serial Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Item *</label>
            <select
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50',
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
              <label className="text-sm text-slate-muted">Serial Number *</label>
              <input
                value={serialNumber}
                onChange={(e) => setSerialNumber(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50',
                  fieldErrors.serialNumber && 'border-red-500/60'
                )}
                placeholder="SN-12345"
              />
              {fieldErrors.serialNumber && <p className="text-xs text-red-400">{fieldErrors.serialNumber}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="delivered">Delivered</option>
                <option value="expired">Expired</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Purchase Date</label>
              <input
                type="date"
                value={purchaseDate}
                onChange={(e) => setPurchaseDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Warranty Expiry</label>
              <input
                type="date"
                value={warrantyExpiry}
                onChange={(e) => setWarrantyExpiry(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50"
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
            className="bg-purple-500 hover:bg-purple-600"
          >
            Create Serial
          </Button>
        </div>
      </form>
    </div>
  );
}
