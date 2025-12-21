'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Award, Plus, Pencil, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { hrApi, HrDesignation, HrDesignationPayload } from '@/lib/api/domains/hr';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';

export default function DesignationsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<HrDesignationPayload>({ designation_name: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const designationsRes = useSWR('hr-designations', () => hrApi.getDesignations());
  const { isLoading, error, retry } = useSWRStatus(designationsRes);
  const designations = designationsRes.data?.items || [];

  const handleCreate = async () => {
    if (!formData.designation_name.trim()) return;
    setActionError(null);
    try {
      await hrApi.createDesignation(formData);
      setIsCreating(false);
      setFormData({ designation_name: '' });
      designationsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.designation_name.trim()) return;
    setActionError(null);
    try {
      await hrApi.updateDesignation(id, formData);
      setEditingId(null);
      setFormData({ designation_name: '' });
      designationsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await hrApi.deleteDesignation(id);
      setDeleteConfirm(null);
      designationsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (desig: HrDesignation) => {
    setEditingId(desig.id);
    setFormData({
      designation_name: desig.designation_name || desig.name,
      description: desig.description,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ designation_name: '' });
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Designation',
      render: (item: HrDesignation) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.designation_name}
            onChange={(e) => setFormData({ ...formData, designation_name: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            autoFocus
          />
        ) : (
          <span className="text-foreground font-medium">{item.designation_name || item.name}</span>
        ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item: HrDesignation) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
            placeholder="Description"
          />
        ) : (
          <span className="text-slate-muted text-sm">{item.description || '-'}</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: HrDesignation) => (
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
            <Award className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Designations</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ designation_name: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Designation
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
            <h3 className="text-sm font-medium text-foreground mb-3">New Designation</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Designation Name *</label>
                <input
                  type="text"
                  value={formData.designation_name}
                  onChange={(e) => setFormData({ ...formData, designation_name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!formData.designation_name.trim()}
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
          data={designations}
          keyField="id"
          loading={false}
          emptyMessage="No designations found"
        />
      </div>
    </DashboardShell>
  );
}
