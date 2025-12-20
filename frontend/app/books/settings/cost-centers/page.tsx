'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Target, Plus, Pencil, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { accountingApi, AccountingCostCenter, AccountingCostCenterPayload } from '@/lib/api/domains/accounting';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';

export default function CostCentersPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<AccountingCostCenterPayload>({ cost_center_name: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const costCentersRes = useSWR('accounting-cost-centers', () => accountingApi.getCostCenters());
  const { isLoading, error, retry } = useSWRStatus(costCentersRes);
  const costCenters = costCentersRes.data?.cost_centers || [];

  const handleCreate = async () => {
    if (!formData.cost_center_name.trim()) return;
    setActionError(null);
    try {
      await accountingApi.createCostCenter(formData);
      setIsCreating(false);
      setFormData({ cost_center_name: '' });
      costCentersRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.cost_center_name.trim()) return;
    setActionError(null);
    try {
      await accountingApi.updateCostCenter(id, formData);
      setEditingId(null);
      setFormData({ cost_center_name: '' });
      costCentersRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await accountingApi.deleteCostCenter(id);
      setDeleteConfirm(null);
      costCentersRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (cc: AccountingCostCenter) => {
    setEditingId(cc.id);
    setFormData({
      cost_center_name: cc.cost_center_name || cc.name,
      parent_cost_center: cc.parent_cost_center,
      is_group: cc.is_group,
      company: cc.company,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ cost_center_name: '' });
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Cost Center',
      render: (item: AccountingCostCenter) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.cost_center_name}
            onChange={(e) => setFormData({ ...formData, cost_center_name: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
            autoFocus
          />
        ) : (
          <span className="text-white font-medium">{item.cost_center_name || item.name}</span>
        ),
    },
    {
      key: 'parent',
      header: 'Parent Cost Center',
      render: (item: AccountingCostCenter) =>
        editingId === item.id ? (
          <select
            value={formData.parent_cost_center || ''}
            onChange={(e) => setFormData({ ...formData, parent_cost_center: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
          >
            <option value="">None</option>
            {costCenters.filter((cc) => cc.id !== item.id && cc.is_group).map((cc) => (
              <option key={cc.id} value={cc.cost_center_name || cc.name}>{cc.cost_center_name || cc.name}</option>
            ))}
          </select>
        ) : (
          <span className="text-slate-muted text-sm">{item.parent_cost_center || '-'}</span>
        ),
    },
    {
      key: 'company',
      header: 'Company',
      render: (item: AccountingCostCenter) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.company || ''}
            onChange={(e) => setFormData({ ...formData, company: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
          />
        ) : (
          <span className="text-slate-muted text-sm">{item.company || '-'}</span>
        ),
    },
    {
      key: 'is_group',
      header: 'Type',
      render: (item: AccountingCostCenter) => (
        <span className={`text-xs px-2 py-1 rounded ${
          item.is_group
            ? 'bg-purple-500/10 text-purple-400'
            : 'bg-slate-elevated text-slate-muted'
        }`}>
          {item.is_group ? 'Group' : 'Ledger'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: AccountingCostCenter) => (
        <div className="flex items-center justify-end gap-2">
          {editingId === item.id ? (
            <>
              <button
                onClick={() => handleUpdate(item.id)}
                className="p-1.5 rounded bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30"
                title="Save"
              >
                <Check className="w-4 h-4" />
              </button>
              <button
                onClick={cancelEdit}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                title="Cancel"
              >
                <X className="w-4 h-4" />
              </button>
            </>
          ) : deleteConfirm === item.id ? (
            <>
              <button
                onClick={() => handleDelete(item.id)}
                className="p-1.5 rounded bg-coral-alert/20 text-coral-alert hover:bg-coral-alert/30"
                title="Confirm Delete"
              >
                <Check className="w-4 h-4" />
              </button>
              <button
                onClick={() => setDeleteConfirm(null)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                title="Cancel"
              >
                <X className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => startEdit(item)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border hover:text-white"
                title="Edit"
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                onClick={() => setDeleteConfirm(item.id)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-coral-alert/20 hover:text-coral-alert"
                title="Delete"
              >
                <Trash2 className="w-4 h-4" />
              </button>
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
            <Target className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-white">Cost Centers</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ cost_center_name: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Cost Center
            </button>
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
            <h3 className="text-sm font-medium text-white mb-3">New Cost Center</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.cost_center_name}
                  onChange={(e) => setFormData({ ...formData, cost_center_name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Parent Cost Center</label>
                <select
                  value={formData.parent_cost_center || ''}
                  onChange={(e) => setFormData({ ...formData, parent_cost_center: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">None</option>
                  {costCenters.filter((cc) => cc.is_group).map((cc) => (
                    <option key={cc.id} value={cc.cost_center_name || cc.name}>{cc.cost_center_name || cc.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Company</label>
                <input
                  type="text"
                  value={formData.company || ''}
                  onChange={(e) => setFormData({ ...formData, company: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_group || false}
                    onChange={(e) => setFormData({ ...formData, is_group: e.target.checked })}
                    className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                  />
                  <span className="text-sm text-slate-muted">Is Group</span>
                </label>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!formData.cost_center_name.trim()}
                className="px-4 py-2 rounded-lg bg-teal-electric text-white text-sm font-medium hover:bg-teal-glow disabled:opacity-50 disabled:cursor-not-allowed"
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

        <DataTable
          columns={columns}
          data={costCenters}
          keyField="id"
          loading={false}
          emptyMessage="No cost centers found"
        />
      </div>
    </DashboardShell>
  );
}
