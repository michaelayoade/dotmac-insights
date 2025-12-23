'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, BookOpen, FileText, Pencil, Save, X, Trash2, Loader2, CheckCircle2 } from 'lucide-react';
import { useAccountingAccountDetail } from '@/hooks/useApi';
import { accountingApi, AccountingAccountPayload } from '@/lib/api/domains/accounting';
import { cn } from '@/lib/utils';
import { Button, LinkButton } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

const ROOT_TYPES = ['Asset', 'Liability', 'Equity', 'Income', 'Expense'] as const;

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error, mutate } = useAccountingAccountDetail(
    Number.isFinite(id) ? id : null,
    { include_ledger: true, limit: 50 }
  );

  const [isEditing, setIsEditing] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [form, setForm] = useState<Partial<AccountingAccountPayload>>({});
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setForm({
        account_name: (data as any).name || data.account_name,
        account_number: data.account_number,
        root_type: data.root_type,
        account_type: data.account_type,
        parent_account: data.parent_account,
        is_group: data.is_group,
        currency: data.currency,
        disabled: (data as any).disabled,
      });
    }
  }, [data]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement;
    const { name, value, type } = target;
    const nextValue = type === 'checkbox' ? target.checked : value;
    setForm((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleSave = async () => {
    setSaving(true);
    setActionError(null);
    try {
      await accountingApi.updateAccount(id, form);
      setSuccess('Account updated successfully');
      setIsEditing(false);
      mutate();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update account');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setActionError(null);
    try {
      await accountingApi.deleteAccount(id);
      router.push('/books/chart-of-accounts');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete account');
      setDeleteConfirm(false);
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setActionError(null);
    if (data) {
      setForm({
        account_name: (data as any).name || data.account_name,
        account_number: data.account_number,
        root_type: data.root_type,
        account_type: data.account_type,
        parent_account: data.parent_account,
        is_group: data.is_group,
        currency: data.currency,
        disabled: (data as any).disabled,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="h-6 w-28 bg-slate-elevated rounded mb-3 animate-pulse" />
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load account</p>
        <Button
          onClick={() => router.back()}
          variant="secondary"
          icon={ArrowLeft}
          className="mt-3"
        >
          Back
        </Button>
      </div>
    );
  }

  const acct: any = data as any;
  const ledger = (data as any).ledger || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <LinkButton href="/books/chart-of-accounts" variant="secondary" icon={ArrowLeft}>
            Back to chart
          </LinkButton>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Account</p>
            <h1 className="text-xl font-semibold text-foreground">{acct.name || acct.account_name || `Account #${acct.id}`}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <>
              <Button onClick={() => setIsEditing(true)} variant="secondary" icon={Pencil}>
                Edit
              </Button>
              <Button onClick={() => setDeleteConfirm(true)} variant="danger" icon={Trash2}>
                Delete
              </Button>
            </>
          ) : (
            <>
              <Button onClick={handleSave} disabled={saving} loading={saving} module="books" icon={Save}>
                Save
              </Button>
              <Button onClick={cancelEdit} variant="secondary" icon={X}>
                Cancel
              </Button>
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
                Are you sure you want to delete this account?
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={handleDelete} variant="danger" size="sm">
                Yes, Delete
              </Button>
              <Button onClick={() => setDeleteConfirm(false)} variant="secondary" size="sm">
                Cancel
              </Button>
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

      {/* Account Details */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        {isEditing ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Account Name</label>
              <input
                name="account_name"
                value={form.account_name || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Account Number</label>
              <input
                name="account_number"
                value={form.account_number || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Root Type</label>
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
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Parent Account</label>
              <input
                name="parent_account"
                value={form.parent_account || ''}
                onChange={handleChange}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-muted">Currency</label>
              <input
                name="currency"
                value={form.currency || ''}
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
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Account</p>
              <p className="text-foreground font-semibold">{acct.name || acct.account_name || `Account #${acct.id}`}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Type</p>
              <p className={cn('text-foreground font-semibold capitalize')}>{data.account_type || data.root_type || '—'}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Currency</p>
              <p className="text-foreground font-semibold">{data.currency || 'NGN'}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Balance</p>
              <p className="text-foreground font-semibold">{formatAccountingCurrency(acct.balance ?? acct.debit ?? 0, data.currency || 'NGN')}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Debit</p>
              <p className="text-foreground font-semibold">{formatAccountingCurrency(acct.debit ?? 0, data.currency || 'NGN')}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Credit</p>
              <p className="text-foreground font-semibold">{formatAccountingCurrency(acct.credit ?? 0, data.currency || 'NGN')}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Parent</p>
              <p className="text-foreground font-semibold">{data.parent_account || '—'}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Company</p>
              <p className="text-foreground font-semibold">{acct.company || '—'}</p>
            </div>
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">Status</p>
              <p className={cn(
                'font-semibold',
                acct.disabled ? 'text-slate-muted' : 'text-emerald-success'
              )}>
                {acct.disabled ? 'Disabled' : 'Active'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Ledger Entries */}
      {ledger.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Recent Ledger Entries</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Date</th>
                  <th className="text-left px-2 py-2">Voucher</th>
                  <th className="text-left px-2 py-2">Party</th>
                  <th className="text-right px-2 py-2">Debit</th>
                  <th className="text-right px-2 py-2">Credit</th>
                  <th className="text-left px-2 py-2">Cost Center</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry: any, idx: number) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-slate-200">{formatAccountingDate(entry.posting_date)}</td>
                    <td className="px-2 py-2 text-foreground font-mono flex items-center gap-2">
                      {entry.voucher_type && <FileText className="w-3 h-3 text-slate-muted" />}
                      <span>{entry.voucher_type || ''} {entry.voucher_no || ''}</span>
                    </td>
                    <td className="px-2 py-2 text-slate-200">{entry.party || '-'}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatAccountingCurrency(entry.debit, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-right text-slate-200">{formatAccountingCurrency(entry.credit, data.currency || 'NGN')}</td>
                    <td className="px-2 py-2 text-slate-200">{entry.cost_center || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
