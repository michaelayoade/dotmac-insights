'use client';

import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { Landmark, Plus, Pencil, Trash2, X, Check, AlertTriangle, Building2, CreditCard, CheckCircle2, XCircle } from 'lucide-react';
import { accountingApi, AccountingBankAccount, AccountingBankAccountPayload } from '@/lib/api/domains/accounting';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';
import { cn } from '@/lib/utils';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export default function BankAccountsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<AccountingBankAccountPayload>({ account_name: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const bankAccountsRes = useSWR('accounting-bank-accounts', () => accountingApi.getBankAccounts());
  const { isLoading, error, retry } = useSWRStatus(bankAccountsRes);
  const accounts = bankAccountsRes.data?.accounts || [];

  const totalBalance = accounts.reduce((sum: number, acc: AccountingBankAccount) => sum + (acc.balance || 0), 0);
  const activeCount = accounts.filter((acc: AccountingBankAccount) => !(acc as any).disabled).length;

  const handleCreate = async () => {
    if (!formData.account_name.trim()) return;
    setActionError(null);
    try {
      await accountingApi.createBankAccount(formData);
      setIsCreating(false);
      setFormData({ account_name: '' });
      bankAccountsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.account_name.trim()) return;
    setActionError(null);
    try {
      await accountingApi.updateBankAccount(id, formData);
      setEditingId(null);
      setFormData({ account_name: '' });
      bankAccountsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await accountingApi.deleteBankAccount(id);
      setDeleteConfirm(null);
      bankAccountsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (account: AccountingBankAccount) => {
    setEditingId(account.id);
    setFormData({
      account_name: account.account_name || account.name,
      bank: account.bank,
      account_number: account.account_number,
      account_type: account.account_type,
      currency: account.currency,
      is_default: account.is_default,
      is_company_account: account.is_company_account,
      disabled: (account as any).disabled,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ account_name: '' });
    setActionError(null);
  };

  return (
    <DashboardShell isLoading={isLoading} error={error} onRetry={retry}>
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <Building2 className="w-5 h-5 text-slate-muted" />
              <p className="text-slate-muted text-sm">Total Accounts</p>
            </div>
            <p className="text-3xl font-bold text-foreground">{accounts.length}</p>
            <p className="text-slate-muted text-sm mt-1">{activeCount} active</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <CreditCard className="w-5 h-5 text-green-400" />
              <p className="text-green-400 text-sm">Total Balance</p>
            </div>
            <p className="text-3xl font-bold text-green-400">{formatCurrency(totalBalance)}</p>
            <p className="text-green-400/70 text-sm mt-1">Across all accounts</p>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <Landmark className="w-5 h-5 text-blue-400" />
              <p className="text-blue-400 text-sm">Banks</p>
            </div>
            <p className="text-3xl font-bold text-blue-400">
              {new Set(accounts.map((acc: AccountingBankAccount) => acc.bank)).size}
            </p>
            <p className="text-blue-400/70 text-sm mt-1">Different banks</p>
          </div>
        </div>

        {/* Header with Add Button */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Landmark className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Bank Accounts</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ account_name: '' }); }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
            >
              <Plus className="w-4 h-4" />
              Add Bank Account
            </button>
          )}
        </div>

        {actionError && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-coral-alert" />
            <span className="text-sm text-coral-alert">{actionError}</span>
          </div>
        )}

        {/* Create Form */}
        {isCreating && (
          <div className="bg-slate-card border border-slate-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-foreground mb-3">New Bank Account</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Account Name *</label>
                <input
                  type="text"
                  value={formData.account_name}
                  onChange={(e) => setFormData({ ...formData, account_name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Bank</label>
                <input
                  type="text"
                  value={formData.bank || ''}
                  onChange={(e) => setFormData({ ...formData, bank: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="e.g., GTBank"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Account Number</label>
                <input
                  type="text"
                  value={formData.account_number || ''}
                  onChange={(e) => setFormData({ ...formData, account_number: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Account Type</label>
                <select
                  value={formData.account_type || ''}
                  onChange={(e) => setFormData({ ...formData, account_type: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">Select type</option>
                  <option value="Checking">Checking</option>
                  <option value="Savings">Savings</option>
                  <option value="Current">Current</option>
                  <option value="Domiciliary">Domiciliary</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Currency</label>
                <input
                  type="text"
                  value={formData.currency || ''}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="NGN"
                  maxLength={3}
                />
              </div>
              <div className="flex items-end gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_default || false}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                  />
                  <span className="text-sm text-slate-muted">Default</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_company_account || false}
                    onChange={(e) => setFormData({ ...formData, is_company_account: e.target.checked })}
                    className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                  />
                  <span className="text-sm text-slate-muted">Company Account</span>
                </label>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!formData.account_name.trim()}
                className="px-4 py-2 rounded-lg bg-teal-electric text-foreground text-sm font-medium hover:bg-teal-glow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create
              </button>
              <button
                onClick={cancelEdit}
                className="px-4 py-2 rounded-lg bg-slate-elevated text-slate-muted text-sm hover:bg-slate-border"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Bank Account Cards */}
        {accounts.length === 0 ? (
          <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
            <Landmark className="w-12 h-12 text-slate-muted mx-auto mb-4" />
            <p className="text-slate-muted">No bank accounts found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((account: AccountingBankAccount) => {
              const isActive = !(account as any).disabled;
              const isEditingThis = editingId === account.id;
              const isDeleting = deleteConfirm === account.id;

              return (
                <div
                  key={account.id}
                  className={cn(
                    'bg-slate-card border rounded-xl p-6 transition-colors',
                    isActive ? 'border-slate-border hover:border-teal-electric/50' : 'border-slate-border/50 opacity-75'
                  )}
                >
                  {isEditingThis ? (
                    <div className="space-y-3">
                      <input
                        type="text"
                        value={formData.account_name}
                        onChange={(e) => setFormData({ ...formData, account_name: e.target.value })}
                        className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
                        placeholder="Account Name"
                      />
                      <input
                        type="text"
                        value={formData.bank || ''}
                        onChange={(e) => setFormData({ ...formData, bank: e.target.value || null })}
                        className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
                        placeholder="Bank Name"
                      />
                      <input
                        type="text"
                        value={formData.account_number || ''}
                        onChange={(e) => setFormData({ ...formData, account_number: e.target.value || null })}
                        className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
                        placeholder="Account Number"
                      />
                      <div className="flex items-center gap-2">
                        <label className="flex items-center gap-1 text-xs text-slate-muted">
                          <input
                            type="checkbox"
                            checked={formData.disabled || false}
                            onChange={(e) => setFormData({ ...formData, disabled: e.target.checked })}
                            className="w-3 h-3 rounded"
                          />
                          Disabled
                        </label>
                      </div>
                      <div className="flex items-center gap-2 pt-2">
                        <button
                          onClick={() => handleUpdate(account.id)}
                          className="p-1.5 rounded bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ) : isDeleting ? (
                    <div className="text-center py-4">
                      <p className="text-coral-alert text-sm mb-3">Delete this account?</p>
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleDelete(account.id)}
                          className="p-1.5 rounded bg-coral-alert/20 text-coral-alert hover:bg-coral-alert/30"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-teal-electric/20 rounded-lg">
                            <Landmark className="w-6 h-6 text-teal-electric" />
                          </div>
                          <div>
                            <h3 className="text-foreground font-semibold">{account.account_name || account.name}</h3>
                            <p className="text-slate-muted text-sm">{account.bank || '-'}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => startEdit(account)}
                            className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border hover:text-foreground"
                            title="Edit"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(account.id)}
                            className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-coral-alert/20 hover:text-coral-alert"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-muted text-sm">Account Number</span>
                          <span className="font-mono text-foreground">
                            {account.account_number ? `****${String(account.account_number).slice(-4)}` : '-'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-muted text-sm">Account Type</span>
                          <span className="text-foreground capitalize">{account.account_type || 'Checking'}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-muted text-sm">Currency</span>
                          <span className="text-foreground">{account.currency || 'NGN'}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-muted text-sm">Status</span>
                          <span className={cn(
                            'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1',
                            isActive
                              ? 'bg-green-500/20 text-green-400 border-green-500/30'
                              : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
                          )}>
                            {isActive ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                            {isActive ? 'Active' : 'Inactive'}
                          </span>
                        </div>

                        <div className="pt-3 mt-3 border-t border-slate-border">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-muted text-sm">Current Balance</span>
                            <span className={cn(
                              'font-mono font-bold text-lg',
                              (account.balance || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            )}>
                              {formatCurrency(account.balance, account.currency || 'NGN')}
                            </span>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
