'use client';

import { useState, useEffect } from 'react';
import {
  Settings,
  Hash,
  Coins,
  Calendar,
  FileText,
  Plus,
  Pencil,
  Trash2,
  Check,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useBooksSettings,
  useNumberFormats,
  useCurrencies,
  useBooksSettingsMutations,
  useNumberFormatMutations,
  useCurrencyMutations,
} from '@/hooks/useApi';
import type { DocumentNumberFormatResponse, DocumentType, ResetFrequency } from '@/lib/api';

type TabKey = 'general' | 'formats' | 'currencies';

const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'general', label: 'General Settings', icon: Settings },
  { key: 'formats', label: 'Number Formats', icon: Hash },
  { key: 'currencies', label: 'Currencies', icon: Coins },
];

const documentTypeLabels: Record<DocumentType, string> = {
  invoice: 'Sales Invoice',
  bill: 'Purchase Bill',
  payment: 'Payment Voucher',
  receipt: 'Receipt',
  credit_note: 'Credit Note',
  debit_note: 'Debit Note',
  journal_entry: 'Journal Entry',
  purchase_order: 'Purchase Order',
  sales_order: 'Sales Order',
  quotation: 'Quotation',
  delivery_note: 'Delivery Note',
  goods_receipt: 'Goods Receipt',
};

const resetFrequencyLabels: Record<ResetFrequency, string> = {
  never: 'Never',
  yearly: 'Yearly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
};

type DateFormatType = 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD' | 'DD-MMM-YYYY';
type NumberFormatType = '1,234.56' | '1.234,56' | '1 234,56' | '1,23,456.78';
type RoundingMethod = 'half_up' | 'half_down' | 'bankers';
type NegativeFormat = 'minus' | 'parentheses';
type SymbolPosition = 'before' | 'after';

type BooksSettingsResponse = {
  base_currency?: string;
  currency_precision?: number;
  quantity_precision?: number;
  rate_precision?: number;
  exchange_rate_precision?: number;
  rounding_method?: RoundingMethod;
  fiscal_year_start_month?: number;
  fiscal_year_start_day?: number;
  auto_create_fiscal_years?: boolean;
  auto_create_fiscal_periods?: boolean;
  date_format?: DateFormatType;
  number_format?: NumberFormatType;
  negative_format?: NegativeFormat;
  currency_symbol_position?: SymbolPosition;
  backdating_days_allowed?: number;
  future_posting_days_allowed?: number;
  require_posting_in_open_period?: boolean;
  auto_voucher_numbering?: boolean;
  allow_duplicate_party_invoice?: boolean;
  require_attachment_journal_entry?: boolean;
  require_attachment_expense?: boolean;
  require_attachment_payment?: boolean;
  require_attachment_invoice?: boolean;
  require_approval_journal_entry?: boolean;
  require_approval_expense?: boolean;
  require_approval_payment?: boolean;
  retained_earnings_account?: string;
  fx_gain_account?: string;
  fx_loss_account?: string;
  default_receivable_account?: string;
  default_payable_account?: string;
  default_income_account?: string;
  default_expense_account?: string;
  allow_negative_stock?: boolean;
  default_valuation_method?: string;
};

type BooksSettingsUpdate = Partial<BooksSettingsResponse>;

type CurrencySettingsResponse = {
  currency_code: string;
  currency_name?: string;
  symbol?: string;
  symbol_position?: SymbolPosition;
  decimal_places: number;
  thousands_separator?: string;
  decimal_separator?: string;
  smallest_unit?: number;
  is_enabled?: boolean;
  is_base_currency?: boolean;
};

// Preset number format patterns
const formatPresets: { label: string; pattern: string; description: string }[] = [
  { label: 'Year-Month Sequential', pattern: '{PREFIX}-{YYYY}{MM}-{####}', description: 'INV-202412-0001' },
  { label: 'Year Sequential', pattern: '{PREFIX}-{YYYY}-{#####}', description: 'INV-2024-00001' },
  { label: 'Fiscal Year Sequential', pattern: '{PREFIX}-{FY}-{#####}', description: 'INV-2024-25-00001' },
  { label: 'Simple Sequential', pattern: '{PREFIX}-{######}', description: 'INV-000001' },
  { label: 'Date Sequential', pattern: '{PREFIX}/{YYYY}/{MM}/{####}', description: 'INV/2024/12/0001' },
  { label: 'Quarter Sequential', pattern: '{PREFIX}-{YYYY}Q{Q}-{####}', description: 'INV-2024Q4-0001' },
];

// Preset document type defaults
const documentTypeDefaults: Record<DocumentType, { prefix: string; pattern: string; reset: ResetFrequency }> = {
  invoice: { prefix: 'INV', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'yearly' },
  bill: { prefix: 'BILL', pattern: '{PREFIX}-{YYYY}-{#####}', reset: 'yearly' },
  payment: { prefix: 'PAY', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'monthly' },
  receipt: { prefix: 'RCP', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'monthly' },
  credit_note: { prefix: 'CN', pattern: '{PREFIX}-{YYYY}-{####}', reset: 'yearly' },
  debit_note: { prefix: 'DN', pattern: '{PREFIX}-{YYYY}-{####}', reset: 'yearly' },
  journal_entry: { prefix: 'JV', pattern: '{PREFIX}-{FY}-{#####}', reset: 'yearly' },
  purchase_order: { prefix: 'PO', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'yearly' },
  sales_order: { prefix: 'SO', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'yearly' },
  quotation: { prefix: 'QTN', pattern: '{PREFIX}-{YYYY}{MM}-{####}', reset: 'monthly' },
  delivery_note: { prefix: 'DN', pattern: '{PREFIX}-{YYYY}-{####}', reset: 'yearly' },
  goods_receipt: { prefix: 'GR', pattern: '{PREFIX}-{YYYY}-{####}', reset: 'yearly' },
};

// Common currency presets
const currencyPresets: Array<{
  code: string;
  name: string;
  symbol: string;
  position: SymbolPosition;
  decimals: number;
  thousands: string;
  decimal: string;
}> = [
  { code: 'NGN', name: 'Nigerian Naira', symbol: '₦', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'USD', name: 'US Dollar', symbol: '$', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'EUR', name: 'Euro', symbol: '€', position: 'before', decimals: 2, thousands: '.', decimal: ',' },
  { code: 'GBP', name: 'British Pound', symbol: '£', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'KES', name: 'Kenyan Shilling', symbol: 'KSh', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'GHS', name: 'Ghanaian Cedi', symbol: 'GH₵', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'ZAR', name: 'South African Rand', symbol: 'R', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'XOF', name: 'West African CFA Franc', symbol: 'CFA', position: 'after', decimals: 0, thousands: ' ', decimal: ',' },
  { code: 'XAF', name: 'Central African CFA Franc', symbol: 'FCFA', position: 'after', decimals: 0, thousands: ' ', decimal: ',' },
  { code: 'INR', name: 'Indian Rupee', symbol: '₹', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'AED', name: 'UAE Dirham', symbol: 'د.إ', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'AUD', name: 'Australian Dollar', symbol: 'A$', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
  { code: 'JPY', name: 'Japanese Yen', symbol: '¥', position: 'before', decimals: 0, thousands: ',', decimal: '.' },
  { code: 'CNY', name: 'Chinese Yuan', symbol: '¥', position: 'before', decimals: 2, thousands: ',', decimal: '.' },
];

const dateFormatLabels: Record<DateFormatType, string> = {
  'DD/MM/YYYY': '31/12/2024 (DD/MM/YYYY)',
  'MM/DD/YYYY': '12/31/2024 (MM/DD/YYYY)',
  'YYYY-MM-DD': '2024-12-31 (YYYY-MM-DD)',
  'DD-MMM-YYYY': '31-Dec-2024 (DD-MMM-YYYY)',
};

const numberFormatLabels: Record<NumberFormatType, string> = {
  '1,234.56': '1,234.56 (US/UK)',
  '1.234,56': '1.234,56 (European)',
  '1 234,56': '1 234,56 (French)',
  '1,23,456.78': '1,23,456.78 (Indian)',
};

export default function BooksSettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('general');

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Books Settings</h1>
        <p className="text-slate-muted text-sm">Configure accounting preferences, document numbering, and currencies.</p>
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-border">
        <nav className="-mb-px flex space-x-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-teal-electric text-teal-electric'
                    : 'border-transparent text-slate-muted hover:text-white hover:border-slate-border'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'general' && <GeneralSettingsTab />}
      {activeTab === 'formats' && <NumberFormatsTab />}
      {activeTab === 'currencies' && <CurrenciesTab />}
    </div>
  );
}

// ============================================================================
// GENERAL SETTINGS TAB
// ============================================================================

function GeneralSettingsTab() {
  const { data: settings, isLoading, error } = useBooksSettings();
  const { updateSettings } = useBooksSettingsMutations();
  const [form, setForm] = useState<Partial<BooksSettingsResponse>>({});
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      setForm(settings);
    }
  }, [settings]);

  const buildUpdatePayload = (data: Partial<BooksSettingsResponse>): BooksSettingsUpdate => {
    const allowed: Array<keyof BooksSettingsUpdate> = [
      'base_currency',
      'currency_precision',
      'quantity_precision',
      'rate_precision',
      'exchange_rate_precision',
      'rounding_method',
      'fiscal_year_start_month',
      'fiscal_year_start_day',
      'auto_create_fiscal_years',
      'auto_create_fiscal_periods',
      'date_format',
      'number_format',
      'negative_format',
      'currency_symbol_position',
      'backdating_days_allowed',
      'future_posting_days_allowed',
      'require_posting_in_open_period',
      'auto_voucher_numbering',
      'allow_duplicate_party_invoice',
      'require_attachment_journal_entry',
      'require_attachment_expense',
      'require_attachment_payment',
      'require_attachment_invoice',
      'require_approval_journal_entry',
      'require_approval_expense',
      'require_approval_payment',
      'retained_earnings_account',
      'fx_gain_account',
      'fx_loss_account',
      'default_receivable_account',
      'default_payable_account',
      'default_income_account',
      'default_expense_account',
      'allow_negative_stock',
      'default_valuation_method',
    ];

    return allowed.reduce((acc, key) => {
      if (data[key] !== undefined) {
        acc[key] = data[key] as any;
      }
      return acc;
    }, {} as BooksSettingsUpdate);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage(null);
    try {
      await updateSettings(buildUpdatePayload(form));
      setSaveMessage('Settings saved successfully');
    } catch (e: any) {
      setSaveMessage(e.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return <div className="text-slate-muted text-sm">Loading settings...</div>;
  }

  if (error) {
    return <div className="text-rose-400 text-sm">Failed to load settings. Please try again.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* General Settings */}
        <Card title="Currency & Precision" icon={Coins}>
          <div className="space-y-4">
            <FormField label="Base Currency">
              <input
                type="text"
                value={form.base_currency || ''}
                onChange={(e) => setForm((p: any) => ({ ...p, base_currency: e.target.value }))}
                className="input-field"
                maxLength={3}
              />
            </FormField>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Currency Precision">
                <select
                  value={form.currency_precision ?? 2}
                  onChange={(e) => setForm((p: any) => ({ ...p, currency_precision: Number(e.target.value) }))}
                  className="input-field"
                >
                  {[0, 2, 4].map((n) => (
                    <option key={n} value={n}>{n} decimals</option>
                  ))}
                </select>
              </FormField>
              <FormField label="Quantity Precision">
                <select
                  value={form.quantity_precision ?? 2}
                  onChange={(e) => setForm((p: any) => ({ ...p, quantity_precision: Number(e.target.value) }))}
                  className="input-field"
                >
                  {[0, 2, 3, 4, 6].map((n) => (
                    <option key={n} value={n}>{n} decimals</option>
                  ))}
                </select>
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Rate Precision">
                <select
                  value={form.rate_precision ?? 4}
                  onChange={(e) => setForm((p: any) => ({ ...p, rate_precision: Number(e.target.value) }))}
                  className="input-field"
                >
                  {[2, 4, 6].map((n) => (
                    <option key={n} value={n}>{n} decimals</option>
                  ))}
                </select>
              </FormField>
              <FormField label="FX Rate Precision">
                <select
                  value={form.exchange_rate_precision ?? 6}
                  onChange={(e) => setForm((p: any) => ({ ...p, exchange_rate_precision: Number(e.target.value) }))}
                  className="input-field"
                >
                  {[4, 6, 8].map((n) => (
                    <option key={n} value={n}>{n} decimals</option>
                  ))}
                </select>
              </FormField>
            </div>
            <FormField label="Rounding Method">
              <select
                value={form.rounding_method || 'round_half_up'}
                onChange={(e) => setForm((p: any) => ({ ...p, rounding_method: e.target.value as RoundingMethod }))}
                className="input-field"
              >
                <option value="round_half_up">Round Half Up (Standard)</option>
                <option value="round_half_down">Round Half Down</option>
                <option value="round_down">Round Down (Truncate)</option>
                <option value="round_up">Round Up</option>
                <option value="bankers">Banker's Rounding</option>
              </select>
            </FormField>
          </div>
        </Card>

        {/* Fiscal Year */}
        <Card title="Fiscal Year" icon={Calendar}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Start Month">
                <select
                  value={form.fiscal_year_start_month ?? 1}
                  onChange={(e) => setForm((p: any) => ({ ...p, fiscal_year_start_month: Number(e.target.value) }))}
                  className="input-field"
                >
                  {[
                    'January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'
                  ].map((m, i) => (
                    <option key={i + 1} value={i + 1}>{m}</option>
                  ))}
                </select>
              </FormField>
              <FormField label="Start Day">
                <input
                  type="number"
                  min={1}
                  max={31}
                  value={form.fiscal_year_start_day ?? 1}
                  onChange={(e) => setForm((p: any) => ({ ...p, fiscal_year_start_day: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </div>
            <div className="space-y-2">
              <CheckboxField
                label="Auto-create fiscal years"
                checked={form.auto_create_fiscal_years ?? true}
                onChange={(v) => setForm((p: any) => ({ ...p, auto_create_fiscal_years: v }))}
              />
              <CheckboxField
                label="Auto-create fiscal periods"
                checked={form.auto_create_fiscal_periods ?? true}
                onChange={(v) => setForm((p: any) => ({ ...p, auto_create_fiscal_periods: v }))}
              />
            </div>
          </div>
        </Card>

        {/* Display Formats */}
        <Card title="Display Formats" icon={FileText}>
          <div className="space-y-4">
            <FormField label="Date Format">
              <select
                value={form.date_format || 'DD/MM/YYYY'}
                onChange={(e) => setForm((p: any) => ({ ...p, date_format: e.target.value as DateFormatType }))}
                className="input-field"
              >
                {Object.entries(dateFormatLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Number Format">
              <select
                value={form.number_format || '1,234.56'}
                onChange={(e) => setForm((p: any) => ({ ...p, number_format: e.target.value as NumberFormatType }))}
                className="input-field"
              >
                {Object.entries(numberFormatLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Negative Format">
              <select
                value={form.negative_format || 'minus'}
                onChange={(e) => setForm((p: any) => ({ ...p, negative_format: e.target.value as NegativeFormat }))}
                className="input-field"
              >
                <option value="minus">-1,234.56 (Minus prefix)</option>
                <option value="parentheses">(1,234.56) (Parentheses)</option>
                <option value="minus_after">1,234.56- (Minus suffix)</option>
              </select>
            </FormField>
            <FormField label="Currency Symbol Position">
              <select
                value={form.currency_symbol_position || 'before'}
                onChange={(e) => setForm((p: any) => ({ ...p, currency_symbol_position: e.target.value as SymbolPosition }))}
                className="input-field"
              >
                <option value="before">Before amount ($1,234.56)</option>
                <option value="after">After amount (1,234.56$)</option>
              </select>
            </FormField>
          </div>
        </Card>

        {/* Posting Controls */}
        <Card title="Posting Controls" icon={Settings}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Backdating Days">
                <input
                  type="number"
                  min={0}
                  value={form.backdating_days_allowed ?? 7}
                  onChange={(e) => setForm((p: any) => ({ ...p, backdating_days_allowed: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <FormField label="Future Posting Days">
                <input
                  type="number"
                  min={0}
                  value={form.future_posting_days_allowed ?? 0}
                  onChange={(e) => setForm((p: any) => ({ ...p, future_posting_days_allowed: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </div>
            <div className="space-y-2">
              <CheckboxField
                label="Require posting in open period"
                checked={form.require_posting_in_open_period ?? true}
                onChange={(v) => setForm((p: any) => ({ ...p, require_posting_in_open_period: v }))}
              />
              <CheckboxField
                label="Auto voucher numbering"
                checked={form.auto_voucher_numbering ?? true}
                onChange={(v) => setForm((p: any) => ({ ...p, auto_voucher_numbering: v }))}
              />
              <CheckboxField
                label="Allow duplicate party invoice numbers"
                checked={form.allow_duplicate_party_invoice ?? false}
                onChange={(v) => setForm((p: any) => ({ ...p, allow_duplicate_party_invoice: v }))}
              />
            </div>
          </div>
        </Card>

        {/* Attachment Requirements */}
        <Card title="Attachment Requirements" icon={FileText}>
          <div className="space-y-2">
            <CheckboxField
              label="Require attachment for journal entries"
              checked={form.require_attachment_journal_entry ?? false}
              onChange={(v) => setForm((p: any) => ({ ...p, require_attachment_journal_entry: v }))}
            />
            <CheckboxField
              label="Require attachment for expenses"
              checked={form.require_attachment_expense ?? true}
              onChange={(v) => setForm((p: any) => ({ ...p, require_attachment_expense: v }))}
            />
            <CheckboxField
              label="Require attachment for payments"
              checked={form.require_attachment_payment ?? false}
              onChange={(v) => setForm((p: any) => ({ ...p, require_attachment_payment: v }))}
            />
            <CheckboxField
              label="Require attachment for invoices"
              checked={form.require_attachment_invoice ?? false}
              onChange={(v) => setForm((p: any) => ({ ...p, require_attachment_invoice: v }))}
            />
          </div>
        </Card>

        {/* Approval Requirements */}
        <Card title="Approval Requirements" icon={Check}>
          <div className="space-y-2">
            <CheckboxField
              label="Require approval for journal entries"
              checked={form.require_approval_journal_entry ?? false}
              onChange={(v) => setForm((p: any) => ({ ...p, require_approval_journal_entry: v }))}
            />
            <CheckboxField
              label="Require approval for expenses"
              checked={form.require_approval_expense ?? true}
              onChange={(v) => setForm((p: any) => ({ ...p, require_approval_expense: v }))}
            />
            <CheckboxField
              label="Require approval for payments"
              checked={form.require_approval_payment ?? false}
              onChange={(v) => setForm((p: any) => ({ ...p, require_approval_payment: v }))}
            />
          </div>
        </Card>
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-end gap-4">
        {saveMessage && (
          <span className={cn('text-sm', saveMessage.includes('success') ? 'text-emerald-400' : 'text-rose-400')}>
            {saveMessage}
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// NUMBER FORMATS TAB
// ============================================================================

function NumberFormatsTab() {
  const { data: formats, isLoading, error } = useNumberFormats();
  const { createFormat, updateFormat, deleteFormat, previewFormat, resetSequence } = useNumberFormatMutations();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<DocumentNumberFormatResponse>>({});
  const [preview, setPreview] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const getInitialForm = (docType: DocumentType) => {
    const defaults = documentTypeDefaults[docType];
    return {
      document_type: docType,
      prefix: defaults.prefix,
      format_pattern: defaults.pattern,
      min_digits: 4,
      starting_number: 1,
      reset_frequency: defaults.reset,
    };
  };

  const [newForm, setNewForm] = useState(getInitialForm('invoice'));

  const handleDocTypeChange = (docType: DocumentType) => {
    const defaults = documentTypeDefaults[docType];
    setNewForm({
      ...newForm,
      document_type: docType,
      prefix: defaults.prefix,
      format_pattern: defaults.pattern,
      reset_frequency: defaults.reset,
    });
    generatePreview(defaults.pattern, defaults.prefix, newForm.min_digits);
  };

  const handlePatternPresetChange = (pattern: string) => {
    setNewForm({ ...newForm, format_pattern: pattern });
    generatePreview(pattern, newForm.prefix, newForm.min_digits);
  };

  const generatePreview = (pattern: string, prefix: string, minDigits: number) => {
    // Generate local preview without API call for instant feedback
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const quarter = Math.ceil((now.getMonth() + 1) / 3);
    const fiscalYear = now.getMonth() >= 3 ? `${year}-${String(year + 1).slice(2)}` : `${year - 1}-${String(year).slice(2)}`;

    let result = pattern
      .replace('{PREFIX}', prefix)
      .replace('{YYYY}', String(year))
      .replace('{YY}', String(year).slice(2))
      .replace('{MM}', month)
      .replace('{DD}', day)
      .replace('{Q}', String(quarter))
      .replace('{FY}', fiscalYear);

    // Handle sequence placeholders
    const seqMatch = result.match(/\{(#+)\}/);
    if (seqMatch) {
      const digits = Math.max(seqMatch[1].length, minDigits);
      result = result.replace(/\{#+\}/, '1'.padStart(digits, '0'));
    }

    setPreview(result);
  };

  const handleCreate = async () => {
    try {
      await createFormat(newForm);
      setShowAdd(false);
      setNewForm(getInitialForm('invoice'));
      setPreview(null);
    } catch (e) {
      console.error('Failed to create format:', e);
    }
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    try {
      await updateFormat(editingId, editForm);
      setEditingId(null);
      setEditForm({});
    } catch (e) {
      console.error('Failed to update format:', e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this format?')) return;
    try {
      await deleteFormat(id);
    } catch (e) {
      console.error('Failed to delete format:', e);
    }
  };

  if (isLoading) {
    return <div className="text-slate-muted text-sm">Loading number formats...</div>;
  }

  if (error) {
    return <div className="text-rose-400 text-sm">Failed to load number formats.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Format Tokens Guide */}
      <Card title="Format Pattern Tokens" icon={Hash}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <TokenBadge token="{PREFIX}" desc="Document prefix" />
          <TokenBadge token="{YYYY}" desc="4-digit year" />
          <TokenBadge token="{YY}" desc="2-digit year" />
          <TokenBadge token="{MM}" desc="Month (01-12)" />
          <TokenBadge token="{DD}" desc="Day (01-31)" />
          <TokenBadge token="{FY}" desc="Fiscal year (2024-25)" />
          <TokenBadge token="{Q}" desc="Quarter (1-4)" />
          <TokenBadge token="{####}" desc="Sequence (# = padding)" />
        </div>
      </Card>

      {/* Add New Format */}
      {!showAdd ? (
        <button
          onClick={() => {
            setShowAdd(true);
            generatePreview(newForm.format_pattern, newForm.prefix, newForm.min_digits);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-slate-border text-slate-muted hover:text-white hover:border-teal-electric transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Number Format
        </button>
      ) : (
        <Card title="New Number Format" icon={Plus}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Document Type - auto-fills prefix, pattern, and reset */}
            <FormField label="Document Type">
              <select
                value={newForm.document_type}
                onChange={(e) => handleDocTypeChange(e.target.value as DocumentType)}
                className="input-field"
              >
                {Object.entries(documentTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </FormField>

            {/* Prefix - auto-filled but editable */}
            <FormField label="Prefix">
              <input
                type="text"
                value={newForm.prefix}
                onChange={(e) => {
                  const prefix = e.target.value.toUpperCase();
                  setNewForm((p) => ({ ...p, prefix }));
                  generatePreview(newForm.format_pattern, prefix, newForm.min_digits);
                }}
                className="input-field"
                maxLength={10}
              />
            </FormField>

            {/* Pattern Preset Dropdown */}
            <FormField label="Format Pattern Preset">
              <select
                value={newForm.format_pattern}
                onChange={(e) => handlePatternPresetChange(e.target.value)}
                className="input-field"
              >
                {formatPresets.map((preset) => (
                  <option key={preset.pattern} value={preset.pattern}>
                    {preset.label} ({preset.description})
                  </option>
                ))}
                <option value="custom">Custom Pattern...</option>
              </select>
            </FormField>

            {/* Custom Pattern Input (shown when custom is selected or pattern doesn't match presets) */}
            {!formatPresets.some((p) => p.pattern === newForm.format_pattern) && (
              <FormField label="Custom Pattern">
                <input
                  type="text"
                  value={newForm.format_pattern}
                  onChange={(e) => {
                    setNewForm((p) => ({ ...p, format_pattern: e.target.value }));
                    generatePreview(e.target.value, newForm.prefix, newForm.min_digits);
                  }}
                  className="input-field"
                  placeholder="e.g. {PREFIX}-{YYYY}-{####}"
                />
              </FormField>
            )}

            {/* Reset Frequency */}
            <FormField label="Reset Frequency">
              <select
                value={newForm.reset_frequency}
                onChange={(e) => setNewForm((p) => ({ ...p, reset_frequency: e.target.value as ResetFrequency }))}
                className="input-field"
              >
                {Object.entries(resetFrequencyLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </FormField>

            {/* Min Digits */}
            <FormField label="Min Sequence Digits">
              <input
                type="number"
                min={1}
                max={10}
                value={newForm.min_digits}
                onChange={(e) => {
                  const digits = Number(e.target.value);
                  setNewForm((p) => ({ ...p, min_digits: digits }));
                  generatePreview(newForm.format_pattern, newForm.prefix, digits);
                }}
                className="input-field"
              />
            </FormField>

            {/* Starting Number */}
            <FormField label="Starting Number">
              <input
                type="number"
                min={1}
                value={newForm.starting_number}
                onChange={(e) => setNewForm((p) => ({ ...p, starting_number: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>

          {/* Live Preview */}
          <div className="mt-4 p-4 bg-slate-elevated rounded-lg border border-slate-border">
            <div className="flex items-center justify-between">
              <span className="text-slate-muted text-sm">Live Preview</span>
              <span className="text-teal-electric font-mono text-lg">{preview || '...'}</span>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <button
              onClick={handleCreate}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              <Check className="w-4 h-4" />
              Create Format
            </button>
            <button
              onClick={() => {
                setShowAdd(false);
                setNewForm(getInitialForm('invoice'));
                setPreview(null);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-white text-sm hover:bg-slate-elevated"
            >
              <X className="w-4 h-4" />
              Cancel
            </button>
          </div>
        </Card>
      )}

      {/* Formats List */}
      <div className="grid grid-cols-1 gap-4">
        {!formats?.length ? (
          <div className="bg-slate-card border border-slate-border rounded-xl p-6 text-center">
            <Hash className="w-8 h-8 text-slate-muted mx-auto mb-3" />
            <p className="text-white font-medium mb-1">No Number Formats Configured</p>
            <p className="text-slate-muted text-sm">Click "Add Number Format" above to configure document numbering.</p>
          </div>
        ) : (
          formats.map((fmt: DocumentNumberFormatResponse) => (
            <div
              key={fmt.id}
              className={cn(
                'bg-slate-card border border-slate-border rounded-xl p-4',
                !fmt.is_active && 'opacity-60'
              )}
            >
              {editingId === fmt.id ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <FormField label="Prefix">
                      <input
                        type="text"
                        value={editForm.prefix ?? fmt.prefix}
                        onChange={(e) => setEditForm((p) => ({ ...p, prefix: e.target.value.toUpperCase() }))}
                        className="input-field"
                      />
                    </FormField>
                    <FormField label="Format Pattern">
                      <input
                        type="text"
                        value={editForm.format_pattern ?? fmt.format_pattern}
                        onChange={(e) => setEditForm((p) => ({ ...p, format_pattern: e.target.value }))}
                        className="input-field"
                      />
                    </FormField>
                    <FormField label="Reset Frequency">
                      <select
                        value={editForm.reset_frequency ?? fmt.reset_frequency}
                        onChange={(e) => setEditForm((p) => ({ ...p, reset_frequency: e.target.value as ResetFrequency }))}
                        className="input-field"
                      >
                        {Object.entries(resetFrequencyLabels).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </FormField>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={handleUpdate} className="px-3 py-1.5 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold">
                      Save
                    </button>
                    <button onClick={() => { setEditingId(null); setEditForm({}); }} className="px-3 py-1.5 rounded-lg border border-slate-border text-white text-sm">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="text-white font-medium">{documentTypeLabels[fmt.document_type as DocumentType]}</span>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        fmt.is_active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-slate-elevated text-slate-muted'
                      )}>
                        {fmt.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-muted">
                      <span className="font-mono bg-slate-elevated px-2 py-0.5 rounded">{fmt.format_pattern}</span>
                      <span>Reset: {resetFrequencyLabels[fmt.reset_frequency as ResetFrequency]}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-muted">
                      <span>Current: <span className="text-teal-electric font-mono">{fmt.current_number}</span></span>
                      <span>Starting: {fmt.starting_number}</span>
                      <span>Min digits: {fmt.min_digits}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { setEditingId(fmt.id); setEditForm({}); }}
                      className="p-2 rounded-lg text-slate-muted hover:text-white hover:bg-slate-elevated"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(fmt.id)}
                      className="p-2 rounded-lg text-slate-muted hover:text-rose-400 hover:bg-slate-elevated"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function TokenBadge({ token, desc }: { token: string; desc: string }) {
  return (
    <div className="bg-slate-elevated rounded-lg px-3 py-2">
      <span className="text-teal-electric font-mono">{token}</span>
      <span className="text-slate-muted ml-2">{desc}</span>
    </div>
  );
}

// ============================================================================
// CURRENCIES TAB
// ============================================================================

function CurrenciesTab() {
  const { data: currencies, isLoading, error } = useCurrencies();
  const { createCurrency, updateCurrency } = useCurrencyMutations();
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<CurrencySettingsResponse>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [newForm, setNewForm] = useState({
    currency_code: '',
    currency_name: '',
    symbol: '',
    symbol_position: 'before' as SymbolPosition,
    decimal_places: 2,
    thousands_separator: ',',
    decimal_separator: '.',
    smallest_unit: 0.01,
    is_enabled: true,
  });

  // Get list of currencies not already added
  const availablePresets = currencyPresets.filter(
    (preset) => !currencies?.some((c: CurrencySettingsResponse) => c.currency_code === preset.code)
  );

  const handlePresetSelect = (code: string) => {
    setSelectedPreset(code);
    const preset = currencyPresets.find((p) => p.code === code);
    if (preset) {
      setNewForm({
        currency_code: preset.code,
        currency_name: preset.name,
        symbol: preset.symbol,
        symbol_position: preset.position,
        decimal_places: preset.decimals,
        thousands_separator: preset.thousands,
        decimal_separator: preset.decimal,
        smallest_unit: preset.decimals === 0 ? 1 : 0.01,
        is_enabled: true,
      });
    }
  };

  const handleCreate = async () => {
    try {
      await createCurrency(newForm);
      setShowAdd(false);
      setSelectedPreset('');
      setNewForm({
        currency_code: '',
        currency_name: '',
        symbol: '',
        symbol_position: 'before',
        decimal_places: 2,
        thousands_separator: ',',
        decimal_separator: '.',
        smallest_unit: 0.01,
        is_enabled: true,
      });
    } catch (e) {
      console.error('Failed to create currency:', e);
    }
  };

  const resetAddForm = () => {
    setShowAdd(false);
    setSelectedPreset('');
    setNewForm({
      currency_code: '',
      currency_name: '',
      symbol: '',
      symbol_position: 'before',
      decimal_places: 2,
      thousands_separator: ',',
      decimal_separator: '.',
      smallest_unit: 0.01,
      is_enabled: true,
    });
  };

  const handleUpdate = async () => {
    if (editingCode === null) return;
    try {
      await updateCurrency(editingCode, editForm);
      setEditingCode(null);
      setEditForm({});
    } catch (e) {
      console.error('Failed to update currency:', e);
    }
  };

  const formatPreview = (curr: typeof newForm | CurrencySettingsResponse) => {
    const amount = 1234.56;
    const formatted = amount.toLocaleString('en-US', {
      minimumFractionDigits: curr.decimal_places,
      maximumFractionDigits: curr.decimal_places,
    }).replace(',', curr.thousands_separator || ',').replace('.', curr.decimal_separator || '.');
    return curr.symbol_position === 'before' ? `${curr.symbol}${formatted}` : `${formatted}${curr.symbol}`;
  };

  if (isLoading) {
    return <div className="text-slate-muted text-sm">Loading currencies...</div>;
  }

  if (error) {
    return <div className="text-rose-400 text-sm">Failed to load currencies.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Add New Currency */}
      {!showAdd ? (
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-slate-border text-slate-muted hover:text-white hover:border-teal-electric transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Currency
        </button>
      ) : (
        <Card title="New Currency" icon={Plus}>
          {/* Currency Preset Selector */}
          <div className="mb-4">
            <FormField label="Select Currency">
              <select
                value={selectedPreset}
                onChange={(e) => handlePresetSelect(e.target.value)}
                className="input-field"
              >
                <option value="">-- Select a currency --</option>
                {availablePresets.map((preset) => (
                  <option key={preset.code} value={preset.code}>
                    {preset.code} - {preset.name} ({preset.symbol})
                  </option>
                ))}
                <option value="custom">Custom Currency...</option>
              </select>
            </FormField>
          </div>

          {/* Show form fields when a preset is selected or custom is chosen */}
          {(selectedPreset || newForm.currency_code) && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <FormField label="Currency Code">
                  <input
                    type="text"
                    value={newForm.currency_code}
                    onChange={(e) => setNewForm((p) => ({ ...p, currency_code: e.target.value.toUpperCase() }))}
                    className="input-field"
                    maxLength={3}
                    placeholder="e.g. USD"
                    disabled={selectedPreset !== 'custom' && selectedPreset !== ''}
                  />
                </FormField>
                <FormField label="Currency Name">
                  <input
                    type="text"
                    value={newForm.currency_name}
                    onChange={(e) => setNewForm((p) => ({ ...p, currency_name: e.target.value }))}
                    className="input-field"
                    placeholder="e.g. US Dollar"
                  />
                </FormField>
                <FormField label="Symbol">
                  <input
                    type="text"
                    value={newForm.symbol}
                    onChange={(e) => setNewForm((p) => ({ ...p, symbol: e.target.value }))}
                    className="input-field"
                    maxLength={5}
                    placeholder="e.g. $"
                  />
                </FormField>
                <FormField label="Symbol Position">
                  <select
                    value={newForm.symbol_position}
                    onChange={(e) => setNewForm((p) => ({ ...p, symbol_position: e.target.value as SymbolPosition }))}
                    className="input-field"
                  >
                    <option value="before">Before ($100)</option>
                    <option value="after">After (100$)</option>
                  </select>
                </FormField>
                <FormField label="Decimal Places">
                  <input
                    type="number"
                    min={0}
                    max={6}
                    value={newForm.decimal_places}
                    onChange={(e) => setNewForm((p) => ({ ...p, decimal_places: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
                <FormField label="Thousands Separator">
                  <select
                    value={newForm.thousands_separator}
                    onChange={(e) => setNewForm((p) => ({ ...p, thousands_separator: e.target.value }))}
                    className="input-field"
                  >
                    <option value=",">Comma (,)</option>
                    <option value=".">Period (.)</option>
                    <option value=" ">Space ( )</option>
                    <option value="'">Apostrophe (')</option>
                  </select>
                </FormField>
                <FormField label="Decimal Separator">
                  <select
                    value={newForm.decimal_separator}
                    onChange={(e) => setNewForm((p) => ({ ...p, decimal_separator: e.target.value }))}
                    className="input-field"
                  >
                    <option value=".">Period (.)</option>
                    <option value=",">Comma (,)</option>
                  </select>
                </FormField>
                <FormField label="Smallest Unit">
                  <select
                    value={newForm.smallest_unit}
                    onChange={(e) => setNewForm((p) => ({ ...p, smallest_unit: Number(e.target.value) }))}
                    className="input-field"
                  >
                    <option value={0.01}>0.01 (Cents)</option>
                    <option value={0.05}>0.05 (5 cents)</option>
                    <option value={0.1}>0.10 (10 cents)</option>
                    <option value={1}>1.00 (Whole units)</option>
                  </select>
                </FormField>
              </div>

              {/* Preview */}
              <div className="mt-4 p-4 bg-slate-elevated rounded-lg border border-slate-border">
                <div className="flex items-center justify-between">
                  <span className="text-slate-muted text-sm">Format Preview</span>
                  <span className="text-teal-electric font-mono text-lg">{formatPreview(newForm)}</span>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!newForm.currency_code || !newForm.currency_name || !newForm.symbol}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                  Add Currency
                </button>
                <button
                  onClick={resetAddForm}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-white text-sm hover:bg-slate-elevated"
                >
                  <X className="w-4 h-4" />
                  Cancel
                </button>
              </div>
            </>
          )}

          {/* Cancel button when no selection */}
          {!selectedPreset && !newForm.currency_code && (
            <div className="mt-4">
              <button
                onClick={resetAddForm}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-white text-sm hover:bg-slate-elevated"
              >
                <X className="w-4 h-4" />
                Cancel
              </button>
            </div>
          )}
        </Card>
      )}

      {/* Currencies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {!currencies?.length ? (
          <div className="col-span-full bg-slate-card border border-slate-border rounded-xl p-6 text-center">
            <Coins className="w-8 h-8 text-slate-muted mx-auto mb-3" />
            <p className="text-white font-medium mb-1">No Currencies Configured</p>
            <p className="text-slate-muted text-sm">Click "Add Currency" above to configure currencies for your books.</p>
          </div>
        ) : (
          currencies.map((curr: CurrencySettingsResponse) => (
            <div
              key={curr.currency_code}
              className={cn(
                'bg-slate-card border border-slate-border rounded-xl p-4 space-y-3',
                !curr.is_enabled && 'opacity-60'
              )}
            >
              {editingCode === curr.currency_code ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <FormField label="Symbol">
                      <input
                        type="text"
                        value={editForm.symbol ?? curr.symbol}
                        onChange={(e) => setEditForm((p: any) => ({ ...p, symbol: e.target.value }))}
                        className="input-field"
                      />
                    </FormField>
                    <FormField label="Decimals">
                      <input
                        type="number"
                        min={0}
                        max={6}
                        value={editForm.decimal_places ?? curr.decimal_places}
                        onChange={(e) => setEditForm((p: any) => ({ ...p, decimal_places: Number(e.target.value) }))}
                        className="input-field"
                      />
                    </FormField>
                  </div>
                  <CheckboxField
                    label="Enabled"
                    checked={(editForm.is_enabled ?? curr.is_enabled) ?? false}
                    onChange={(v) => setEditForm((p: any) => ({ ...p, is_enabled: v }))}
                  />
                  <div className="flex items-center gap-2">
                    <button onClick={handleUpdate} className="px-3 py-1.5 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold">
                      Save
                    </button>
                    <button onClick={() => { setEditingCode(null); setEditForm({}); }} className="px-3 py-1.5 rounded-lg border border-slate-border text-white text-sm">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center text-lg font-bold text-teal-electric">
                        {curr.symbol}
                      </div>
                      <div>
                        <p className="text-white font-medium">{curr.currency_code}</p>
                        <p className="text-slate-muted text-xs">{curr.currency_name}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {curr.is_base_currency && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-teal-electric/10 text-teal-electric border border-teal-electric/30">
                          Base
                        </span>
                      )}
                      {!curr.is_enabled && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-elevated text-slate-muted">
                          Disabled
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-muted">
                    <div>Decimals: {curr.decimal_places}</div>
                    <div>Symbol: {curr.symbol_position === 'before' ? 'Before' : 'After'}</div>
                    <div>Thousands: "{curr.thousands_separator}"</div>
                    <div>Decimal: "{curr.decimal_separator}"</div>
                  </div>
                  <div className="p-2 bg-slate-elevated rounded text-center">
                    <span className="text-slate-muted text-xs">Format: </span>
                    <span className="text-white font-mono">{formatPreview(curr)}</span>
                  </div>
                  <button
                    onClick={() => { setEditingCode(curr.currency_code); setEditForm({}); }}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:bg-slate-elevated text-sm"
                  >
                    <Pencil className="w-4 h-4" />
                    Edit
                  </button>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============================================================================
// SHARED COMPONENTS
// ============================================================================

function Card({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-teal-electric" />
        <h2 className="text-white font-semibold text-sm">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      {children}
    </div>
  );
}

function CheckboxField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
      />
      <span className="text-slate-200 text-sm">{label}</span>
    </label>
  );
}
