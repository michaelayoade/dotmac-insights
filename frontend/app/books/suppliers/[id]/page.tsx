'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Building, Phone, Mail, MapPin, Receipt, CreditCard, Pencil, Save, X, Trash2, Loader2, CheckCircle2 } from 'lucide-react';
import { usePurchasingSupplierDetail } from '@/hooks/useApi';
import { accountingApi, AccountingSupplierPayload } from '@/lib/api/domains/accounting';
import { formatCurrency, cn } from '@/lib/utils';

function formatValue(value: string | number | null | undefined, fallback = '—') {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'number') return value;
  const trimmed = value.toString().trim();
  return trimmed.length ? trimmed : fallback;
}

const SUPPLIER_TYPES = ['Company', 'Individual', 'Proprietorship', 'Partnership'] as const;

export default function SupplierDetailPage() {
  const router = useRouter();
  const params = useParams();
  const idParam = params?.id as string;
  const idNum = Number(idParam);
  const supplierId = Number.isFinite(idNum) ? idNum : null;
  const { data: supplier, isLoading, error, mutate } = usePurchasingSupplierDetail(supplierId);

  const [isEditing, setIsEditing] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [form, setForm] = useState<Partial<AccountingSupplierPayload>>({});
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (supplier) {
      setForm({
        supplier_name: supplier.name ?? supplier.supplier_name ?? undefined,
        supplier_code: supplier.code || (supplier as any).supplier_code,
        supplier_type: (supplier as any).supplier_type,
        supplier_group: (supplier as any).supplier_group,
        country: (supplier as any).country,
        default_currency: supplier.currency,
        payment_terms: (supplier as any).payment_terms,
        tax_id: (supplier as any).tax_id,
        email: supplier.email,
        phone: supplier.phone,
        disabled: (supplier as any).disabled,
      });
    }
  }, [supplier]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement;
    const { name, value, type } = target;
    const nextValue = type === 'checkbox' ? target.checked : value || null;
    setForm((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleSave = async () => {
    if (!supplierId) return;
    setSaving(true);
    setActionError(null);
    try {
      await accountingApi.updateSupplier(supplierId, form);
      setSuccess('Supplier updated successfully');
      setIsEditing(false);
      mutate();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update supplier');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!supplierId) return;
    setActionError(null);
    try {
      await accountingApi.deleteSupplier(supplierId);
      router.push('/books/suppliers');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete supplier');
      setDeleteConfirm(false);
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setActionError(null);
    if (supplier) {
      setForm({
        supplier_name: supplier.name ?? supplier.supplier_name ?? undefined,
        supplier_code: supplier.code || (supplier as any).supplier_code,
        supplier_type: (supplier as any).supplier_type,
        supplier_group: (supplier as any).supplier_group,
        country: (supplier as any).country,
        default_currency: supplier.currency,
        payment_terms: (supplier as any).payment_terms,
        tax_id: (supplier as any).tax_id,
        email: supplier.email,
        phone: supplier.phone,
        disabled: (supplier as any).disabled,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-6 space-y-3">
        <div className="h-6 w-40 bg-slate-elevated rounded animate-pulse" />
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !supplier) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Supplier not found</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const currency = supplier.currency || 'NGN';
  const outstanding = supplier.outstanding ?? supplier.total_outstanding ?? 0;
  const totalPurchases = supplier.total_purchases ?? 0;
  const cards = [
    { label: 'Outstanding', value: formatCurrency(outstanding, currency), tone: 'text-orange-400' },
    { label: 'Total Purchases', value: formatCurrency(totalPurchases, currency), tone: 'text-blue-400' },
    { label: 'Status', value: (supplier as any).disabled ? 'Disabled' : 'Active', tone: (supplier as any).disabled ? 'text-slate-400' : 'text-emerald-success' },
    { label: 'Bills', value: (supplier.bill_count ?? 0).toString(), tone: 'text-slate-200' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/suppliers"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to suppliers
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Supplier</p>
            <h1 className="text-xl font-semibold text-foreground">{supplier.name || supplier.supplier_name || `Supplier #${supplier.id}`}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <>
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
                Are you sure you want to delete this supplier?
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

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">{card.label}</p>
            <p className={`text-xl font-bold ${card.tone}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Details */}
      {isEditing ? (
        <div className="space-y-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <h3 className="text-foreground font-semibold mb-4">Basic Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Supplier Name</label>
                <input
                  name="supplier_name"
                  value={form.supplier_name || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Supplier Code</label>
                <input
                  name="supplier_code"
                  value={form.supplier_code || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Supplier Type</label>
                <select
                  name="supplier_type"
                  value={form.supplier_type || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">Select type</option>
                  {SUPPLIER_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Supplier Group</label>
                <input
                  name="supplier_group"
                  value={form.supplier_group || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <h3 className="text-foreground font-semibold mb-4">Contact & Location</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Email</label>
                <input
                  name="email"
                  type="email"
                  value={form.email || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Phone</label>
                <input
                  name="phone"
                  value={form.phone || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Country</label>
                <input
                  name="country"
                  value={form.country || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Tax ID</label>
                <input
                  name="tax_id"
                  value={form.tax_id || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <h3 className="text-foreground font-semibold mb-4">Settings</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Default Currency</label>
                <input
                  name="default_currency"
                  value={form.default_currency || ''}
                  onChange={handleChange}
                  maxLength={3}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Payment Terms</label>
                <input
                  name="payment_terms"
                  value={form.payment_terms || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  name="disabled"
                  checked={form.disabled || false}
                  onChange={handleChange}
                  className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                />
                <label className="text-sm text-slate-muted">Disabled</label>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Building className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Details</h3>
            </div>
            <p className="text-slate-200 text-sm">
              {supplier.name || supplier.supplier_name} {supplier.code ? `(${supplier.code})` : ''}
            </p>
            <div className="space-y-1 text-sm text-slate-muted">
              <div className="flex items-center gap-2"><MapPin className="w-3 h-3" />{formatValue((supplier as any).address)}</div>
              <div className="flex items-center gap-2"><Phone className="w-3 h-3" />{formatValue(supplier.phone)}</div>
              <div className="flex items-center gap-2"><Mail className="w-3 h-3" />{formatValue(supplier.email)}</div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-teal-electric" />
              <h3 className="text-foreground font-semibold">Financials</h3>
            </div>
            <p className="text-sm text-slate-200">Currency: {currency}</p>
            <p className="text-sm text-slate-200">Outstanding: {formatCurrency(outstanding, currency)}</p>
            <p className="text-sm text-slate-200">Total Purchases: {formatCurrency(totalPurchases, currency)}</p>
            <p className="text-sm text-slate-200">Credit Limit: {formatCurrency(supplier.credit_limit ?? 0, currency)}</p>
          </div>
        </div>
      )}

      {!isEditing && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Receipt className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Notes</h3>
          </div>
          <p className="text-slate-muted text-sm">{supplier.notes || 'No notes provided'}</p>
        </div>
      )}
    </div>
  );
}
