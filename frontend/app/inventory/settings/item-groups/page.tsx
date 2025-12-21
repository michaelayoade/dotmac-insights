'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Layers, Plus, Pencil, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { inventoryApi, InventoryItemGroup, InventoryItemGroupPayload } from '@/lib/api/domains/inventory';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';

export default function ItemGroupsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<InventoryItemGroupPayload>({ name: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const groupsRes = useSWR('inventory-item-groups', () => inventoryApi.getItemGroups());
  const { isLoading, error, retry } = useSWRStatus(groupsRes);
  const groups = groupsRes.data?.items || [];

  const handleCreate = async () => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await inventoryApi.createItemGroup(formData);
      setIsCreating(false);
      setFormData({ name: '' });
      groupsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await inventoryApi.updateItemGroup(id, formData);
      setEditingId(null);
      setFormData({ name: '' });
      groupsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await inventoryApi.deleteItemGroup(id);
      setDeleteConfirm(null);
      groupsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (group: InventoryItemGroup) => {
    setEditingId(group.id);
    setFormData({
      name: group.name,
      parent_item_group: group.parent_item_group,
      is_group: group.is_group,
      default_uom: group.default_uom,
      default_warehouse: group.default_warehouse,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ name: '' });
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (item: InventoryItemGroup) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            autoFocus
          />
        ) : (
          <span className="text-foreground font-medium">{item.name}</span>
        ),
    },
    {
      key: 'parent',
      header: 'Parent Group',
      render: (item: InventoryItemGroup) =>
        editingId === item.id ? (
          <select
            value={formData.parent_item_group || ''}
            onChange={(e) => setFormData({ ...formData, parent_item_group: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
          >
            <option value="">None</option>
            {groups.filter((g) => g.id !== item.id).map((g) => (
              <option key={g.id} value={g.name}>{g.name}</option>
            ))}
          </select>
        ) : (
          <span className="text-slate-muted text-sm">{item.parent_item_group || '-'}</span>
        ),
    },
    {
      key: 'default_uom',
      header: 'Default UOM',
      render: (item: InventoryItemGroup) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.default_uom || ''}
            onChange={(e) => setFormData({ ...formData, default_uom: e.target.value || null })}
            className="w-32 bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            placeholder="e.g., Nos"
          />
        ) : (
          <span className="text-slate-muted text-sm">{item.default_uom || '-'}</span>
        ),
    },
    {
      key: 'default_warehouse',
      header: 'Default Warehouse',
      render: (item: InventoryItemGroup) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.default_warehouse || ''}
            onChange={(e) => setFormData({ ...formData, default_warehouse: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            placeholder="Warehouse name"
          />
        ) : (
          <span className="text-slate-muted text-sm">{item.default_warehouse || '-'}</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: InventoryItemGroup) => (
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
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border hover:text-foreground"
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
            <Layers className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Item Groups</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ name: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Item Group
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
            <h3 className="text-sm font-medium text-foreground mb-3">New Item Group</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Item group name"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Parent Group</label>
                <select
                  value={formData.parent_item_group || ''}
                  onChange={(e) => setFormData({ ...formData, parent_item_group: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">None</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.name}>{g.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Default UOM</label>
                <input
                  type="text"
                  value={formData.default_uom || ''}
                  onChange={(e) => setFormData({ ...formData, default_uom: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="e.g., Nos, Kg"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Default Warehouse</label>
                <input
                  type="text"
                  value={formData.default_warehouse || ''}
                  onChange={(e) => setFormData({ ...formData, default_warehouse: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Warehouse name"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!formData.name.trim()}
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

        <DataTable
          columns={columns}
          data={groups}
          keyField="id"
          loading={false}
          emptyMessage="No item groups found"
        />
      </div>
    </DashboardShell>
  );
}
