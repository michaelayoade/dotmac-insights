'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { MapPin, Plus, Pencil, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { salesApi, Territory, TerritoryPayload } from '@/lib/api/domains/sales';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';
import { Button } from '@/components/ui';

export default function TerritoriesPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<TerritoryPayload>({ name: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const territoriesRes = useSWR('sales-territories', () => salesApi.getTerritories());
  const { isLoading, error, retry } = useSWRStatus(territoriesRes);
  const territories = territoriesRes.data?.items || [];

  const handleCreate = async () => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await salesApi.createTerritory(formData);
      setIsCreating(false);
      setFormData({ name: '' });
      territoriesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await salesApi.updateTerritory(id, formData);
      setEditingId(null);
      setFormData({ name: '' });
      territoriesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await salesApi.deleteTerritory(id);
      setDeleteConfirm(null);
      territoriesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (territory: Territory) => {
    setEditingId(territory.id);
    setFormData({
      name: territory.name,
      parent_territory: territory.parent_territory,
      is_group: territory.is_group,
      territory_manager: territory.territory_manager,
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
      render: (item: Territory) =>
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
      header: 'Parent Territory',
      render: (item: Territory) =>
        editingId === item.id ? (
          <select
            value={formData.parent_territory || ''}
            onChange={(e) => setFormData({ ...formData, parent_territory: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
          >
            <option value="">None</option>
            {territories.filter((t) => t.id !== item.id).map((t) => (
              <option key={t.id} value={t.name}>{t.name}</option>
            ))}
          </select>
        ) : (
          <span className="text-slate-muted text-sm">{item.parent_territory || '-'}</span>
        ),
    },
    {
      key: 'manager',
      header: 'Territory Manager',
      render: (item: Territory) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.territory_manager || ''}
            onChange={(e) => setFormData({ ...formData, territory_manager: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            placeholder="Manager name"
          />
        ) : (
          <span className="text-slate-muted text-sm">{item.territory_manager || '-'}</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: Territory) => (
        <div className="flex items-center justify-end gap-2">
          {editingId === item.id ? (
            <>
              <Button
                onClick={() => handleUpdate(item.id)}
                className="p-1.5 rounded bg-teal-electric/20 text-teal-electric hover:bg-teal-electric/30"
                title="Save"
              >
                <Check className="w-4 h-4" />
              </Button>
              <Button
                onClick={cancelEdit}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                title="Cancel"
              >
                <X className="w-4 h-4" />
              </Button>
            </>
          ) : deleteConfirm === item.id ? (
            <>
              <Button
                onClick={() => handleDelete(item.id)}
                className="p-1.5 rounded bg-coral-alert/20 text-coral-alert hover:bg-coral-alert/30"
                title="Confirm Delete"
              >
                <Check className="w-4 h-4" />
              </Button>
              <Button
                onClick={() => setDeleteConfirm(null)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border"
                title="Cancel"
              >
                <X className="w-4 h-4" />
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={() => startEdit(item)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-slate-border hover:text-foreground"
                title="Edit"
              >
                <Pencil className="w-4 h-4" />
              </Button>
              <Button
                onClick={() => setDeleteConfirm(item.id)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-coral-alert/20 hover:text-coral-alert"
                title="Delete"
              >
                <Trash2 className="w-4 h-4" />
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
            <MapPin className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Territories</h1>
          </div>
          {!isCreating && (
            <Button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ name: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Territory
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
            <h3 className="text-sm font-medium text-foreground mb-3">New Territory</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Territory name"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Parent Territory</label>
                <select
                  value={formData.parent_territory || ''}
                  onChange={(e) => setFormData({ ...formData, parent_territory: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">None</option>
                  {territories.map((t) => (
                    <option key={t.id} value={t.name}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Territory Manager</label>
                <input
                  type="text"
                  value={formData.territory_manager || ''}
                  onChange={(e) => setFormData({ ...formData, territory_manager: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Manager name"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Button
                onClick={handleCreate}
                disabled={!formData.name.trim()}
                className="px-4 py-2 rounded-lg bg-teal-electric text-foreground text-sm font-medium hover:bg-teal-glow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create
              </Button>
              <Button
                onClick={cancelEdit}
                className="px-4 py-2 rounded-lg bg-slate-elevated text-slate-muted text-sm hover:bg-slate-border"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        <DataTable
          columns={columns}
          data={territories}
          keyField="id"
          loading={false}
          emptyMessage="No territories found"
        />
      </div>
    </DashboardShell>
  );
}
