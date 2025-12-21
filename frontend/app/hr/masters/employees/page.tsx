'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Users, Plus, Pencil, Trash2, X, Check, AlertTriangle, Eye } from 'lucide-react';
import { hrApi, HrEmployee, HrEmployeePayload } from '@/lib/api/domains/hr';
import { DataTable, Pagination } from '@/components/DataTable';
import { DashboardShell } from '@/components/ui/DashboardShell';
import { useSWRStatus } from '@/hooks/useSWRStatus';

export default function EmployeesPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<HrEmployeePayload>({});
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const employeesRes = useSWR(
    ['hr-employees', page, pageSize, search],
    () => hrApi.getEmployees({ search: search || undefined, limit: pageSize, offset: (page - 1) * pageSize })
  );
  const { isLoading, error, retry } = useSWRStatus(employeesRes);
  const employees = employeesRes.data?.items || [];
  const total = employeesRes.data?.total || 0;

  const handleCreate = async () => {
    if (!formData.first_name?.trim()) return;
    setActionError(null);
    try {
      await hrApi.createEmployee(formData);
      setIsCreating(false);
      setFormData({});
      employeesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleUpdate = async (id: number) => {
    setActionError(null);
    try {
      await hrApi.updateEmployee(id, formData);
      setEditingId(null);
      setFormData({});
      employeesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleDelete = async (id: number) => {
    setActionError(null);
    try {
      await hrApi.deleteEmployee(id);
      setDeleteConfirm(null);
      employeesRes.mutate();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const startEdit = (emp: HrEmployee) => {
    setEditingId(emp.id);
    setFormData({
      first_name: emp.name?.split(' ')[0],
      last_name: emp.name?.split(' ').slice(1).join(' '),
      department: emp.department,
      designation: emp.designation,
      status: emp.status,
      company_email: emp.email,
    });
    setIsCreating(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({});
    setActionError(null);
  };

  const columns = [
    {
      key: 'name',
      header: 'Employee',
      render: (item: HrEmployee) => (
        <div className="flex flex-col">
          <span className="text-foreground font-medium">{item.name}</span>
          <span className="text-xs text-slate-muted">{item.employee_number || item.email || '-'}</span>
        </div>
      ),
    },
    {
      key: 'department',
      header: 'Department',
      render: (item: HrEmployee) => (
        <span className="text-slate-muted text-sm">{item.department || '-'}</span>
      ),
    },
    {
      key: 'designation',
      header: 'Designation',
      render: (item: HrEmployee) => (
        <span className="text-slate-muted text-sm">{item.designation || '-'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: HrEmployee) => (
        <span className={`text-xs px-2 py-1 rounded ${
          item.status === 'Active' ? 'bg-emerald-success/10 text-emerald-success' :
          item.status === 'Left' ? 'bg-coral-alert/10 text-coral-alert' :
          'bg-slate-elevated text-slate-muted'
        }`}>
          {item.status || 'Active'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (item: HrEmployee) => (
        <div className="flex items-center justify-end gap-2">
          {deleteConfirm === item.id ? (
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
            <Users className="w-5 h-5 text-teal-electric" />
            <h1 className="text-xl font-semibold text-foreground">Employees</h1>
          </div>
          {!isCreating && (
            <button
              onClick={() => { setIsCreating(true); setEditingId(null); setFormData({}); }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric/10 border border-teal-electric/30 text-teal-electric text-sm hover:bg-teal-electric/20"
            >
              <Plus className="w-4 h-4" />
              Add Employee
            </button>
          )}
        </div>

        {actionError && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-coral-alert" />
            <span className="text-sm text-coral-alert">{actionError}</span>
          </div>
        )}

        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search employees..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full sm:w-64 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
        </div>

        {(isCreating || editingId) && (
          <div className="bg-slate-card border border-slate-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-foreground mb-3">
              {isCreating ? 'New Employee' : 'Edit Employee'}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-muted mb-1">First Name *</label>
                <input
                  type="text"
                  value={formData.first_name || ''}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Last Name</label>
                <input
                  type="text"
                  value={formData.last_name || ''}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Email</label>
                <input
                  type="email"
                  value={formData.company_email || ''}
                  onChange={(e) => setFormData({ ...formData, company_email: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Department</label>
                <input
                  type="text"
                  value={formData.department || ''}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Designation</label>
                <input
                  type="text"
                  value={formData.designation || ''}
                  onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">Status</label>
                <select
                  value={formData.status || 'Active'}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  <option value="Active">Active</option>
                  <option value="Left">Left</option>
                  <option value="Inactive">Inactive</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={() => isCreating ? handleCreate() : handleUpdate(editingId!)}
                disabled={!formData.first_name?.trim()}
                className="px-4 py-2 rounded-lg bg-teal-electric text-foreground text-sm font-medium hover:bg-teal-glow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCreating ? 'Create' : 'Save'}
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
          data={employees}
          keyField="id"
          loading={false}
          emptyMessage="No employees found"
        />

        {total > pageSize && (
          <Pagination
            total={total}
            limit={pageSize}
            offset={(page - 1) * pageSize}
            onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
            onLimitChange={(newLimit) => { setPageSize(newLimit); setPage(1); }}
          />
        )}
      </div>
    </DashboardShell>
  );
}
