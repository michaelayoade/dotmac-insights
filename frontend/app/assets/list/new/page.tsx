'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Package } from 'lucide-react';
import { useAssetMutations, useAssetCategories } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewAssetPage() {
  const router = useRouter();
  const { createAsset } = useAssetMutations();
  const { data: categories } = useAssetCategories();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [assetName, setAssetName] = useState('');
  const [assetCode, setAssetCode] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [purchaseCost, setPurchaseCost] = useState('');
  const [location, setLocation] = useState('');
  const [serialNumber, setSerialNumber] = useState('');
  const [depreciationMethod, setDepreciationMethod] = useState('straight_line');
  const [usefulLife, setUsefulLife] = useState('');
  const [salvageValue, setSalvageValue] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!assetName.trim()) errs.assetName = 'Asset name is required';
    if (!assetCode.trim()) errs.assetCode = 'Asset code is required';
    if (!purchaseDate) errs.purchaseDate = 'Purchase date is required';
    if (!purchaseCost) errs.purchaseCost = 'Purchase cost is required';
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
        asset_name: assetName.trim(),
        asset_code: assetCode.trim(),
        category_id: categoryId ? Number(categoryId) : undefined,
        purchase_date: purchaseDate,
        purchase_cost: Number(purchaseCost),
        location: location.trim() || undefined,
        serial_number: serialNumber.trim() || undefined,
        depreciation_method: depreciationMethod,
        useful_life_years: usefulLife ? Number(usefulLife) : undefined,
        salvage_value: salvageValue ? Number(salvageValue) : undefined,
      };
      const created = await createAsset(payload);
      router.push(`/assets/list/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create asset');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/assets/list" label="Assets" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Asset Management</p>
            <h1 className="text-xl font-semibold text-foreground">New Asset</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Package className="w-4 h-4 text-teal-electric" />
            Asset Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Asset Code *</label>
              <input
                value={assetCode}
                onChange={(e) => setAssetCode(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.assetCode && 'border-red-500/60'
                )}
                placeholder="AST-001"
              />
              {fieldErrors.assetCode && <p className="text-xs text-red-400">{fieldErrors.assetCode}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Asset Name *</label>
              <input
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.assetName && 'border-red-500/60'
                )}
                placeholder="Office Laptop"
              />
              {fieldErrors.assetName && <p className="text-xs text-red-400">{fieldErrors.assetName}</p>}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">Select Category</option>
                {categories?.map((cat: any) => (
                  <option key={cat.id} value={cat.id}>{cat.category_name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Serial Number</label>
              <input
                value={serialNumber}
                onChange={(e) => setSerialNumber(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="SN12345"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Purchase Date *</label>
              <input
                type="date"
                value={purchaseDate}
                onChange={(e) => setPurchaseDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.purchaseDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.purchaseDate && <p className="text-xs text-red-400">{fieldErrors.purchaseDate}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Purchase Cost *</label>
              <input
                type="number"
                value={purchaseCost}
                onChange={(e) => setPurchaseCost(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.purchaseCost && 'border-red-500/60'
                )}
                placeholder="0"
              />
              {fieldErrors.purchaseCost && <p className="text-xs text-red-400">{fieldErrors.purchaseCost}</p>}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Location</label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="Head Office - Floor 2"
            />
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Package className="w-4 h-4 text-teal-electric" />
            Depreciation Settings
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Depreciation Method</label>
            <select
              value={depreciationMethod}
              onChange={(e) => setDepreciationMethod(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="straight_line">Straight Line</option>
              <option value="declining_balance">Declining Balance</option>
              <option value="double_declining">Double Declining</option>
              <option value="sum_of_years">Sum of Years' Digits</option>
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Useful Life (Years)</label>
              <input
                type="number"
                value={usefulLife}
                onChange={(e) => setUsefulLife(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="5"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Salvage Value</label>
              <input
                type="number"
                value={salvageValue}
                onChange={(e) => setSalvageValue(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="0"
              />
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 flex justify-end gap-3">
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
            module="assets"
          >
            Create Asset
          </Button>
        </div>
      </form>
    </div>
  );
}
