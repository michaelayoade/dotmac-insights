'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CreditCard, Save } from 'lucide-react';
import { useCorporateCardMutations } from '@/hooks/useExpenses';
import type { CorporateCardCreatePayload } from '@/lib/expenses.types';

export default function NewCardPage() {
  const router = useRouter();
  const { createCard } = useCorporateCardMutations();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<CorporateCardCreatePayload>({
    card_number_last4: '',
    card_name: '',
    card_type: 'credit',
    bank_name: '',
    card_provider: '',
    employee_id: 0,
    credit_limit: 0,
    single_transaction_limit: null,
    daily_limit: null,
    monthly_limit: null,
    currency: 'NGN',
    issue_date: new Date().toISOString().split('T')[0],
    expiry_date: null,
    liability_account: '',
    company: null,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'number' ? (value === '' ? null : Number(value)) : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (formData.card_number_last4.length !== 4) {
        throw new Error('Card last 4 digits must be exactly 4 characters');
      }
      if (!formData.card_name.trim()) {
        throw new Error('Card name is required');
      }
      if (!formData.employee_id || formData.employee_id <= 0) {
        throw new Error('Valid employee ID is required');
      }

      const card = await createCard(formData);
      router.push(`/expenses/cards/${card.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create card');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/expenses/cards" className="inline-flex items-center gap-2 text-slate-muted hover:text-white transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to cards
      </Link>

      {/* Header */}
      <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
        <div className="flex items-center gap-4">
          <div className="p-4 rounded-2xl bg-violet-500/15 text-violet-300">
            <CreditCard className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Add Corporate Card</h1>
            <p className="text-slate-muted mt-1">Assign a new corporate card to an employee</p>
          </div>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
            {error}
          </div>
        )}

        {/* Card Information */}
        <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Card Information</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Card Name *</label>
              <input
                type="text"
                name="card_name"
                value={formData.card_name}
                onChange={handleChange}
                placeholder="e.g., John's Expense Card"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Last 4 Digits *</label>
              <input
                type="text"
                name="card_number_last4"
                value={formData.card_number_last4}
                onChange={handleChange}
                placeholder="1234"
                maxLength={4}
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Card Type</label>
              <select
                name="card_type"
                value={formData.card_type || ''}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white focus:outline-none focus:border-violet-500"
              >
                <option value="credit">Credit</option>
                <option value="debit">Debit</option>
                <option value="prepaid">Prepaid</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Card Provider</label>
              <select
                name="card_provider"
                value={formData.card_provider || ''}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white focus:outline-none focus:border-violet-500"
              >
                <option value="">Select provider</option>
                <option value="visa">Visa</option>
                <option value="mastercard">Mastercard</option>
                <option value="verve">Verve</option>
                <option value="amex">American Express</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Bank Name</label>
              <input
                type="text"
                name="bank_name"
                value={formData.bank_name || ''}
                onChange={handleChange}
                placeholder="e.g., First Bank"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Employee ID *</label>
              <input
                type="number"
                name="employee_id"
                value={formData.employee_id || ''}
                onChange={handleChange}
                placeholder="Enter employee ID"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
                required
              />
            </div>
          </div>
        </div>

        {/* Limits */}
        <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Limits</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Credit Limit *</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  name="credit_limit"
                  value={formData.credit_limit || ''}
                  onChange={handleChange}
                  placeholder="0"
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
                  required
                />
                <select
                  name="currency"
                  value={formData.currency}
                  onChange={handleChange}
                  className="w-24 px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white focus:outline-none focus:border-violet-500"
                >
                  <option value="NGN">NGN</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Single Transaction Limit</label>
              <input
                type="number"
                name="single_transaction_limit"
                value={formData.single_transaction_limit ?? ''}
                onChange={handleChange}
                placeholder="No limit"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Daily Limit</label>
              <input
                type="number"
                name="daily_limit"
                value={formData.daily_limit ?? ''}
                onChange={handleChange}
                placeholder="No limit"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Monthly Limit</label>
              <input
                type="number"
                name="monthly_limit"
                value={formData.monthly_limit ?? ''}
                onChange={handleChange}
                placeholder="No limit"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
              />
            </div>
          </div>
        </div>

        {/* Dates & Accounting */}
        <div className="rounded-2xl border border-slate-border bg-slate-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Dates & Accounting</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Issue Date *</label>
              <input
                type="date"
                name="issue_date"
                value={formData.issue_date}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white focus:outline-none focus:border-violet-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Expiry Date</label>
              <input
                type="date"
                name="expiry_date"
                value={formData.expiry_date || ''}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white focus:outline-none focus:border-violet-500"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm text-slate-muted mb-1">Liability Account</label>
              <input
                type="text"
                name="liability_account"
                value={formData.liability_account || ''}
                onChange={handleChange}
                placeholder="e.g., Corporate Card Payable"
                className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white placeholder-slate-muted focus:outline-none focus:border-violet-500"
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link
            href="/expenses/cards"
            className="px-4 py-2 rounded-xl border border-slate-border text-slate-muted hover:text-white hover:border-slate-400 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-6 py-2 rounded-xl bg-violet-500 text-white font-semibold hover:bg-violet-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Save className="w-4 h-4" />
            {isSubmitting ? 'Creating...' : 'Create Card'}
          </button>
        </div>
      </form>
    </div>
  );
}
