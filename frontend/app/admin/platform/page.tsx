'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cloud,
  CloudOff,
  Flag,
  Key,
  RefreshCw,
  Server,
  Settings,
  Shield,
  ToggleLeft,
  ToggleRight,
  XCircle,
  Clock,
  Zap,
  Globe,
  Lock,
} from 'lucide-react';
import {
  usePlatformStatus,
  usePlatformFeatureFlags,
  type PlatformFeatureFlag,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button, LoadingState } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

function StatusBadge({
  status,
  size = 'default',
}: {
  status: 'valid' | 'invalid' | 'expired' | 'unknown' | 'connected' | 'disconnected';
  size?: 'default' | 'small';
}) {
  const config = {
    valid: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Valid' },
    connected: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'Connected' },
    invalid: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', label: 'Invalid' },
    expired: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', label: 'Expired' },
    unknown: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', label: 'Unknown' },
    disconnected: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', label: 'Disconnected' },
  };

  const c = config[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        c.bg,
        c.border,
        c.text,
        size === 'small' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      )}
    >
      {(status === 'valid' || status === 'connected') && <CheckCircle2 className="w-3.5 h-3.5" />}
      {(status === 'invalid' || status === 'expired') && <XCircle className="w-3.5 h-3.5" />}
      {(status === 'unknown' || status === 'disconnected') && <AlertTriangle className="w-3.5 h-3.5" />}
      {c.label}
    </span>
  );
}

function FeatureFlagRow({ flag }: { flag: PlatformFeatureFlag }) {
  return (
    <div className="flex items-center justify-between px-5 py-3 hover:bg-slate-elevated/30 transition-colors">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center',
            flag.enabled ? 'bg-emerald-500/10' : 'bg-slate-elevated'
          )}
        >
          {flag.enabled ? (
            <ToggleRight className="w-4 h-4 text-emerald-400" />
          ) : (
            <ToggleLeft className="w-4 h-4 text-slate-400" />
          )}
        </div>
        <div>
          <p className="text-foreground font-medium text-sm font-mono">{flag.name}</p>
          <p className="text-slate-muted text-xs">{flag.description}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs px-2 py-0.5 rounded bg-slate-elevated text-slate-muted">
          {flag.category}
        </span>
        <span
          className={cn(
            'text-xs font-medium',
            flag.enabled ? 'text-emerald-400' : 'text-slate-muted'
          )}
        >
          {flag.enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>
    </div>
  );
}

export default function PlatformStatusPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('admin:read');
  const canFetch = !authLoading && !missingScope;
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
    mutate: refetchStatus,
  } = usePlatformStatus({ isPaused: () => !canFetch });

  const { data: featureFlags, isLoading: flagsLoading } = usePlatformFeatureFlags({
    isPaused: () => !canFetch,
  });

  const flagsByCategory = useMemo(() => {
    if (!featureFlags?.flags) return {};
    return featureFlags.flags.reduce<Record<string, PlatformFeatureFlag[]>>((acc, flag) => {
      const cat = flag.category || 'general';
      acc[cat] = acc[cat] || [];
      acc[cat].push(flag);
      return acc;
    }, {});
  }, [featureFlags]);

  const enabledFlagsCount = featureFlags?.flags.filter((f) => f.enabled).length ?? 0;
  const totalFlagsCount = featureFlags?.flags.length ?? 0;

  const isLoading = statusLoading || flagsLoading;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the admin:read permission to view this page."
        backHref="/"
        backLabel="Back to Dashboard"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-teal-500/20 to-cyan-500/20 rounded-xl">
            <Cloud className="w-6 h-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Platform Status</h1>
            <p className="text-slate-muted text-sm">
              Monitor platform health, license status, and feature flags
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => refetchStatus()}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </Button>
          <Link
            href="/admin/security"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <Shield className="w-4 h-4" />
            Security
          </Link>
        </div>
      </div>

      {/* Error State */}
      {statusError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="text-rose-400 font-medium">Failed to load platform status</p>
            <p className="text-rose-300/70 text-sm">
              {statusError.message || 'Please check your connection and try again.'}
            </p>
          </div>
        </div>
      )}

      {/* Platform Connection Status */}
      <div className="bg-gradient-to-br from-slate-card via-slate-card to-slate-elevated/50 border border-slate-border rounded-2xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-foreground">Platform Connection</h2>
          </div>
          {status && (
            <StatusBadge status={status.platform_configured ? 'connected' : 'disconnected'} />
          )}
        </div>

        {statusLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-slate-card border border-slate-border rounded-xl p-5 animate-pulse">
                <div className="h-4 w-20 bg-slate-700 rounded mb-2" />
                <div className="h-8 w-32 bg-slate-700 rounded" />
              </div>
            ))}
          </div>
        ) : status ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Environment"
              value={status.environment}
              icon={Server}
            />
            <StatCard
              title="License Status"
              value={<StatusBadge status={status.license.status} size="small" />}
              icon={Key}
              variant={status.license.status === 'valid' ? 'success' : status.license.status === 'expired' ? 'warning' : 'danger'}
              subtitle={status.license.message}
            />
            <StatCard
              title="Feature Flags"
              value={`${enabledFlagsCount}/${totalFlagsCount}`}
              icon={Flag}
              subtitle={`${enabledFlagsCount} enabled`}
            />
            <StatCard
              title="Telemetry"
              value={status.otel_enabled ? 'Enabled' : 'Disabled'}
              icon={Activity}
              variant={status.otel_enabled ? 'success' : undefined}
            />
          </div>
        ) : null}
      </div>

      {/* License Details */}
      {status?.license && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-amber-400" />
              <h3 className="font-semibold text-foreground">License Details</h3>
            </div>
            <StatusBadge status={status.license.status} />
          </div>
          <div className="p-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Status</p>
                <p className="text-foreground font-medium capitalize">{status.license.status}</p>
              </div>
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Message</p>
                <p className="text-foreground font-medium">{status.license.message}</p>
              </div>
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Grace Period</p>
                <div className="flex items-center gap-2">
                  {status.license.in_grace_period ? (
                    <>
                      <Clock className="w-4 h-4 text-amber-400" />
                      <span className="text-amber-400 font-medium">
                        {status.license.grace_period_hours}h remaining
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-muted">Not in grace period</span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Configured</p>
                <p className="text-foreground font-medium">{status.license.configured ? 'Yes' : 'No'}</p>
              </div>
            </div>

            {status.license.in_grace_period && (
              <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-amber-400 font-medium">License Grace Period Active</p>
                  <p className="text-amber-300/70 text-sm">
                    Your license has expired. You have {status.license.grace_period_hours} hours
                    to renew before service is interrupted.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Instance Info */}
      {status && (status.instance_id || status.tenant_id || status.platform_url) && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-foreground">Instance Information</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {status.instance_id && (
              <div className="p-3 bg-slate-elevated/50 rounded-lg">
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Instance ID</p>
                <p className="text-foreground font-mono text-sm truncate">{status.instance_id}</p>
              </div>
            )}
            {status.tenant_id && (
              <div className="p-3 bg-slate-elevated/50 rounded-lg">
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Tenant ID</p>
                <p className="text-foreground font-mono text-sm truncate">{status.tenant_id}</p>
              </div>
            )}
            {status.platform_url && (
              <div className="p-3 bg-slate-elevated/50 rounded-lg">
                <p className="text-slate-muted text-xs uppercase tracking-wide mb-1">Platform URL</p>
                <p className="text-foreground font-mono text-sm truncate">{status.platform_url}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feature Flags */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flag className="w-5 h-5 text-violet-400" />
            <h3 className="font-semibold text-foreground">Feature Flags</h3>
            {featureFlags && (
              <span className="text-xs px-2 py-0.5 rounded bg-slate-elevated text-slate-muted">
                Source: {featureFlags.source}
              </span>
            )}
          </div>
          {featureFlags && (
            <span className="text-sm text-slate-muted">
              {enabledFlagsCount} of {totalFlagsCount} enabled
            </span>
          )}
        </div>

        {flagsLoading ? (
          <div className="p-5 space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 animate-pulse">
                <div className="w-8 h-8 bg-slate-700 rounded-lg" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-slate-700 rounded mb-1" />
                  <div className="h-3 w-64 bg-slate-700 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : !featureFlags?.flags.length ? (
          <div className="p-8 text-center">
            <Flag className="w-10 h-10 text-slate-muted mx-auto mb-3" />
            <p className="text-slate-muted text-sm">No feature flags configured</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-border">
            {Object.entries(flagsByCategory).map(([category, flags]) => (
              <div key={category}>
                <div className="px-5 py-2 bg-slate-elevated/30">
                  <span className="text-xs font-medium text-slate-muted uppercase tracking-wide">
                    {category}
                  </span>
                </div>
                {flags.map((flag) => (
                  <FeatureFlagRow key={flag.name} flag={flag} />
                ))}
              </div>
            ))}
          </div>
        )}

        {featureFlags?.platform_precedence && (
          <div className="px-5 py-3 border-t border-slate-border bg-slate-elevated/30">
            <p className="text-xs text-slate-muted flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-teal-electric" />
              Platform feature flags take precedence over environment variables
            </p>
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/admin/security"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-3 bg-teal-500/10 rounded-xl">
              <Shield className="w-5 h-5 text-teal-400" />
            </div>
            <div className="flex-1">
              <h4 className="text-foreground font-medium flex items-center gap-2">
                Security & Controls
                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-slate-muted" />
              </h4>
              <p className="text-slate-muted text-sm">Roles, permissions, audit logs</p>
            </div>
          </div>
        </Link>

        <Link
          href="/admin/settings"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-3 bg-violet-500/10 rounded-xl">
              <Settings className="w-5 h-5 text-violet-400" />
            </div>
            <div className="flex-1">
              <h4 className="text-foreground font-medium flex items-center gap-2">
                System Settings
                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-slate-muted" />
              </h4>
              <p className="text-slate-muted text-sm">Configure integrations</p>
            </div>
          </div>
        </Link>

        <Link
          href="/sync"
          className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 hover:bg-slate-elevated/30 transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="p-3 bg-amber-500/10 rounded-xl">
              <RefreshCw className="w-5 h-5 text-amber-400" />
            </div>
            <div className="flex-1">
              <h4 className="text-foreground font-medium flex items-center gap-2">
                Data Sync
                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-slate-muted" />
              </h4>
              <p className="text-slate-muted text-sm">Sync status and logs</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
