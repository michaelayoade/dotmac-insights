'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Building2 } from 'lucide-react';
import { usePurchasingSupplierMutations } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { cn } from '@/lib/utils';
import { Button, BackButton, LoadingState } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function NewSupplierPage() {
  const router = useRouter();
  const { isLoading: authLoading, missingScope } = useRequireScope('purchasing:write');
  const { createSupplier } = usePurchasingSupplierMutations();
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const [supplierName, setSupplierName] = useState('');
  const [supplierGroup, setSupplierGroup] = useState('');
  const [supplierType, setSupplierType] = useState('');
  const [country, setCountry] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [taxId, setTaxId] = useState('');
  const [paymentTerms, setPaymentTerms] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the purchasing:write permission to create suppliers."
        backHref="/purchasing/suppliers"
        backLabel="Back to Suppliers"
      />
    );
  }

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!supplierName.trim()) errs.supplierName = 'Supplier name is required';
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = 'Invalid email format';
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
        supplier_name: supplierName.trim(),
        supplier_group: supplierGroup.trim() || undefined,
        supplier_type: supplierType.trim() || undefined,
        country: country.trim() || undefined,
        default_currency: currency,
        email_id: email.trim() || undefined,
        mobile_no: mobile.trim() || undefined,
        tax_id: taxId.trim() || undefined,
        payment_terms: paymentTerms.trim() || undefined,
      };
      const created = await createSupplier(payload);
      router.push(`/purchasing/suppliers/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create supplier');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/purchasing/suppliers" label="Suppliers" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Purchasing</p>
            <h1 className="text-xl font-semibold text-foreground">New Supplier</h1>
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
            <Building2 className="w-4 h-4 text-teal-electric" />
            Supplier Details
          </h3>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Supplier Name *</label>
            <input
              type="text"
              value={supplierName}
              onChange={(e) => setSupplierName(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                fieldErrors.supplierName && 'border-red-500/60'
              )}
              placeholder="e.g., Acme Supplies Ltd."
              autoFocus
            />
            {fieldErrors.supplierName && <p className="text-xs text-red-400">{fieldErrors.supplierName}</p>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Supplier Group</label>
              <input
                type="text"
                value={supplierGroup}
                onChange={(e) => setSupplierGroup(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="e.g., Hardware, Services"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Supplier Type</label>
              <select
                value={supplierType}
                onChange={(e) => setSupplierType(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">Select Type</option>
                <option value="Company">Company</option>
                <option value="Individual">Individual</option>
                <option value="Distributor">Distributor</option>
                <option value="Manufacturer">Manufacturer</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Country</label>
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="e.g., Nigeria"
              />
            </div>
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
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 mt-4">
          <h3 className="text-foreground font-semibold">Contact Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={cn(
                  'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                  fieldErrors.email && 'border-red-500/60'
                )}
                placeholder="supplier@example.com"
              />
              {fieldErrors.email && <p className="text-xs text-red-400">{fieldErrors.email}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Mobile</label>
              <input
                type="tel"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="+234..."
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 mt-4">
          <h3 className="text-foreground font-semibold">Accounting</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Tax ID</label>
              <input
                type="text"
                value={taxId}
                onChange={(e) => setTaxId(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="e.g., TIN-12345678"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Payment Terms</label>
              <select
                value={paymentTerms}
                onChange={(e) => setPaymentTerms(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">Select Terms</option>
                <option value="Net 15">Net 15</option>
                <option value="Net 30">Net 30</option>
                <option value="Net 45">Net 45</option>
                <option value="Net 60">Net 60</option>
                <option value="Due on Receipt">Due on Receipt</option>
              </select>
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
            Create Supplier
          </Button>
        </div>
      </form>
    </div>
  );
}
