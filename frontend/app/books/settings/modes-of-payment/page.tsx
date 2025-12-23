'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { CreditCard, Plus, Pencil, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { accountingApi, AccountingModeOfPayment, AccountingModeOfPaymentPayload } from '@/lib/api/domains/accounting';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';
import { Button } from '@/components/ui';

const PAYMENT_TYPES = ['Cash', 'Bank', 'General'] as const;

export default function ModesOfPaymentPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<AccountingModeOfPaymentPayload>({ mode_of_payment: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const modesRes = useSWR('accounting-modes-of-payment', () => accountingApi.getModesOfPayment());
  const { isLoading, error, retry } = useSWRStatus(modesRes);
  const modes = modesRes.data?.items || [];

  const handleCreate = async () => {
    if (!formData.mode_of_payment.trim()) return;
    setActionError(null);
    try {
      await accountingApi.createModeOfPayment(formData);
      setIsCreating(false);
      setFormData({ mode_of_payment: '' });
      modesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.mode_of_payment.trim()) return;
    setActionError(null);
    try {
      await accountingApi.updateModeOfPayment(id, formData);
      setEditingId(null);
      setFormData({ mode_of_payment: '' });
      modesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await accountingApi.deleteModeOfPayment(id);
      setDeleteConfirm(null);
      modesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (mode: AccountingModeOfPayment) => {
    setEditingId(mode.id);
    setFormData({
      mode_of_payment: mode.mode_of_payment || mode.name,
      type: mode.type,
      enabled: mode.enabled,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ mode_of_payment: '' });
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Mode of Payment',
      render: (item: AccountingModeOfPayment) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.mode_of_payment}
            onChange={(e) => setFormData({ ...formData, mode_of_payment: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            autoFocus
          />
        ) : (
          <span className="text-foreground font-medium">{item.mode_of_payment || item.name}</span>
        ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (item: AccountingModeOfPayment) =>
        editingId === item.id ? (
          <select
            value={formData.type || ''}
            onChange={(e) => setFormData({ ...formData, type: e.target.value || null })}
            className="bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
          >
            <option value="">Select type</option>
            {PAYMENT_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        ) : (
          <span className={`text-xs px-2 py-1 rounded ${
            item.type === 'Cash'
              ? 'bg-emerald-success/10 text-emerald-success'
              : item.type === 'Bank'
              ? 'bg-blue-500/10 text-blue-400'
              : 'bg-slate-elevated text-slate-muted'
          }`}>
            {item.type || 'General'}
          </span>
        ),
    },
    {
      key: 'enabled',
      header: 'Status',
      render: (item: AccountingModeOfPayment) => (
        <span className={`text-xs px-2 py-1 rounded ${
          item.enabled !== false
            ? 'bg-emerald-success/10 text-emerald-success'
            : 'bg-slate-elevated text-slate-muted'
        }`}>
          {item.enabled !== false ? 'Enabled' : 'Disabled'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: AccountingModeOfPayment) => (
        <div className="flex items-center justify-end gap-2">
          {editingId === item.id ? (
            <>
              <Button onClick={() => handleUpdate(item.id)} variant="success" size="sm" icon={Check} title="Save" />
              <Button onClick={cancelEdit} variant="secondary" size="sm" icon={X} title="Cancel" />
            </>
          ) : deleteConfirm === item.id ? (
            <>
              <Button onClick={() => handleDelete(item.id)} variant="danger" size="sm" icon={Check} title="Confirm Delete" />
              <Button onClick={() => setDeleteConfirm(null)} variant="secondary" size="sm" icon={X} title="Cancel" />
            </>
          ) : (
            <>
              <Button onClick={() => startEdit(item)} variant="ghost" size="sm" icon={Pencil} title="Edit" />
              <Button onClick={() => setDeleteConfirm(item.id)} variant="ghost" size="sm" icon={Trash2} title="Delete">
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <DashboardShell isLoading={isLoading} error={error} onRetry={retry}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Modes of Payment</h1>
          </div>
          {!isCreating && (
            <Button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ mode_of_payment: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Mode of Payment
            </Button>
          )}
        </div>

        {actionError && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-coral-alert" />
            <span className="text-sm text-coral-alert">{actionError}</span>
          </div>
        )}

        {isCreating && (
          <div className="bg-slate-card border border-slate-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-foreground mb-3">New Mode of Payment</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.mode_of_payment}
                  onChange={(e) => setFormData({ ...formData, mode_of_payment: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Type</label>
                <select
                  value={formData.type || ''}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">Select type</option>
                  {PAYMENT_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled !== false}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                  />
                  <span className="text-sm text-slate-muted">Enabled</span>
                </label>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Button onClick={handleCreate} disabled={!formData.mode_of_payment.trim()} module="books">
                Create
              </Button>
              <Button onClick={cancelEdit} variant="secondary">
                Cancel
              </Button>
            </div>
          </div>
        )}

        <DataTable
          columns={columns}
          data={modes}
          keyField="id"
          loading={false}
          emptyMessage="No modes of payment found"
        />
      </div>
    </DashboardShell>
  );
}
