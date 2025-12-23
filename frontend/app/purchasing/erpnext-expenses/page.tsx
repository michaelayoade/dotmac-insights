'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import useSWR, { mutate } from 'swr';
import { useERPNextExpenses } from '@/hooks/useApi';
import { purchasingApi, ERPNextExpenseClaimPayload } from '@/lib/api/domains/purchasing';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import { formatCurrency, formatNumber, formatDate } from '@/lib/formatters';
import { Button, FilterCard, FilterSelect } from '@/components/ui';
import {
  AlertTriangle,
  Receipt,
  Calendar,
  DollarSign,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
  User,
  Briefcase,
  Plus,
  X,
  Save,
  Loader2,
  Trash2,
  XCircle,
} from 'lucide-react';

const EXPENSE_STATUSES = ['draft', 'submitted', 'approved', 'rejected', 'paid'] as const;

export default function ERPNextExpensesPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [form, setForm] = useState<ERPNextExpenseClaimPayload>({
    employee_name: '',
    expense_type: '',
    description: '',
    total_claimed_amount: 0,
    total_sanctioned_amount: 0,
    currency: 'NGN',
    status: 'draft',
    posting_date: new Date().toISOString().split('T')[0],
  });

  const { data, isLoading, error: fetchError } = useERPNextExpenses({
    status: status || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const expenses = data?.expenses || [];
  const total = data?.total || 0;
  const totalClaimed = expenses.reduce((sum: number, e: any) => sum + (e.total_claimed_amount || e.amount || 0), 0);
  const totalReimbursed = expenses.reduce((sum: number, e: any) => sum + (e.total_amount_reimbursed || 0), 0);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'number' ? (value ? parseFloat(value) : 0) : value,
    }));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.employee_name?.trim()) {
      setError('Employee name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await purchasingApi.createERPNextExpense(form);
      setShowCreate(false);
      setForm({
        employee_name: '',
        expense_type: '',
        description: '',
        total_claimed_amount: 0,
        total_sanctioned_amount: 0,
        currency: 'NGN',
        status: 'draft',
        posting_date: new Date().toISOString().split('T')[0],
      });
      mutate((key) => Array.isArray(key) && key[0] === 'erpnext-expenses');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create expense claim');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await purchasingApi.deleteERPNextExpense(deleteId);
      setDeleteId(null);
      mutate((key) => Array.isArray(key) && key[0] === 'erpnext-expenses');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete expense claim');
    } finally {
      setDeleting(false);
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

  const columns = [
    {
      key: 'id',
      header: 'ID',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-foreground font-medium">#{item.id}</span>
        </div>
      ),
    },
    {
      key: 'employee',
      header: 'Employee',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[180px]">
            {item.employee_name || item.erpnext_employee || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'expense_type',
      header: 'Type',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[150px]">
            {item.expense_type || item.description || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">{formatDate(item.posting_date)}</span>
        </div>
      ),
    },
    {
      key: 'claimed',
      header: 'Claimed',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground font-medium">
          {formatCurrency(item.total_claimed_amount || item.amount)}
        </span>
      ),
    },
    {
      key: 'sanctioned',
      header: 'Sanctioned',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-amber-400">
          {formatCurrency(item.total_sanctioned_amount)}
        </span>
      ),
    },
    {
      key: 'reimbursed',
      header: 'Reimbursed',
      align: 'right' as const,
      render: (item: any) => {
        const reimbursed = item.total_amount_reimbursed || 0;
        return (
          <span className={cn('font-mono', reimbursed > 0 ? 'text-green-400' : 'text-slate-muted')}>
            {formatCurrency(reimbursed)}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const expenseStatus = item.status || 'draft';
        const config = getStatusConfig(expenseStatus);
        const StatusIcon = config.icon;
        return (
          <span
            className={cn(
              'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
              config.color
            )}
          >
            <StatusIcon className="w-3 h-3" />
            {config.label}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      render: (item: any) => (
        <Button
          onClick={(e) => {
            e.stopPropagation();
            setDeleteId(item.id);
          }}
          className="p-1.5 rounded-lg text-slate-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {(fetchError || error) && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">
            {error || (fetchError instanceof Error ? fetchError.message : 'Failed to load expenses')}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">ERPNext Expense Claims</h1>
          <p className="text-slate-muted text-sm">Manage expense claims synced from ERPNext</p>
        </div>
        <Button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Expense Claim
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Receipt className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Claims</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-amber-400" />
            <p className="text-amber-400 text-sm">Total Claimed</p>
          </div>
          <p className="text-xl font-bold text-amber-400">{formatCurrency(totalClaimed)}</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">Reimbursed</p>
          </div>
          <p className="text-xl font-bold text-green-400">{formatCurrency(totalReimbursed)}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-blue-400" />
            <p className="text-slate-muted text-sm">Pending</p>
          </div>
          <p className="text-xl font-bold text-foreground">
            {formatCurrency(totalClaimed - totalReimbursed)}
          </p>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        actions={status && (
          <Button
            onClick={() => {
              setStatus('');
              setPage(1);
            }}
            className="text-slate-muted text-sm hover:text-foreground transition-colors"
          >
            Clear filters
          </Button>
        )}
        contentClassName="flex flex-wrap gap-4 items-center"
      >
        <FilterSelect
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="paid">Paid</option>
        </FilterSelect>
      </FilterCard>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-card border border-slate-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-slate-border">
              <h2 className="text-lg font-semibold text-foreground">New Expense Claim</h2>
              <Button
                onClick={() => setShowCreate(false)}
                className="p-2 rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
            <form onSubmit={handleCreate} className="p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Employee Name *</label>
                  <input
                    name="employee_name"
                    value={form.employee_name || ''}
                    onChange={handleChange}
                    required
                    className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-muted">Expense Type</label>
                  <input
                    name="expense_type"
                    value={form.expense_type || ''}
                    onChange={handleChange}
                    placeholder="e.g., Travel, Meals, Office Supplies"
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
                  <label className="text-xs text-slate-muted">Currency</label>
                  <input
                    name="currency"
                    value={form.currency || 'NGN'}
                    onChange={handleChange}
                    maxLength={3}
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
              <div className="space-y-1">
                <label className="text-xs text-slate-muted">Description</label>
                <textarea
                  name="description"
                  value={form.description || ''}
                  onChange={handleChange}
                  rows={3}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50 resize-none"
                />
              </div>
              <div className="flex items-center gap-3 pt-2">
                <Button
                  type="submit"
                  disabled={saving}
                  className={cn(
                    'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90',
                    saving && 'opacity-60 cursor-not-allowed'
                  )}
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saving ? 'Creating...' : 'Create Expense Claim'}
                </Button>
                <Button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteId && (
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
              <Button
                onClick={handleDelete}
                disabled={deleting}
                className={cn(
                  'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500 text-foreground font-semibold hover:bg-red-600',
                  deleting && 'opacity-60 cursor-not-allowed'
                )}
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {deleting ? 'Deleting...' : 'Delete'}
              </Button>
              <Button
                onClick={() => setDeleteId(null)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <DataTable
        columns={columns}
        data={expenses}
        keyField="id"
        loading={isLoading}
        emptyMessage="No expense claims found"
        onRowClick={(item) => router.push(`/purchasing/erpnext-expenses/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
