'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useAccountingBankAccounts, useBankTransactionMutations } from '@/hooks/useApi';
import { ArrowLeft, Save, AlertTriangle, CreditCard, Calendar, FileText, User } from 'lucide-react';

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; icon?: React.ReactNode }) {
  const { label, icon, className, ...rest } = props;
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      <div className="relative">
        {icon && <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted">{icon}</div>}
        <input {...rest} className={cn('input-field', icon && 'pl-9', className)} />
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input-field">
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function NewBankTransactionPage() {
  const router = useRouter();
  const { data: bankAccountsData } = useAccountingBankAccounts();
  const { createTransaction } = useBankTransactionMutations();

  const [form, setForm] = useState({
    account: '',
    transaction_date: new Date().toISOString().slice(0, 10),
    amount: '',
    transaction_type: 'deposit' as 'deposit' | 'withdrawal',
    description: '',
    reference_number: '',
    party_type: '',
    party: '',
  });

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const bankAccounts = (bankAccountsData as any)?.accounts || [];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const validate = () => {
    if (!form.account) return 'Bank account is required';
    if (!form.transaction_date) return 'Transaction date is required';
    if (!form.amount || parseFloat(form.amount) <= 0) return 'Amount must be greater than 0';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    try {
      await createTransaction({
        account: form.account,
        transaction_date: form.transaction_date,
        amount: parseFloat(form.amount),
        transaction_type: form.transaction_type,
        description: form.description || undefined,
        reference_number: form.reference_number || undefined,
        party_type: (form.party_type as 'Customer' | 'Supplier') || undefined,
        party: form.party || undefined,
      });

      router.push('/books/bank-transactions');
    } catch (err: any) {
      setError(err?.message || 'Failed to create transaction');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/books/bank-transactions"
          className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">New Bank Transaction</h1>
          <p className="text-slate-muted text-sm">Record a manual bank transaction</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Main Details */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h2 className="text-white font-medium flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-teal-electric" />
            Transaction Details
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Bank Account *"
              value={form.account}
              onChange={(value) => setForm((prev) => ({ ...prev, account: value }))}
              options={bankAccounts.map((acc: any) => ({
                value: acc.name || acc.account_name,
                label: `${acc.account_name || acc.name} - ${acc.bank || 'Unknown Bank'}`,
              }))}
              placeholder="Select bank account..."
            />

            <Input
              label="Transaction Date *"
              type="date"
              name="transaction_date"
              value={form.transaction_date}
              onChange={handleChange}
              icon={<Calendar className="w-4 h-4" />}
            />

            <div className="space-y-1.5">
              <label className="block text-sm text-slate-muted">Transaction Type *</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="transaction_type"
                    value="deposit"
                    checked={form.transaction_type === 'deposit'}
                    onChange={handleChange}
                    className="w-4 h-4 text-teal-electric"
                  />
                  <span className="text-white">Deposit (Money In)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="transaction_type"
                    value="withdrawal"
                    checked={form.transaction_type === 'withdrawal'}
                    onChange={handleChange}
                    className="w-4 h-4 text-teal-electric"
                  />
                  <span className="text-white">Withdrawal (Money Out)</span>
                </label>
              </div>
            </div>

            <Input
              label="Amount *"
              type="number"
              name="amount"
              value={form.amount}
              onChange={handleChange}
              placeholder="0.00"
              min="0.01"
              step="0.01"
            />
          </div>
        </div>

        {/* Additional Details */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h2 className="text-white font-medium flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            Additional Details
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Reference Number"
              name="reference_number"
              value={form.reference_number}
              onChange={handleChange}
              placeholder="e.g., CHK001, TRF-2024-001"
            />

            <div className="md:col-span-2">
              <label className="block text-sm text-slate-muted mb-1.5">Description</label>
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                rows={2}
                placeholder="Transaction description or memo..."
                className="input-field resize-none"
              />
            </div>
          </div>
        </div>

        {/* Party Details */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <h2 className="text-white font-medium flex items-center gap-2">
            <User className="w-4 h-4 text-teal-electric" />
            Party Details (Optional)
          </h2>
          <p className="text-slate-muted text-sm">
            Link this transaction to a customer or supplier for easier reconciliation.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Party Type"
              value={form.party_type}
              onChange={(value) => setForm((prev) => ({ ...prev, party_type: value }))}
              options={[
                { value: 'Customer', label: 'Customer' },
                { value: 'Supplier', label: 'Supplier' },
              ]}
              placeholder="Select party type..."
            />

            <Input
              label="Party Name/ID"
              name="party"
              value={form.party}
              onChange={handleChange}
              placeholder="Customer or supplier name"
              disabled={!form.party_type}
            />
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-xl p-4 flex items-center gap-2 text-coral-alert">
            <AlertTriangle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link
            href="/books/bank-transactions"
            className="px-4 py-2 text-slate-muted hover:text-white border border-slate-border rounded-lg hover:border-slate-muted transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60 transition-colors"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Creating...' : 'Create Transaction'}
          </button>
        </div>
      </form>
    </div>
  );
}
