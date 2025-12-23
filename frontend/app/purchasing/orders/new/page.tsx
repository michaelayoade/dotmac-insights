'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ShoppingCart } from 'lucide-react';
import { usePurchasingOrderMutations, usePurchasingSuppliers } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton, LoadingState } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function NewPurchaseOrderPage() {
  const router = useRouter();
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:write');
  const { createOrder } = usePurchasingOrderMutations();
  const { data: suppliersData } = usePurchasingSuppliers({ limit: 100, offset: 0 });
  const suppliers = suppliersData?.suppliers || suppliersData?.items || [];
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [supplier, setSupplier] = useState('');
  const [orderDate, setOrderDate] = useState(new Date().toISOString().split('T')[0]);
  const [deliveryDate, setDeliveryDate] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [grandTotal, setGrandTotal] = useState('');
  const [costCenter, setCostCenter] = useState('');
  const [project, setProject] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:write permission to create purchase orders."
        backHref="/purchasing/orders"
        backLabel="Back to Orders"
      />
    );
  }

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!supplier) errs.supplier = 'Supplier is required';
    if (!orderDate) errs.orderDate = 'Order date is required';
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
        supplier,
        transaction_date: orderDate,
        schedule_date: deliveryDate || undefined,
        currency,
        grand_total: grandTotal ? Number(grandTotal) : undefined,
        cost_center: costCenter.trim() || undefined,
        project: project.trim() || undefined,
        status: 'Draft',
      };
      const created = await createOrder(payload);
      router.push(`/purchasing/orders/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create purchase order');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/purchasing/orders" label="Orders" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Purchasing</p>
            <h1 className="text-xl font-semibold text-foreground">New Purchase Order</h1>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="max-w-2xl">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <ShoppingCart className="w-4 h-4 text-teal-electric" />
            Order Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Supplier *</label>
            <select
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                fieldErrors.supplier && 'border-red-500/60'
              )}
            >
              <option value="">Select Supplier</option>
              {suppliers.map((s: any) => (
                <option key={s.id} value={s.name || s.supplier_name}>
                  {s.name || s.supplier_name}
                </option>
              ))}
            </select>
            {fieldErrors.supplier && <p className="text-xs text-red-400">{fieldErrors.supplier}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Order Date *</label>
              <input
                type="date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.orderDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.orderDate && <p className="text-xs text-red-400">{fieldErrors.orderDate}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Expected Delivery</label>
              <input
                type="date"
                value={deliveryDate}
                onChange={(e) => setDeliveryDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="NGN">NGN</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Estimated Total</label>
              <input
                type="number"
                value={grandTotal}
                onChange={(e) => setGrandTotal(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="0.00"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Cost Center</label>
              <input
                type="text"
                value={costCenter}
                onChange={(e) => setCostCenter(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="e.g., Main Office"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Project</label>
              <input
                type="text"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Link to project"
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
            className="bg-teal-electric hover:bg-teal-electric/90"
          >
            Create Order
          </Button>
        </div>
      </form>
    </div>
  );
}
