'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import {
  Shield,
  ShieldCheck,
  Users,
  Key,
  History,
  Lock,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Settings,
  Eye,
  UserCog,
  Activity,
  Clock,
  Cloud,
} from 'lucide-react';
import { adminApi, type RoleResponse, type SettingsAuditEntry } from '@/lib/api/domains';
import { useSettingsAuditLog } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function MetricCard({
  label,
  value,
  icon: Icon,
  variant = 'default',
  href,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  variant?: 'default' | 'success' | 'warning' | 'danger';
  href?: string;
}) {
  const content = (
    <div
      className={cn(
        'bg-slate-card border border-slate-border rounded-xl p-5 transition-all',
        href && 'hover:border-slate-border/80 hover:bg-slate-elevated/30 cursor-pointer group'
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
        </div>
        <div
          className={cn(
            'p-3 rounded-xl',
            variant === 'success' && 'bg-emerald-500/10',
            variant === 'warning' && 'bg-amber-500/10',
            variant === 'danger' && 'bg-rose-500/10',
            variant === 'default' && 'bg-slate-elevated'
          )}
        >
          <Icon
            className={cn(
              'w-6 h-6',
              variant === 'success' && 'text-emerald-400',
              variant === 'warning' && 'text-amber-400',
              variant === 'danger' && 'text-rose-400',
              variant === 'default' && 'text-slate-400'
            )}
          />
        </div>
      </div>
      {href && (
        <div className="flex items-center gap-1 mt-3 text-sm text-slate-muted group-hover:text-teal-electric transition-colors">
          <span>Manage</span>
          <ArrowRight className="w-4 h-4" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

function QuickActionCard({
  title,
  description,
  icon: Icon,
  href,
  accentColor = 'slate',
}: {
  title: string;
  description: string;
  icon: React.ElementType;
  href: string;
  accentColor?: 'slate' | 'teal' | 'amber' | 'rose' | 'violet';
}) {
  return (
    <Link
      href={href}
      className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
    >
      <div className="flex items-start gap-4">
        <div
          className={cn(
            'p-3 rounded-xl',
            accentColor === 'teal' && 'bg-teal-500/10',
            accentColor === 'amber' && 'bg-amber-500/10',
            accentColor === 'rose' && 'bg-rose-500/10',
            accentColor === 'violet' && 'bg-violet-500/10',
            accentColor === 'slate' && 'bg-slate-elevated'
          )}
        >
          <Icon
            className={cn(
              'w-6 h-6',
              accentColor === 'teal' && 'text-teal-400',
              accentColor === 'amber' && 'text-amber-400',
              accentColor === 'rose' && 'text-rose-400',
              accentColor === 'violet' && 'text-violet-400',
              accentColor === 'slate' && 'text-slate-400'
            )}
          />
        </div>
        <div className="flex-1">
          <h3 className="text-white font-semibold flex items-center gap-2">
            {title}
            <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-slate-muted" />
          </h3>
          <p className="text-slate-muted text-sm mt-1">{description}</p>
        </div>
      </div>
    </Link>
  );
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleString('en-NG', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function SecurityPage() {
  const {
    data: roles,
    isLoading: rolesLoading,
    mutate: refetchRoles,
  } = useSWR<RoleResponse[]>('admin-roles', adminApi.listRoles);

  const { data: auditEntries, isLoading: auditLoading } = useSettingsAuditLog({ limit: 10 }) as {
    data: SettingsAuditEntry[] | undefined;
    isLoading: boolean;
  };

  const securityStats = useMemo(() => {
    const totalRoles = roles?.length ?? 0;
    const systemRoles = roles?.filter((r) => r.is_system).length ?? 0;
    const customRoles = totalRoles - systemRoles;
    const totalUsers = roles?.reduce((sum, r) => sum + r.user_count, 0) ?? 0;
    const recentAuditCount = auditEntries?.length ?? 0;

    return { totalRoles, systemRoles, customRoles, totalUsers, recentAuditCount };
  }, [roles, auditEntries]);

  const isLoading = rolesLoading || auditLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-slate-elevated rounded-xl">
            <ShieldCheck className="w-6 h-6 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Security & Controls</h1>
            <p className="text-slate-muted text-sm">
              Access management, audit trails, and data protections
            </p>
          </div>
        </div>
        <button
          onClick={() => refetchRoles()}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors self-start"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Security Overview */}
      <div className="bg-gradient-to-br from-slate-card via-slate-card to-slate-elevated/50 border border-slate-border rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-teal-electric" />
          <h2 className="text-lg font-semibold text-white">Security Overview</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Roles"
            value={isLoading ? '...' : securityStats.totalRoles}
            icon={Shield}
            variant="default"
            href="/admin/roles"
          />
          <MetricCard
            label="Users with Roles"
            value={isLoading ? '...' : securityStats.totalUsers}
            icon={Users}
            variant="success"
          />
          <MetricCard
            label="Custom Roles"
            value={isLoading ? '...' : securityStats.customRoles}
            icon={UserCog}
            variant="default"
          />
          <MetricCard
            label="Recent Audit Events"
            value={isLoading ? '...' : securityStats.recentAuditCount}
            icon={Activity}
            variant={securityStats.recentAuditCount > 0 ? 'warning' : 'default'}
            href="/admin/settings/audit"
          />
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Access Management</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickActionCard
            title="Roles & Permissions"
            description="Create and manage roles with scoped access controls"
            icon={Shield}
            href="/admin/roles"
            accentColor="teal"
          />
          <QuickActionCard
            title="Audit Log"
            description="Track all configuration changes and user actions"
            icon={History}
            href="/admin/settings/audit"
            accentColor="amber"
          />
          <QuickActionCard
            title="System Settings"
            description="Configure integrations and system-wide options"
            icon={Settings}
            href="/admin/settings"
            accentColor="violet"
          />
          <QuickActionCard
            title="Platform Status"
            description="License, feature flags, and platform health"
            icon={Cloud}
            href="/admin/platform"
            accentColor="teal"
          />
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Roles Summary */}
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-teal-electric" />
              <h3 className="font-semibold text-white">Roles</h3>
            </div>
            <Link
              href="/admin/roles"
              className="text-sm text-slate-muted hover:text-teal-electric transition-colors flex items-center gap-1"
            >
              Manage <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-border">
            {rolesLoading ? (
              <div className="p-5 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="w-8 h-8 bg-slate-700 rounded-lg" />
                    <div className="flex-1">
                      <div className="h-4 w-24 bg-slate-700 rounded mb-1" />
                      <div className="h-3 w-16 bg-slate-700 rounded" />
                    </div>
                  </div>
                ))}
              </div>
            ) : !roles?.length ? (
              <div className="p-8 text-center">
                <Shield className="w-10 h-10 text-slate-muted mx-auto mb-3" />
                <p className="text-slate-muted text-sm">No roles configured</p>
                <Link
                  href="/admin/roles"
                  className="text-teal-electric text-sm hover:underline mt-2 inline-block"
                >
                  Create your first role
                </Link>
              </div>
            ) : (
              roles.slice(0, 5).map((role) => (
                <div
                  key={role.id}
                  className="px-5 py-3 flex items-center justify-between hover:bg-slate-elevated/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center',
                        role.is_system ? 'bg-violet-500/10' : 'bg-teal-500/10'
                      )}
                    >
                      <Shield
                        className={cn(
                          'w-4 h-4',
                          role.is_system ? 'text-violet-400' : 'text-teal-400'
                        )}
                      />
                    </div>
                    <div>
                      <p className="text-white font-medium text-sm flex items-center gap-2">
                        {role.name}
                        {role.is_system && (
                          <span className="px-1.5 py-0.5 rounded bg-slate-elevated text-slate-muted text-[10px]">
                            System
                          </span>
                        )}
                      </p>
                      <p className="text-slate-muted text-xs">
                        {role.permissions.length} permissions
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-mono text-sm">{role.user_count}</p>
                    <p className="text-slate-muted text-xs">users</p>
                  </div>
                </div>
              ))
            )}
            {roles && roles.length > 5 && (
              <div className="px-5 py-3 text-center">
                <Link
                  href="/admin/roles"
                  className="text-sm text-slate-muted hover:text-teal-electric transition-colors"
                >
                  View all {roles.length} roles
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Recent Audit Activity */}
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-amber-400" />
              <h3 className="font-semibold text-white">Recent Activity</h3>
            </div>
            <Link
              href="/admin/settings/audit"
              className="text-sm text-slate-muted hover:text-teal-electric transition-colors flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-border">
            {auditLoading ? (
              <div className="p-5 space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="w-2 h-2 bg-slate-700 rounded-full" />
                    <div className="flex-1">
                      <div className="h-4 w-32 bg-slate-700 rounded mb-1" />
                      <div className="h-3 w-24 bg-slate-700 rounded" />
                    </div>
                  </div>
                ))}
              </div>
            ) : !auditEntries?.length ? (
              <div className="p-8 text-center">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                <p className="text-slate-muted text-sm">No recent changes</p>
                <p className="text-slate-muted text-xs mt-1">
                  Configuration changes will appear here
                </p>
              </div>
            ) : (
              auditEntries.slice(0, 6).map((entry) => (
                <div
                  key={entry.id}
                  className="px-5 py-3 hover:bg-slate-elevated/30 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        'w-2 h-2 rounded-full mt-2',
                        entry.action === 'create' && 'bg-emerald-400',
                        entry.action === 'update' && 'bg-blue-400',
                        entry.action === 'delete' && 'bg-rose-400',
                        entry.action === 'test' && 'bg-amber-400'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm">
                        <span
                          className={cn(
                            'font-medium capitalize',
                            entry.action === 'create' && 'text-emerald-400',
                            entry.action === 'update' && 'text-blue-400',
                            entry.action === 'delete' && 'text-rose-400',
                            entry.action === 'test' && 'text-amber-400'
                          )}
                        >
                          {entry.action}
                        </span>{' '}
                        <span className="text-slate-muted">{entry.group_name}</span>
                      </p>
                      <p className="text-slate-muted text-xs flex items-center gap-2 mt-1">
                        <span className="truncate">{entry.user_email}</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(entry.created_at)}
                        </span>
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Security Best Practices */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Lock className="w-5 h-5 text-slate-400" />
          <h3 className="font-semibold text-white">Security Best Practices</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-elevated/50">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5" />
            <div>
              <p className="text-white text-sm font-medium">Role-Based Access</p>
              <p className="text-slate-muted text-xs">
                Assign permissions through roles, not directly to users
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-elevated/50">
            <Eye className="w-5 h-5 text-blue-400 mt-0.5" />
            <div>
              <p className="text-white text-sm font-medium">Monitor Audit Logs</p>
              <p className="text-slate-muted text-xs">
                Review configuration changes regularly for anomalies
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-elevated/50">
            <Key className="w-5 h-5 text-amber-400 mt-0.5" />
            <div>
              <p className="text-white text-sm font-medium">Least Privilege</p>
              <p className="text-slate-muted text-xs">
                Grant only the minimum permissions needed for each role
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
