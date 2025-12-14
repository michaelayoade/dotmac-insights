'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Building, Phone, Mail, MapPin, Receipt, CreditCard } from 'lucide-react';
import { usePurchasingSupplierDetail } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';

function formatValue(value: string | number | null | undefined, fallback = '—') {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'number') return value;
  const trimmed = value.toString().trim();
  return trimmed.length ? trimmed : fallback;
}

export default function SupplierDetailPage() {
  const router = useRouter();
  const params = useParams();
  const idParam = params?.id as string;
  const idNum = Number(idParam);
  const supplierId = Number.isFinite(idNum) ? idNum : null;
  const { data: supplier, isLoading, error } = usePurchasingSupplierDetail(supplierId);

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
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
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
    { label: 'Status', value: supplier.status || 'active', tone: 'text-slate-200' },
    { label: 'Bills', value: (supplier.bill_count ?? 0).toString(), tone: 'text-slate-200' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/suppliers"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to suppliers
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Supplier</p>
            <h1 className="text-xl font-semibold text-white">{supplier.name || supplier.supplier_name || `Supplier #${supplier.id}`}</h1>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm">{card.label}</p>
            <p className={`text-xl font-bold ${card.tone}`}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Building className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Details</h3>
          </div>
          <p className="text-slate-200 text-sm">
            {supplier.name || supplier.supplier_name} {supplier.code ? `(${supplier.code})` : ''}
          </p>
          <div className="space-y-1 text-sm text-slate-muted">
            <div className="flex items-center gap-2"><MapPin className="w-3 h-3" />{formatValue(supplier.address)}</div>
            <div className="flex items-center gap-2"><Phone className="w-3 h-3" />{formatValue(supplier.phone)}</div>
            <div className="flex items-center gap-2"><Mail className="w-3 h-3" />{formatValue(supplier.email)}</div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Financials</h3>
          </div>
          <p className="text-sm text-slate-200">Currency: {currency}</p>
          <p className="text-sm text-slate-200">Outstanding: {formatCurrency(outstanding, currency)}</p>
          <p className="text-sm text-slate-200">Total Purchases: {formatCurrency(totalPurchases, currency)}</p>
          <p className="text-sm text-slate-200">Credit Limit: {formatCurrency(supplier.credit_limit ?? 0, currency)}</p>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <Receipt className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Notes</h3>
        </div>
        <p className="text-slate-muted text-sm">{supplier.notes || 'No notes provided'}</p>
      </div>
    </div>
  );
}
