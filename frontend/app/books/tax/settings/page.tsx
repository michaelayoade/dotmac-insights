'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useTaxSettings, useTaxMutations } from '@/hooks/useApi';
import {
  Settings,
  ArrowLeft,
  AlertTriangle,
  Save,
  Building2,
  FileText,
  Calendar,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const PAYE_FILING_FREQUENCIES = [
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'QUARTERLY', label: 'Quarterly' },
  { value: 'ANNUALLY', label: 'Annually' },
];

const CIT_COMPANY_SIZES = [
  { value: 'SMALL', label: 'Small (Turnover < ₦25M)', rate: '0%' },
  { value: 'MEDIUM', label: 'Medium (Turnover ₦25M - ₦100M)', rate: '20%' },
  { value: 'LARGE', label: 'Large (Turnover > ₦100M)', rate: '30%' },
];

export default function TaxSettingsPage() {
  const { data: settings, isLoading, error } = useTaxSettings();
  const { updateSettings } = useTaxMutations();

  const [form, setForm] = useState({
    company_tin: '',
    company_name: '',
    rc_number: '',
    tax_office: '',
    vat_registered: true,
    vat_registration_number: '',
    default_vat_rate: 7.5,
    paye_filing_frequency: 'MONTHLY',
    cit_company_size: 'SMALL',
    fiscal_year_end_month: 12,
    auto_calculate_wht: true,
    einvoice_enabled: false,
    einvoice_api_key: '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm({
        company_tin: settings.company_tin || '',
        company_name: settings.company_name || '',
        rc_number: settings.rc_number || '',
        tax_office: settings.tax_office || '',
        vat_registered: settings.vat_registered ?? true,
        vat_registration_number: settings.vat_registration_number || '',
        default_vat_rate: settings.default_vat_rate ?? 7.5,
        paye_filing_frequency: settings.paye_filing_frequency || 'MONTHLY',
        cit_company_size: settings.cit_company_size || 'SMALL',
        fiscal_year_end_month: settings.fiscal_year_end_month ?? 12,
        auto_calculate_wht: settings.auto_calculate_wht ?? true,
        einvoice_enabled: settings.einvoice_enabled ?? false,
        einvoice_api_key: settings.einvoice_api_key || '',
      });
    }
  }, [settings]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      await updateSettings(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load tax settings</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Link
            href="/books/tax"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Tax
          </Link>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-muted animate-spin" />
            <h1 className="text-xl font-semibold text-white">Tax Settings</h1>
          </div>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-slate-elevated rounded animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/tax"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Tax
          </Link>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-muted" />
            <h1 className="text-xl font-semibold text-white">Tax Settings</h1>
          </div>
        </div>
        {saved && (
          <div className="flex items-center gap-2 text-emerald-400 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            Settings saved
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Company Information */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="w-5 h-5 text-purple-400" />
            <h2 className="text-white font-semibold">Company Information</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Company TIN *</label>
              <input
                type="text"
                value={form.company_tin}
                onChange={(e) => setForm({ ...form, company_tin: e.target.value })}
                className="input-field"
                placeholder="12345678-0001"
                required
              />
              <p className="text-xs text-slate-muted">Tax Identification Number assigned by FIRS</p>
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Company Name</label>
              <input
                type="text"
                value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                className="input-field"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">RC Number</label>
              <input
                type="text"
                value={form.rc_number}
                onChange={(e) => setForm({ ...form, rc_number: e.target.value })}
                className="input-field"
                placeholder="RC123456"
              />
              <p className="text-xs text-slate-muted">Corporate Affairs Commission registration number</p>
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Tax Office</label>
              <input
                type="text"
                value={form.tax_office}
                onChange={(e) => setForm({ ...form, tax_office: e.target.value })}
                className="input-field"
                placeholder="e.g., Lagos Mainland"
              />
            </div>
          </div>
        </div>

        {/* VAT Settings */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-blue-400" />
            <h2 className="text-white font-semibold">VAT Settings</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.vat_registered}
                  onChange={(e) => setForm({ ...form, vat_registered: e.target.checked })}
                  className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric"
                />
                <span className="text-sm text-white">VAT Registered</span>
              </label>
              <p className="text-xs text-slate-muted ml-6">Check if your company is registered for VAT</p>
            </div>
            {form.vat_registered && (
              <>
                <div className="space-y-1.5">
                  <label className="block text-sm text-slate-muted">VAT Registration Number</label>
                  <input
                    type="text"
                    value={form.vat_registration_number}
                    onChange={(e) => setForm({ ...form, vat_registration_number: e.target.value })}
                    className="input-field"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-sm text-slate-muted">Default VAT Rate (%)</label>
                  <input
                    type="number"
                    value={form.default_vat_rate}
                    onChange={(e) => setForm({ ...form, default_vat_rate: Number(e.target.value) })}
                    className="input-field"
                    step="0.1"
                    min={0}
                    max={100}
                  />
                  <p className="text-xs text-slate-muted">Standard rate is 7.5%</p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* WHT & PAYE Settings */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-5 h-5 text-emerald-400" />
            <h2 className="text-white font-semibold">WHT & PAYE Settings</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.auto_calculate_wht}
                  onChange={(e) => setForm({ ...form, auto_calculate_wht: e.target.checked })}
                  className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric"
                />
                <span className="text-sm text-white">Auto-calculate WHT</span>
              </label>
              <p className="text-xs text-slate-muted ml-6">Automatically calculate WHT on applicable transactions</p>
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">PAYE Filing Frequency</label>
              <select
                value={form.paye_filing_frequency}
                onChange={(e) => setForm({ ...form, paye_filing_frequency: e.target.value })}
                className="input-field"
              >
                {PAYE_FILING_FREQUENCIES.map((freq) => (
                  <option key={freq.value} value={freq.value}>{freq.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* CIT Settings */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="w-5 h-5 text-purple-400" />
            <h2 className="text-white font-semibold">CIT Settings</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Company Size (CIT Rate)</label>
              <select
                value={form.cit_company_size}
                onChange={(e) => setForm({ ...form, cit_company_size: e.target.value })}
                className="input-field"
              >
                {CIT_COMPANY_SIZES.map((size) => (
                  <option key={size.value} value={size.value}>{size.label} - {size.rate}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Fiscal Year End Month</label>
              <select
                value={form.fiscal_year_end_month}
                onChange={(e) => setForm({ ...form, fiscal_year_end_month: Number(e.target.value) })}
                className="input-field"
              >
                {Array.from({ length: 12 }, (_, i) => {
                  const month = new Date(2024, i).toLocaleString('en', { month: 'long' });
                  return <option key={i + 1} value={i + 1}>{month}</option>;
                })}
              </select>
              <p className="text-xs text-slate-muted">Most companies use December (12)</p>
            </div>
          </div>
        </div>

        {/* E-Invoice Settings */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-teal-electric" />
            <h2 className="text-white font-semibold">E-Invoice (FIRS BIS 3.0)</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.einvoice_enabled}
                  onChange={(e) => setForm({ ...form, einvoice_enabled: e.target.checked })}
                  className="rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric"
                />
                <span className="text-sm text-white">Enable E-Invoicing</span>
              </label>
              <p className="text-xs text-slate-muted ml-6">Submit invoices to FIRS for validation</p>
            </div>
            {form.einvoice_enabled && (
              <div className="space-y-1.5">
                <label className="block text-sm text-slate-muted">FIRS API Key</label>
                <input
                  type="password"
                  value={form.einvoice_api_key}
                  onChange={(e) => setForm({ ...form, einvoice_api_key: e.target.value })}
                  className="input-field"
                  placeholder="••••••••••••"
                />
                <p className="text-xs text-slate-muted">Obtain from FIRS e-invoice portal</p>
              </div>
            )}
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-white font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            {saving ? (
              <>
                <Settings className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                Save Settings
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
