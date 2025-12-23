'use client';

import { useState } from 'react';
import {
  Settings,
  FolderTree,
  FileText,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Receipt,
  CreditCard,
  Wallet2,
  Calendar,
  DollarSign,
  Shield,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useExpenseCategories,
  useExpenseCategoryMutations,
  useExpensePolicies,
  useExpensePolicyMutations,
} from '@/hooks/useExpenses';
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import type {
  ExpenseCategory,
  ExpenseCategoryCreatePayload,
  ExpensePolicy,
  ExpensePolicyCreatePayload,
} from '@/lib/expenses.types';

type TabType = 'categories' | 'policies';

// =============================================================================
// UTILITY COMPONENTS
// =============================================================================

function TabButton({ active, onClick, icon: Icon, label, count }: { active: boolean; onClick: () => void; icon: React.ElementType; label: string; count?: number }) {
  return (
    <Button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all',
        active
          ? 'bg-violet-500/15 border border-violet-500/40 text-foreground'
          : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated'
      )}
    >
      <Icon className={cn('w-4 h-4', active ? 'text-violet-400' : '')} />
      {label}
      {count !== undefined && (
        <span className={cn('px-1.5 py-0.5 rounded text-xs', active ? 'bg-violet-500/20 text-violet-300' : 'bg-slate-elevated text-slate-muted')}>
          {count}
        </span>
      )}
    </Button>
  );
}

function ToggleSwitch({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <Button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      className={cn('p-1 rounded transition-colors', disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer')}
    >
      {checked ? (
        <ToggleRight className="w-6 h-6 text-emerald-400" />
      ) : (
        <ToggleLeft className="w-6 h-6 text-slate-muted" />
      )}
    </Button>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={cn('px-2 py-0.5 rounded text-xs font-medium', active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-elevated text-slate-muted')}>
      {active ? 'Active' : 'Inactive'}
    </span>
  );
}

// =============================================================================
// CATEGORY FORM MODAL
// =============================================================================

function CategoryFormModal({
  category,
  onClose,
  onSave,
}: {
  category?: ExpenseCategory;
  onClose: () => void;
  onSave: (payload: ExpenseCategoryCreatePayload) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ExpenseCategoryCreatePayload>({
    code: category?.code || '',
    name: category?.name || '',
    expense_account: category?.expense_account || '',
    description: category?.description || '',
    requires_receipt: category?.requires_receipt ?? true,
    is_tax_deductible: category?.is_tax_deductible ?? true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      console.error('Failed to save category:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-card border border-slate-border rounded-xl w-full max-w-lg mx-4 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-border">
          <h3 className="text-lg font-semibold text-foreground">{category ? 'Edit Category' : 'New Category'}</h3>
          <Button onClick={onClose} className="text-slate-muted hover:text-foreground">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Code *</label>
              <input
                type="text"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="e.g. TRAVEL"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="e.g. Travel Expenses"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-1">Expense Account *</label>
            <input
              type="text"
              value={form.expense_account}
              onChange={(e) => setForm({ ...form, expense_account: e.target.value })}
              required
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              placeholder="e.g. 6100 - Travel"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-1">Description</label>
            <textarea
              value={form.description || ''}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-none"
              placeholder="Optional description..."
            />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
              <input
                type="checkbox"
                checked={form.requires_receipt}
                onChange={(e) => setForm({ ...form, requires_receipt: e.target.checked })}
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
              />
              Requires Receipt
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_tax_deductible}
                onChange={(e) => setForm({ ...form, is_tax_deductible: e.target.checked })}
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
              />
              Tax Deductible
            </label>
          </div>
          <div className="flex justify-end gap-3 pt-3">
            <Button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-muted hover:text-foreground transition-colors">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-foreground text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {category ? 'Update' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =============================================================================
// POLICY FORM MODAL
// =============================================================================

function PolicyFormModal({
  policy,
  categories,
  onClose,
  onSave,
}: {
  policy?: ExpensePolicy;
  categories: ExpenseCategory[];
  onClose: () => void;
  onSave: (payload: ExpensePolicyCreatePayload) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ExpensePolicyCreatePayload>({
    policy_name: policy?.policy_name || '',
    description: policy?.description || '',
    category_id: policy?.category_id || undefined,
    applies_to_all: policy?.applies_to_all ?? true,
    max_single_expense: policy?.max_single_expense || undefined,
    max_daily_limit: policy?.max_daily_limit || undefined,
    max_monthly_limit: policy?.max_monthly_limit || undefined,
    max_claim_amount: policy?.max_claim_amount || undefined,
    currency: policy?.currency || 'NGN',
    receipt_required: policy?.receipt_required ?? true,
    receipt_threshold: policy?.receipt_threshold || undefined,
    auto_approve_below: policy?.auto_approve_below || undefined,
    requires_pre_approval: policy?.requires_pre_approval ?? false,
    allow_out_of_pocket: policy?.allow_out_of_pocket ?? true,
    allow_cash_advance: policy?.allow_cash_advance ?? false,
    allow_corporate_card: policy?.allow_corporate_card ?? false,
    allow_per_diem: policy?.allow_per_diem ?? false,
    effective_from: policy?.effective_from || undefined,
    effective_to: policy?.effective_to || undefined,
    is_active: policy?.is_active ?? true,
    priority: policy?.priority ?? 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      console.error('Failed to save policy:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8">
      <div className="bg-slate-card border border-slate-border rounded-xl w-full max-w-2xl mx-4 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-border">
          <h3 className="text-lg font-semibold text-foreground">{policy ? 'Edit Policy' : 'New Policy'}</h3>
          <Button onClick={onClose} className="text-slate-muted hover:text-foreground">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Basic Info */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-violet-400 flex items-center gap-2">
              <FileText className="w-4 h-4" /> Basic Information
            </h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Policy Name *</label>
                <input
                  type="text"
                  value={form.policy_name}
                  onChange={(e) => setForm({ ...form, policy_name: e.target.value })}
                  required
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="e.g. Default Travel Policy"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Category (optional)</label>
                <select
                  value={form.category_id || ''}
                  onChange={(e) => setForm({ ...form, category_id: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                >
                  <option value="">All Categories</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Description</label>
              <textarea
                value={form.description || ''}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={2}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-none"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Priority</label>
                <input
                  type="number"
                  value={form.priority || 0}
                  onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Effective From</label>
                <input
                  type="date"
                  value={form.effective_from || ''}
                  onChange={(e) => setForm({ ...form, effective_from: e.target.value || undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Effective To</label>
                <input
                  type="date"
                  value={form.effective_to || ''}
                  onChange={(e) => setForm({ ...form, effective_to: e.target.value || undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
            </div>
          </div>

          {/* Limits */}
          <div className="space-y-4 pt-3 border-t border-slate-border">
            <h4 className="text-sm font-medium text-violet-400 flex items-center gap-2">
              <DollarSign className="w-4 h-4" /> Spending Limits
            </h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Max Single Expense</label>
                <input
                  type="number"
                  value={form.max_single_expense ?? ''}
                  onChange={(e) => setForm({ ...form, max_single_expense: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="No limit"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Max Daily Limit</label>
                <input
                  type="number"
                  value={form.max_daily_limit ?? ''}
                  onChange={(e) => setForm({ ...form, max_daily_limit: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="No limit"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Max Monthly Limit</label>
                <input
                  type="number"
                  value={form.max_monthly_limit ?? ''}
                  onChange={(e) => setForm({ ...form, max_monthly_limit: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="No limit"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Max Claim Amount</label>
                <input
                  type="number"
                  value={form.max_claim_amount ?? ''}
                  onChange={(e) => setForm({ ...form, max_claim_amount: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="No limit"
                />
              </div>
            </div>
          </div>

          {/* Approval & Receipt Rules */}
          <div className="space-y-4 pt-3 border-t border-slate-border">
            <h4 className="text-sm font-medium text-violet-400 flex items-center gap-2">
              <Shield className="w-4 h-4" /> Approval & Receipt Rules
            </h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Auto-Approve Below</label>
                <input
                  type="number"
                  value={form.auto_approve_below ?? ''}
                  onChange={(e) => setForm({ ...form, auto_approve_below: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="Never auto-approve"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Receipt Required Above</label>
                <input
                  type="number"
                  value={form.receipt_threshold ?? ''}
                  onChange={(e) => setForm({ ...form, receipt_threshold: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  placeholder="Always required"
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.receipt_required}
                  onChange={(e) => setForm({ ...form, receipt_required: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
                />
                Receipt Required
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.requires_pre_approval}
                  onChange={(e) => setForm({ ...form, requires_pre_approval: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
                />
                Requires Pre-Approval
              </label>
            </div>
          </div>

          {/* Funding Methods */}
          <div className="space-y-4 pt-3 border-t border-slate-border">
            <h4 className="text-sm font-medium text-violet-400 flex items-center gap-2">
              <CreditCard className="w-4 h-4" /> Allowed Funding Methods
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg cursor-pointer hover:bg-slate-border/30 transition-colors">
                <input
                  type="checkbox"
                  checked={form.allow_out_of_pocket}
                  onChange={(e) => setForm({ ...form, allow_out_of_pocket: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-card text-violet-500 focus:ring-violet-500/50"
                />
                <div className="flex items-center gap-2">
                  <Wallet2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-foreground">Out of Pocket</span>
                </div>
              </label>
              <label className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg cursor-pointer hover:bg-slate-border/30 transition-colors">
                <input
                  type="checkbox"
                  checked={form.allow_cash_advance}
                  onChange={(e) => setForm({ ...form, allow_cash_advance: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-card text-violet-500 focus:ring-violet-500/50"
                />
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-amber-400" />
                  <span className="text-sm text-foreground">Cash Advance</span>
                </div>
              </label>
              <label className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg cursor-pointer hover:bg-slate-border/30 transition-colors">
                <input
                  type="checkbox"
                  checked={form.allow_corporate_card}
                  onChange={(e) => setForm({ ...form, allow_corporate_card: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-card text-violet-500 focus:ring-violet-500/50"
                />
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-violet-400" />
                  <span className="text-sm text-foreground">Corporate Card</span>
                </div>
              </label>
              <label className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg cursor-pointer hover:bg-slate-border/30 transition-colors">
                <input
                  type="checkbox"
                  checked={form.allow_per_diem}
                  onChange={(e) => setForm({ ...form, allow_per_diem: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-border bg-slate-card text-violet-500 focus:ring-violet-500/50"
                />
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-sky-400" />
                  <span className="text-sm text-foreground">Per Diem</span>
                </div>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-border">
            <Button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-muted hover:text-foreground transition-colors">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-foreground text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {policy ? 'Update' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =============================================================================
// CATEGORIES TAB
// =============================================================================

function CategoriesTab() {
  const [showInactive, setShowInactive] = useState(false);
  const [editingCategory, setEditingCategory] = useState<ExpenseCategory | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data: categories, isLoading } = useExpenseCategories({ include_inactive: showInactive });
  const { createCategory, updateCategory, deleteCategory } = useExpenseCategoryMutations();

  const handleSave = async (payload: ExpenseCategoryCreatePayload) => {
    if (editingCategory) {
      await updateCategory(editingCategory.id, payload);
    } else {
      await createCategory(payload);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this category?')) {
      setDeletingId(id);
      try {
        await deleteCategory(id);
      } finally {
        setDeletingId(null);
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
            />
            Show Inactive
          </label>
        </div>
        <Button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-foreground text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Category
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        </div>
      ) : !categories?.length ? (
        <div className="text-center py-12 text-slate-muted">
          <FolderTree className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No categories found</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-border">
          <table className="w-full">
            <thead className="bg-slate-elevated">
              <tr className="text-left text-sm text-slate-muted">
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Expense Account</th>
                <th className="px-4 py-3 text-center">Receipt</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {categories.map((cat) => (
                <tr key={cat.id} className="bg-slate-card hover:bg-slate-elevated/50 transition-colors">
                  <td className="px-4 py-3 text-sm font-mono text-violet-400">{cat.code}</td>
                  <td className="px-4 py-3 text-sm text-foreground">{cat.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-muted">{cat.expense_account}</td>
                  <td className="px-4 py-3 text-center">
                    {cat.requires_receipt ? (
                      <Receipt className="w-4 h-4 text-emerald-400 mx-auto" />
                    ) : (
                      <span className="text-slate-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge active={cat.is_active} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        onClick={() => setEditingCategory(cat)}
                        className="p-1.5 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      {!cat.is_system && (
                        <Button
                          onClick={() => handleDelete(cat.id)}
                          disabled={deletingId === cat.id}
                          className="p-1.5 text-slate-muted hover:text-rose-400 hover:bg-slate-elevated rounded transition-colors disabled:opacity-50"
                          title="Delete"
                        >
                          {deletingId === cat.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(showNewForm || editingCategory) && (
        <CategoryFormModal
          category={editingCategory || undefined}
          onClose={() => { setShowNewForm(false); setEditingCategory(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

// =============================================================================
// POLICIES TAB
// =============================================================================

function PoliciesTab() {
  const [showInactive, setShowInactive] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<ExpensePolicy | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data: policies, isLoading } = useExpensePolicies({ include_inactive: showInactive });
  const { data: categories } = useExpenseCategories();
  const { createPolicy, updatePolicy, deletePolicy } = useExpensePolicyMutations();

  const handleSave = async (payload: ExpensePolicyCreatePayload) => {
    if (editingPolicy) {
      await updatePolicy(editingPolicy.id, payload);
    } else {
      await createPolicy(payload);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this policy?')) {
      setDeletingId(id);
      try {
        await deletePolicy(id);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const getCategoryName = (id?: number | null) => {
    if (!id) return 'All';
    return categories?.find((c) => c.id === id)?.name || `#${id}`;
  };

  const formatLimit = (val?: number | null) => (val ? val.toLocaleString() : '-');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
            />
            Show Inactive
          </label>
        </div>
        <Button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-foreground text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Policy
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        </div>
      ) : !policies?.length ? (
        <div className="text-center py-12 text-slate-muted">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No policies found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {policies.map((policy) => (
            <div
              key={policy.id}
              className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-border/80 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-foreground font-medium">{policy.policy_name}</h3>
                    <StatusBadge active={policy.is_active} />
                    <span className="px-2 py-0.5 rounded bg-slate-elevated text-xs text-slate-muted">
                      Priority: {policy.priority}
                    </span>
                  </div>
                  <p className="text-sm text-slate-muted mt-1">
                    {policy.description || 'No description'}
                  </p>
                  <p className="text-xs text-slate-muted mt-1">
                    Category: <span className="text-violet-400">{getCategoryName(policy.category_id)}</span>
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    onClick={() => setEditingPolicy(policy)}
                    className="p-1.5 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded transition-colors"
                    title="Edit"
                  >
                    <Pencil className="w-4 h-4" />
                  </Button>
                  <Button
                    onClick={() => handleDelete(policy.id)}
                    disabled={deletingId === policy.id}
                    className="p-1.5 text-slate-muted hover:text-rose-400 hover:bg-slate-elevated rounded transition-colors disabled:opacity-50"
                    title="Delete"
                  >
                    {deletingId === policy.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                <div className="bg-slate-elevated rounded-lg p-2">
                  <p className="text-[10px] text-slate-muted uppercase">Single Max</p>
                  <p className="text-sm font-mono text-foreground">{formatLimit(policy.max_single_expense)}</p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-2">
                  <p className="text-[10px] text-slate-muted uppercase">Daily Max</p>
                  <p className="text-sm font-mono text-foreground">{formatLimit(policy.max_daily_limit)}</p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-2">
                  <p className="text-[10px] text-slate-muted uppercase">Monthly Max</p>
                  <p className="text-sm font-mono text-foreground">{formatLimit(policy.max_monthly_limit)}</p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-2">
                  <p className="text-[10px] text-slate-muted uppercase">Auto-Approve</p>
                  <p className="text-sm font-mono text-foreground">{formatLimit(policy.auto_approve_below)}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {policy.allow_out_of_pocket && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded">
                    <Wallet2 className="w-3 h-3" /> Out of Pocket
                  </span>
                )}
                {policy.allow_cash_advance && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-amber-500/10 text-amber-400 text-xs rounded">
                    <DollarSign className="w-3 h-3" /> Cash Advance
                  </span>
                )}
                {policy.allow_corporate_card && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-violet-500/10 text-violet-400 text-xs rounded">
                    <CreditCard className="w-3 h-3" /> Corporate Card
                  </span>
                )}
                {policy.allow_per_diem && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-sky-500/10 text-sky-400 text-xs rounded">
                    <Calendar className="w-3 h-3" /> Per Diem
                  </span>
                )}
                {policy.receipt_required && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-slate-elevated text-slate-muted text-xs rounded">
                    <Receipt className="w-3 h-3" /> Receipt Required
                  </span>
                )}
                {policy.requires_pre_approval && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-rose-500/10 text-rose-400 text-xs rounded">
                    <AlertTriangle className="w-3 h-3" /> Pre-Approval
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {(showNewForm || editingPolicy) && (
        <PolicyFormModal
          policy={editingPolicy || undefined}
          categories={categories || []}
          onClose={() => { setShowNewForm(false); setEditingPolicy(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ExpensesSettingsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:write');
  const [activeTab, setActiveTab] = useState<TabType>('categories');
  const canFetch = !authLoading && !missingScope;
  const { data: categories } = useExpenseCategories({}, { isPaused: () => !canFetch });
  const { data: policies } = useExpensePolicies({}, { isPaused: () => !canFetch });

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:write permission to manage expense settings."
        backHref="/expenses"
        backLabel="Back to Expenses"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
          <Settings className="w-5 h-5 text-violet-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Expense Settings</h1>
          <p className="text-slate-muted text-sm">Manage categories, policies, and limits</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 bg-slate-card border border-slate-border rounded-xl p-2">
        <TabButton
          active={activeTab === 'categories'}
          onClick={() => setActiveTab('categories')}
          icon={FolderTree}
          label="Categories"
          count={categories?.length}
        />
        <TabButton
          active={activeTab === 'policies'}
          onClick={() => setActiveTab('policies')}
          icon={FileText}
          label="Policies"
          count={policies?.length}
        />
      </div>

      {/* Tab Content */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        {activeTab === 'categories' && <CategoriesTab />}
        {activeTab === 'policies' && <PoliciesTab />}
      </div>
    </div>
  );
}