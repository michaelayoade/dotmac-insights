'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { mutate } from 'swr';
import { useERPNextExpenseDetail } from '@/hooks/useApi';
import { purchasingApi, ERPNextExpenseClaimPayload } from '@/lib/api/domains/purchasing';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { cn } from '@/lib/utils';
import {
  ArrowLeft,
  Edit3,
  Trash2,
  Save,
  X,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Receipt,
  User,
  Calendar,
  DollarSign,
  Briefcase,
  Building2,
  Clock,
  AlertCircle,
} from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '\u20A60';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

const EXPENSE_STATUSES = ['draft', 'submitted', 'approved', 'rejected', 'paid'] as const;

export default function ERPNextExpenseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const { data: expense, isLoading, error } = useERPNextExpenseDetail(id);

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState<ERPNextExpenseClaimPayload>({});

  const handleStartEdit = () => {
    if (!expense) return;
    setForm({
      employee_name: expense.employee_name,
      erpnext_employee: expense.erpnext_employee,
      expense_type: expense.expense_type,
      description: expense.description,
      remark: expense.remark,
      total_claimed_amount: expense.total_claimed_amount,
      total_sanctioned_amount: expense.total_sanctioned_amount,
      total_amount_reimbursed: expense.total_amount_reimbursed,
      total_advance_amount: expense.total_advance_amount,
      amount: expense.amount,
      currency: expense.currency || 'NGN',
      cost_center: expense.cost_center,
      company: expense.company,
      status: expense.status || 'draft',
      is_paid: expense.is_paid,
      posting_date: expense.posting_date,
    });
    setEditing(true);
    setSaveError(null);
    setSuccess(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setForm((prev) => ({ ...prev, [name]: checked }));
    } else if (type === 'number') {
      setForm((prev) => ({ ...prev, [name]: value ? parseFloat(value) : 0 }));
    } else {
      setForm((prev) => ({ ...prev, [name]: value || null }));
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await purchasingApi.updateERPNextExpense(id, form);
      setSuccess(true);
      setEditing(false);
      mutate(['erpnext-expense-detail', id]);
      mutate((key) => Array.isArray(key) && key[0] === 'erpnext-expenses');
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update expense claim');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await purchasingApi.deleteERPNextExpense(id);
      mutate((key) => Array.isArray(key) && key[0] === 'erpnext-expenses');
      router.push('/purchasing/erpnext-expenses');
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to delete expense claim');
      setDeleting(false);
      setDeleteConfirm(false);
    }
  };

  const getStatusConfig = (expenseStatus: string) => {
    const statusLower = expenseStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      approved: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Approved',
      },
      pending: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Pending',
      },
      rejected: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: AlertCircle,
        label: 'Rejected',
      },
      draft: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: Receipt,
        label: 'Draft',
      },
      submitted: {
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: Receipt,
        label: 'Submitted',
      },
      paid: {
        color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        icon: CheckCircle2,
        label: 'Paid',
      },
    };
    return configs[statusLower] || configs.draft;
  };

  if (isLoading) {
    return (
      <DashboardShell isLoading loadingMessage="Loading...">
        <div />
      </DashboardShell>
    );
  }

  if (error || !expense) {
    return (
      <DashboardShell
        isLoading={false}
        error={error instanceof Error ? error : { message: 'Expense claim not found' }}
      >
        <div />
      </DashboardShell>
    );
  }

  const statusConfig = getStatusConfig(expense.status || 'draft');
  const StatusIcon = statusConfig.icon;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/purchasing/erpnext-expenses"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">ERPNext Expense Claim</p>
            <h1 className="text-xl font-semibold text-foreground">#{expense.id}</h1>
          </div>
        </div>
        {!editing && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleStartEdit}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-teal-electric/50"
            >
              <Edit3 className="w-4 h-4" />
              Edit
            </button>
            <button
              onClick={() => setDeleteConfirm(true)}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      {saveError && (
        <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-coral-alert" />
          <span className="text-sm text-coral-alert">{saveError}</span>
        </div>
      )}
      {success && (
        <div className="bg-emerald-success/10 border border-emerald-success/30 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-success" />
          <span className="text-sm text-emerald-success">Expense claim updated successfully</span>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-card border border-slate-border rounded-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">Delete Expense Claim</h3>
                <p className="text-sm text-slate-muted">This action cannot be undone.</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className={cn(
                  'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500 text-foreground font-semibold hover:bg-red-600',
                  deleting && 'opacity-60 cursor-not-allowed'
                )}
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
              <button
                onClick={() => setDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {editing ? (
        /* Edit Form */
        <div className="space-y-6">
          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-sm font-medium text-slate-muted mb-4">Employee Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Employee Name</label>
                <input
                  name="employee_name"
                  value={form.employee_name || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">ERPNext Employee ID</label>
                <input
                  name="erpnext_employee"
                  value={form.erpnext_employee || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-sm font-medium text-slate-muted mb-4">Expense Details</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Expense Type</label>
                <input
                  name="expense_type"
                  value={form.expense_type || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Posting Date</label>
                <input
                  type="date"
                  name="posting_date"
                  value={form.posting_date || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Status</label>
                <select
                  name="status"
                  value={form.status || 'draft'}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  {EXPENSE_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="is_paid"
                    checked={form.is_paid || false}
                    onChange={handleChange}
                    className="rounded border-slate-border"
                  />
                  Is Paid
                </label>
              </div>
            </div>
            <div className="mt-4 space-y-1">
              <label className="text-xs text-slate-muted">Description</label>
              <textarea
                name="description"
                value={form.description || ''}
                onChange={handleChange}
                rows={2}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50 resize-none"
              />
            </div>
            <div className="mt-4 space-y-1">
              <label className="text-xs text-slate-muted">Remark</label>
              <textarea
                name="remark"
                value={form.remark || ''}
                onChange={handleChange}
                rows={2}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50 resize-none"
              />
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-sm font-medium text-slate-muted mb-4">Amounts</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Claimed Amount</label>
                <input
                  type="number"
                  name="total_claimed_amount"
                  value={form.total_claimed_amount || 0}
                  onChange={handleChange}
                  min={0}
                  step={0.01}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Sanctioned Amount</label>
                <input
                  type="number"
                  name="total_sanctioned_amount"
                  value={form.total_sanctioned_amount || 0}
                  onChange={handleChange}
                  min={0}
                  step={0.01}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Reimbursed Amount</label>
                <input
                  type="number"
                  name="total_amount_reimbursed"
                  value={form.total_amount_reimbursed || 0}
                  onChange={handleChange}
                  min={0}
                  step={0.01}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Advance Amount</label>
                <input
                  type="number"
                  name="total_advance_amount"
                  value={form.total_advance_amount || 0}
                  onChange={handleChange}
                  min={0}
                  step={0.01}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Currency</label>
                <input
                  name="currency"
                  value={form.currency || 'NGN'}
                  onChange={handleChange}
                  maxLength={3}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-6">
            <h2 className="text-sm font-medium text-slate-muted mb-4">Organization</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Company</label>
                <input
                  name="company"
                  value={form.company || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Cost Center</label>
                <input
                  name="cost_center"
                  value={form.cost_center || ''}
                  onChange={handleChange}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90',
                saving && 'opacity-60 cursor-not-allowed'
              )}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        /* View Mode */
        <div className="space-y-6">
          {/* Status Banner */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  'px-3 py-1.5 rounded-full text-sm font-medium border flex items-center gap-1.5',
                  statusConfig.color
                )}
              >
                <StatusIcon className="w-4 h-4" />
                {statusConfig.label}
              </span>
              {expense.is_paid && (
                <span className="px-3 py-1.5 rounded-full text-sm font-medium border bg-emerald-500/20 text-emerald-400 border-emerald-500/30 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Paid
                </span>
              )}
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-muted">Posting Date</p>
              <p className="text-sm text-foreground">{formatDate(expense.posting_date)}</p>
            </div>
          </div>

          {/* Amount Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign className="w-4 h-4 text-amber-400" />
                <p className="text-amber-400 text-sm">Claimed</p>
              </div>
              <p className="text-xl font-bold text-amber-400">
                {formatCurrency(expense.total_claimed_amount, expense.currency || 'NGN')}
              </p>
            </div>
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-4 h-4 text-blue-400" />
                <p className="text-blue-400 text-sm">Sanctioned</p>
              </div>
              <p className="text-xl font-bold text-blue-400">
                {formatCurrency(expense.total_sanctioned_amount, expense.currency || 'NGN')}
              </p>
            </div>
            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign className="w-4 h-4 text-green-400" />
                <p className="text-green-400 text-sm">Reimbursed</p>
              </div>
              <p className="text-xl font-bold text-green-400">
                {formatCurrency(expense.total_amount_reimbursed, expense.currency || 'NGN')}
              </p>
            </div>
            <div className="bg-slate-card border border-slate-border rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-4 h-4 text-slate-muted" />
                <p className="text-slate-muted text-sm">Advance</p>
              </div>
              <p className="text-xl font-bold text-foreground">
                {formatCurrency(expense.total_advance_amount, expense.currency || 'NGN')}
              </p>
            </div>
          </div>

          {/* Employee & Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h2 className="text-sm font-medium text-slate-muted mb-4">Employee Information</h2>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <User className="w-5 h-5 text-teal-electric" />
                  <div>
                    <p className="text-xs text-slate-muted">Employee Name</p>
                    <p className="text-foreground">{expense.employee_name || '-'}</p>
                  </div>
                </div>
                {expense.erpnext_employee && (
                  <div className="flex items-center gap-3">
                    <Receipt className="w-5 h-5 text-slate-muted" />
                    <div>
                      <p className="text-xs text-slate-muted">ERPNext Employee</p>
                      <p className="text-foreground font-mono">{expense.erpnext_employee}</p>
                    </div>
                  </div>
                )}
                {expense.erpnext_id && (
                  <div className="flex items-center gap-3">
                    <Receipt className="w-5 h-5 text-slate-muted" />
                    <div>
                      <p className="text-xs text-slate-muted">ERPNext ID</p>
                      <p className="text-foreground font-mono">{expense.erpnext_id}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h2 className="text-sm font-medium text-slate-muted mb-4">Organization</h2>
              <div className="space-y-3">
                {expense.company && (
                  <div className="flex items-center gap-3">
                    <Building2 className="w-5 h-5 text-teal-electric" />
                    <div>
                      <p className="text-xs text-slate-muted">Company</p>
                      <p className="text-foreground">{expense.company}</p>
                    </div>
                  </div>
                )}
                {expense.cost_center && (
                  <div className="flex items-center gap-3">
                    <Briefcase className="w-5 h-5 text-slate-muted" />
                    <div>
                      <p className="text-xs text-slate-muted">Cost Center</p>
                      <p className="text-foreground">{expense.cost_center}</p>
                    </div>
                  </div>
                )}
                {expense.expense_type && (
                  <div className="flex items-center gap-3">
                    <Receipt className="w-5 h-5 text-slate-muted" />
                    <div>
                      <p className="text-xs text-slate-muted">Expense Type</p>
                      <p className="text-foreground">{expense.expense_type}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Description */}
          {(expense.description || expense.remark) && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-6">
              <h2 className="text-sm font-medium text-slate-muted mb-4">Details</h2>
              {expense.description && (
                <div className="mb-4">
                  <p className="text-xs text-slate-muted mb-1">Description</p>
                  <p className="text-foreground">{expense.description}</p>
                </div>
              )}
              {expense.remark && (
                <div>
                  <p className="text-xs text-slate-muted mb-1">Remark</p>
                  <p className="text-foreground">{expense.remark}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
