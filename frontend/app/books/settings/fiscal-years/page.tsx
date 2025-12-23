'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Calendar, Plus, Pencil, Trash2, X, Check, AlertTriangle, Lock, Unlock } from 'lucide-react';
import { accountingApi, AccountingFiscalYear, AccountingFiscalYearPayload } from '@/lib/api/domains/accounting';
import { DataTable } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';
import { Button } from '@/components/ui';
import { formatAccountingDate } from '@/lib/formatters/accounting';

export default function FiscalYearsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<AccountingFiscalYearPayload>({ year_start_date: '', year_end_date: '' });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fiscalYearsRes = useSWR('accounting-fiscal-years', () => accountingApi.getFiscalYears());
  const { isLoading, error, retry } = useSWRStatus(fiscalYearsRes);
  const fiscalYears = fiscalYearsRes.data?.fiscal_years || [];
  const currentFY = fiscalYearsRes.data?.current_fiscal_year;

  const handleCreate = async () => {
    if (!formData.year_start_date || !formData.year_end_date) return;
    setActionError(null);
    try {
      await accountingApi.createFiscalYear(formData);
      setIsCreating(false);
      setFormData({ year_start_date: '', year_end_date: '' });
      fiscalYearsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    setActionError(null);
    try {
      await accountingApi.updateFiscalYear(id, formData);
      setEditingId(null);
      setFormData({ year_start_date: '', year_end_date: '' });
      fiscalYearsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await accountingApi.deleteFiscalYear(id);
      setDeleteConfirm(null);
      fiscalYearsRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (fy: AccountingFiscalYear) => {
    setEditingId(fy.id);
    setFormData({
      name: fy.name,
      year_start_date: fy.year_start_date,
      year_end_date: fy.year_end_date,
      is_closed: fy.is_closed,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ year_start_date: '', year_end_date: '' });
    setActionError(null);
  };

  const formatDate = (date: string) => {
    try {
      return new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return date;
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Fiscal Year',
      render: (item: AccountingFiscalYear) => (
        <div className="flex items-center gap-2">
          <span className="text-foreground font-medium">{item.name}</span>
          {currentFY?.id === item.id && (
            <span className="text-xs px-2 py-0.5 rounded bg-teal-electric/20 text-teal-electric">Current</span>
          )}
        </div>
      ),
    },
    {
      key: 'start_date',
      header: 'Start Date',
      render: (item: AccountingFiscalYear) =>
        editingId === item.id ? (
          <input
            type="date"
            value={formData.year_start_date}
            onChange={(e) => setFormData({ ...formData, year_start_date: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
          />
        ) : (
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.year_start_date)}</span>
        ),
    },
    {
      key: 'end_date',
      header: 'End Date',
      render: (item: AccountingFiscalYear) =>
        editingId === item.id ? (
          <input
            type="date"
            value={formData.year_end_date}
            onChange={(e) => setFormData({ ...formData, year_end_date: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-teal-electric"
          />
        ) : (
          <span className="text-slate-muted text-sm">{formatAccountingDate(item.year_end_date)}</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: AccountingFiscalYear) => (
        <span className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded ${
          item.is_closed
            ? 'bg-slate-elevated text-slate-muted'
            : 'bg-emerald-success/10 text-emerald-success'
        }`}>
          {item.is_closed ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
          {item.is_closed ? 'Closed' : 'Open'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: AccountingFiscalYear) => (
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
              <Button onClick={() => startEdit(item)} variant="ghost" size="sm" icon={Pencil} title="Edit">
                <Pencil className="w-4 h-4" />
              </Button>
              <Button
                onClick={() => setDeleteConfirm(item.id)}
                className="p-1.5 rounded bg-slate-elevated text-slate-muted hover:bg-coral-alert/20 hover:text-coral-alert"
                title="Delete"
                disabled={!item.disabled}
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
            <Calendar className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Fiscal Years</h1>
          </div>
          {!isCreating && (
            <Button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({ year_start_date: '', year_end_date: '' }); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Fiscal Year
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
            <h3 className="text-sm font-medium text-foreground mb-3">New Fiscal Year</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="e.g., FY 2024-25"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Start Date *</label>
                <input
                  type="date"
                  value={formData.year_start_date}
                  onChange={(e) => setFormData({ ...formData, year_start_date: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">End Date *</label>
                <input
                  type="date"
                  value={formData.year_end_date}
                  onChange={(e) => setFormData({ ...formData, year_end_date: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Button onClick={handleCreate} disabled={!formData.year_start_date || !formData.year_end_date} module="books">
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
          data={fiscalYears}
          keyField="id"
          loading={false}
          emptyMessage="No fiscal years found"
        />
      </div>
    </DashboardShell>
  );
}
