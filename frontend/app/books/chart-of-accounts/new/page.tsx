'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Save, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { accountingApi, AccountingAccountPayload } from '@/lib/api/domains/accounting';
import { Button, LinkButton } from '@/components/ui';

const ROOT_TYPES = ['Asset', 'Liability', 'Equity', 'Income', 'Expense'] as const;

export default function NewAccountPage() {
  const router = useRouter();
  const [form, setForm] = useState<AccountingAccountPayload>({
    account_name: '',
    account_number: '',
    root_type: 'Asset',
    account_type: '',
    parent_account: '',
    is_group: false,
    currency: 'NGN',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement;
    const { name, value, type } = target;
    const nextValue = type === 'checkbox' ? target.checked : value;
    setForm((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.account_name.trim()) {
      setError('Account name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await accountingApi.createAccount(form);
      setSuccess(true);
      setTimeout(() => router.push('/books/chart-of-accounts'), 800);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create account');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <LinkButton href="/books/chart-of-accounts" variant="secondary" icon={ArrowLeft}>
          Back
        </LinkButton>
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Chart of Accounts</p>
          <h1 className="text-xl font-semibold text-foreground">New Account</h1>
        </div>
      </div>

      {error && (
        <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-coral-alert" />
          <span className="text-sm text-coral-alert">{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-emerald-success/10 border border-emerald-success/30 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-success" />
          <span className="text-sm text-emerald-success">Account created successfully</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h2 className="text-sm font-medium text-slate-muted mb-4">Account Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Account Name *</label>
              <input
                name="account_name"
                value={form.account_name}
                onChange={handleChange}
                required
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Account Number</label>
              <input
                name="account_number"
                value={form.account_number || ''}
                onChange={handleChange}
                placeholder="e.g., 1000"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Root Type *</label>
              <select
                name="root_type"
                value={form.root_type || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                {ROOT_TYPES.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Account Type</label>
              <input
                name="account_type"
                value={form.account_type || ''}
                onChange={handleChange}
                placeholder="e.g., Bank, Cash, Receivable"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Parent Account</label>
              <input
                name="parent_account"
                value={form.parent_account || ''}
                onChange={handleChange}
                placeholder="Parent account name"
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Currency</label>
              <input
                name="currency"
                value={form.currency || ''}
                onChange={handleChange}
                placeholder="NGN"
                maxLength={3}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input
                type="checkbox"
                name="is_group"
                checked={form.is_group || false}
                onChange={handleChange}
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
              />
              <label className="text-sm text-slate-muted">Is Group Account</label>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving} loading={saving} module="books" icon={Save}>
            {saving ? 'Creating...' : 'Create Account'}
          </Button>
          <LinkButton href="/books/chart-of-accounts" variant="secondary">
            Cancel
          </LinkButton>
        </div>
      </form>
    </div>
  );
}
