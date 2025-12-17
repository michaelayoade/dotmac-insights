'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { Plus, RefreshCw, Shield, Trash2, Save, CheckCircle2 } from 'lucide-react';
import { adminApi, type RoleResponse, type PermissionResponse } from '@/lib/api/domains';
import { cn } from '@/lib/utils';
import { useToast } from '@dotmac/core';

type FormState = {
  name: string;
  description: string;
  permissionIds: number[];
};

export default function RolesPage() {
  const { toast } = useToast();
  const { data: roles, mutate: mutateRoles, isLoading: rolesLoading } = useSWR<RoleResponse[]>('admin-roles', adminApi.listRoles);
  const { data: permissions, isLoading: permsLoading } = useSWR<PermissionResponse[]>('admin-permissions', () =>
    adminApi.listPermissions()
  );

  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const selectedRole = useMemo(() => roles?.find((r) => r.id === selectedRoleId) || null, [roles, selectedRoleId]);

  const [form, setForm] = useState<FormState>({
    name: '',
    description: '',
    permissionIds: [],
  });

  useEffect(() => {
    if (selectedRole) {
      setForm({
        name: selectedRole.name,
        description: selectedRole.description || '',
        permissionIds: permissions
          ? permissions.filter((p) => selectedRole.permissions.includes(p.scope)).map((p) => p.id)
          : [],
      });
    } else {
      setForm({ name: '', description: '', permissionIds: [] });
    }
  }, [selectedRole, permissions]);

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast({ title: 'Name is required', variant: 'error' });
      return;
    }
    setSaving(true);
    try {
      if (selectedRole) {
        await adminApi.updateRole(selectedRole.id, {
          name: form.name,
          description: form.description || null,
          permission_ids: form.permissionIds,
        });
        toast({ title: 'Role updated', variant: 'success' });
      } else {
        await adminApi.createRole({
          name: form.name,
          description: form.description || null,
          permission_ids: form.permissionIds,
        });
        toast({ title: 'Role created', variant: 'success' });
      }
      await mutateRoles();
      if (!selectedRole) {
        setForm({ name: '', description: '', permissionIds: [] });
      }
    } catch (err: any) {
      toast({ title: 'Failed to save role', description: err?.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedRole) return;
    if (!confirm('Delete this role?')) return;
    setDeleting(true);
    try {
      await adminApi.deleteRole(selectedRole.id);
      toast({ title: 'Role deleted', variant: 'success' });
      setSelectedRoleId(null);
      await mutateRoles();
    } catch (err: any) {
      toast({ title: 'Failed to delete role', description: err?.message, variant: 'error' });
    } finally {
      setDeleting(false);
    }
  };

  const togglePermission = (id: number) => {
    setForm((prev) => {
      const has = prev.permissionIds.includes(id);
      return {
        ...prev,
        permissionIds: has ? prev.permissionIds.filter((pid) => pid !== id) : [...prev.permissionIds, id],
      };
    });
  };

  const groupedPermissions = useMemo(() => {
    if (!permissions) return {};
    return permissions.reduce<Record<string, PermissionResponse[]>>((acc, perm) => {
      const key = perm.category || 'general';
      acc[key] = acc[key] || [];
      acc[key].push(perm);
      return acc;
    }, {});
  }, [permissions]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Roles & Permissions</h1>
          <p className="text-slate-muted">Create roles and assign permission scopes for modular RBAC.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setSelectedRoleId(null);
              setForm({ name: '', description: '', permissionIds: [] });
            }}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Role
          </button>
          <button
            onClick={() => mutateRoles()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
            <p className="text-sm text-slate-muted">Roles</p>
            {rolesLoading && <p className="text-xs text-slate-muted">Loading...</p>}
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-slate-muted">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Permissions</th>
                <th className="px-4 py-3 text-right">Users</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {(roles || []).map((role) => (
                <tr
                  key={role.id}
                  className={cn(
                    'cursor-pointer',
                    selectedRoleId === role.id ? 'bg-slate-elevated/60' : ''
                  )}
                  onClick={() => setSelectedRoleId(role.id)}
                >
                  <td className="px-4 py-3 text-white font-medium flex items-center gap-2">
                    <Shield className="w-4 h-4 text-teal-electric" />
                    {role.name}
                    {role.is_system && (
                      <span className="px-2 py-0.5 rounded-full bg-slate-elevated text-slate-muted text-[11px]">
                        System
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-muted">{role.description || '—'}</td>
                  <td className="px-4 py-3 text-slate-muted">{role.permissions.length}</td>
                  <td className="px-4 py-3 text-right text-slate-muted">{role.user_count}</td>
                </tr>
              ))}
              {!roles?.length && !rolesLoading && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-muted">
                    No roles found. Create your first role to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{selectedRole ? 'Edit Role' : 'New Role'}</h2>
              <p className="text-sm text-slate-muted">
                {selectedRole ? 'Update role and permissions.' : 'Create a reusable role with scoped access.'}
              </p>
            </div>
            {selectedRole && !selectedRole.is_system && (
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-rose-300 hover:text-rose-200 text-sm inline-flex items-center gap-1"
              >
                <Trash2 className="w-4 h-4" />
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            )}
          </div>

          <Field
            label="Name"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Support Agent"
          />
          <Field
            label="Description"
            value={form.description}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            placeholder="Scoped access for frontline support"
          />

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <p className="text-sm text-slate-muted">Permissions</p>
              {permsLoading && <span className="text-xs text-slate-muted">Loading...</span>}
            </div>
            <div className="space-y-3 max-h-64 overflow-auto pr-1">
              {Object.entries(groupedPermissions).map(([category, perms]) => (
                <div key={category} className="space-y-2">
                  <p className="text-xs text-slate-muted uppercase tracking-wide">{category}</p>
                  <div className="grid grid-cols-1 gap-2">
                    {perms.map((perm) => {
                      const checked = form.permissionIds.includes(perm.id);
                      return (
                        <label
                          key={perm.id}
                          className={cn(
                            'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                            checked ? 'border-teal-electric/60 bg-teal-electric/5' : 'border-slate-border hover:border-slate-elevated'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => togglePermission(perm.id)}
                            className="mt-1 accent-teal-electric"
                          />
                          <div>
                            <p className="text-sm text-white flex items-center gap-2">
                              {perm.name}
                              {checked && <CheckCircle2 className="w-4 h-4 text-teal-electric" />}
                            </p>
                            <p className="text-xs text-slate-muted">{perm.description || perm.scope}</p>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
              {!permissions?.length && !permsLoading && (
                <p className="text-xs text-slate-muted">No permissions available.</p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={handleSubmit}
              disabled={saving || selectedRole?.is_system}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                saving
                  ? 'bg-slate-elevated text-slate-muted'
                  : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
              )}
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : selectedRole ? 'Save Changes' : 'Create Role'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, ...inputProps } = props;
  return (
    <div className="space-y-2">
      <label className="text-sm text-slate-muted">{label}</label>
      <input
        {...inputProps}
        className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none"
      />
    </div>
  );
}
