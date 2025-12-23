'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Receipt } from 'lucide-react';
import { usePurchasingBillMutations, usePurchasingSuppliers } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton } from '@/components/ui';

export default function NewBillPage() {
  const router = useRouter();
  const { createBill } = usePurchasingBillMutations();
  const { data: suppliersData } = usePurchasingSuppliers({ limit: 100, offset: 0 });
  const suppliers = suppliersData?.suppliers || suppliersData?.items || [];
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [supplierId, setSupplierId] = useState('');
  const [billDate, setBillDate] = useState(new Date().toISOString().split('T')[0]);
  const [dueDate, setDueDate] = useState('');
  const [billNumber, setBillNumber] = useState('');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [description, setDescription] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!supplierId) errs.supplierId = 'Supplier is required';
    if (!billDate) errs.billDate = 'Bill date is required';
    if (!amount) errs.amount = 'Amount is required';
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
        supplier_id: Number(supplierId),
        posting_date: billDate,
        due_date: dueDate || undefined,
        bill_no: billNumber.trim() || undefined,
        grand_total: Number(amount),
        currency,
        remarks: description.trim() || undefined,
      };
      const created = await createBill(payload);
      router.push(`/purchasing/bills/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create bill');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/purchasing/bills" label="Bills" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Purchasing</p>
            <h1 className="text-xl font-semibold text-foreground">New Purchase Bill</h1>
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
            <Receipt className="w-4 h-4 text-amber-400" />
            Bill Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Supplier *</label>
            <select
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50',
                fieldErrors.supplierId && 'border-red-500/60'
              )}
            >
              <option value="">Select Supplier</option>
              {suppliers.map((supplier: any) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name || supplier.supplier_name}
                </option>
              ))}
            </select>
            {fieldErrors.supplierId && <p className="text-xs text-red-400">{fieldErrors.supplierId}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Bill Number</label>
              <input
                value={billNumber}
                onChange={(e) => setBillNumber(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                placeholder="Supplier's bill reference"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="NGN">NGN</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Bill Date *</label>
              <input
                type="date"
                value={billDate}
                onChange={(e) => setBillDate(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50',
                  fieldErrors.billDate && 'border-red-500/60'
                )}
              />
              {fieldErrors.billDate && <p className="text-xs text-red-400">{fieldErrors.billDate}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Amount *</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50',
                fieldErrors.amount && 'border-red-500/60'
              )}
              placeholder="0.00"
            />
            {fieldErrors.amount && <p className="text-xs text-red-400">{fieldErrors.amount}</p>}
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description / Remarks</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              placeholder="Bill description or notes..."
            />
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
            className="bg-amber-500 hover:bg-amber-600"
          >
            Create Bill
          </Button>
        </div>
      </form>
    </div>
  );
}
