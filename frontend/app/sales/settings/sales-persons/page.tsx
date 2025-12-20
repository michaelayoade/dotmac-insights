'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { UserCheck, Plus, Pencil, Trash2, X, Check, AlertTriangle, ToggleLeft, ToggleRight } from 'lucide-react';
import { salesApi, SalesPerson, SalesPersonPayload } from '@/lib/api/domains/sales';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';

export default function SalesPersonsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<SalesPersonPayload>({ name: '', enabled: true });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const personsRes = useSWR('sales-persons', () => salesApi.getSalesPersons());
  const { isLoading, error, retry } = useSWRStatus(personsRes);
  const persons = personsRes.data?.items || [];

  const handleCreate = async () => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await salesApi.createSalesPerson(formData);
      setIsCreating(false);
      setFormData({ name: '', enabled: true });
      personsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    if (!formData.name.trim()) return;
    setActionError(null);
    try {
      await salesApi.updateSalesPerson(id, formData);
      setEditingId(null);
      setFormData({ name: '', enabled: true });
      personsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await salesApi.deleteSalesPerson(id);
      setDeleteConfirm(null);
      personsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const toggleEnabled = async (person: SalesPerson) => {
    setActionError(null);
    try {
      await salesApi.updateSalesPerson(person.id, { enabled: !person.enabled });
      personsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const startEdit = (person: SalesPerson) => {
    setEditingId(person.id);
    setFormData({
      name: person.name,
      employee: person.employee,
      parent_sales_person: person.parent_sales_person,
      is_group: person.is_group,
      enabled: person.enabled,
      commission_rate: person.commission_rate,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ name: '', enabled: true });
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (item: SalesPerson) =>
        editingId === item.id ? (
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
            autoFocus
          />
        ) : (
          <div className="flex flex-col">
            <span className="text-white font-medium">{item.name}</span>
            {item.employee_name && (
              <span className="text-xs text-slate-muted">{item.employee_name}</span>
            )}
          </div>
        ),
    },
    {
      key: 'parent',
      header: 'Reports To',
      render: (item: SalesPerson) =>
        editingId === item.id ? (
          <select
            value={formData.parent_sales_person || ''}
            onChange={(e) => setFormData({ ...formData, parent_sales_person: e.target.value || null })}
            className="w-full bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
          >
            <option value="">None</option>
            {persons.filter((p) => p.id !== item.id).map((p) => (
              <option key={p.id} value={p.name}>{p.name}</option>
            ))}
          </select>
        ) : (
          <span className="text-slate-muted text-sm">{item.parent_sales_person || '-'}</span>
        ),
    },
    {
      key: 'commission',
      header: 'Commission %',
      render: (item: SalesPerson) =>
        editingId === item.id ? (
          <input
            type="number"
            step="0.1"
            value={formData.commission_rate ?? ''}
            onChange={(e) => setFormData({ ...formData, commission_rate: e.target.value ? Number(e.target.value) : null })}
            className="w-20 bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-teal-electric"
            placeholder="0"
          />
        ) : (
          <span className="text-slate-muted text-sm">
            {item.commission_rate != null ? `${item.commission_rate}%` : '-'}
          </span>
        ),
    },
    {
      key: 'enabled',
      header: 'Status',
      render: (item: SalesPerson) => (
        <button
          onClick={() => toggleEnabled(item)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
            item.enabled !== false
              ? 'bg-emerald-success/10 text-emerald-success'
              : 'bg-slate-elevated text-slate-muted'
          }`}
        >
          {item.enabled !== false ? (
            <>
              <ToggleRight className="w-4 h-4" />
              Active
            </>
          ) : (
            <>
              <ToggleLeft className="w-4 h-4" />
              Disabled
            </>
          )}
        </button>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: SalesPerson) => (
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
            <UserCheck className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-white">Sales Persons</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ name: '', enabled: true }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Sales Person
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
            <h3 className="text-sm font-medium text-white mb-3">New Sales Person</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Sales person name"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Employee</label>
                <input
                  type="text"
                  value={formData.employee || ''}
                  onChange={(e) => setFormData({ ...formData, employee: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Link to employee"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Reports To</label>
                <select
                  value={formData.parent_sales_person || ''}
                  onChange={(e) => setFormData({ ...formData, parent_sales_person: e.target.value || null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="">None</option>
                  {persons.map((p) => (
                    <option key={p.id} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Commission %</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.commission_rate ?? ''}
                  onChange={(e) => setFormData({ ...formData, commission_rate: e.target.value ? Number(e.target.value) : null })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="0"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!formData.name.trim()}
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
          data={persons}
          keyField="id"
          loading={false}
          emptyMessage="No sales persons found"
        />
      </div>
    </DashboardShell>
  );
}
