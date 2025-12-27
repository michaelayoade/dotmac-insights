'use client';

import { LayoutDashboard, ShieldCheck, Settings, Webhook, Database, RefreshCw } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'admin',
    label: 'Administration',
    description: 'Platform and access',
    icon: ShieldCheck,
    items: [
      { name: 'Platform', href: '/admin/platform', description: 'System overview' },
      { name: 'Security', href: '/admin/security', description: 'Policies and sessions' },
      { name: 'Roles', href: '/admin/roles', description: 'Permissions and access' },
    ],
  },
  {
    key: 'data',
    label: 'Data',
    description: 'Import and migration',
    icon: Database,
    items: [
      { name: 'Migration', href: '/admin/migration', description: 'Import external data' },
    ],
  },
  {
    key: 'sync',
    label: 'Sync',
    description: 'Data synchronization',
    icon: RefreshCw,
    items: [
      { name: 'Dashboard', href: '/admin/sync', description: 'Sync overview' },
      { name: 'Failed Records', href: '/admin/sync/dlq', description: 'Dead letter queue' },
      { name: 'Cursors', href: '/admin/sync/cursors', description: 'Sync markers' },
      { name: 'Outbound', href: '/admin/sync/outbound', description: 'Outbound sync logs' },
      { name: 'Schedules', href: '/admin/sync/schedules', description: 'Sync scheduling' },
    ],
  },
  {
    key: 'settings',
    label: 'Settings',
    description: 'Configuration',
    icon: Settings,
    items: [
      { name: 'Overview', href: '/admin/settings', description: 'Settings hub' },
      { name: 'Email', href: '/admin/settings/email', description: 'SMTP and templates' },
      { name: 'Payments', href: '/admin/settings/payments', description: 'Gateways and billing' },
      { name: 'Webhooks', href: '/admin/settings/webhooks', description: 'Outbound integrations' },
      { name: 'SMS', href: '/admin/settings/sms', description: 'Messaging providers' },
      { name: 'Notifications', href: '/admin/settings/notifications', description: 'System alerts' },
      { name: 'Branding', href: '/admin/settings/branding', description: 'Logos and themes' },
      { name: 'Localization', href: '/admin/settings/localization', description: 'Regions and language' },
      { name: 'Audit Log', href: '/admin/settings/audit', description: 'Change history' },
    ],
  },
  {
    key: 'webhooks',
    label: 'Webhooks',
    description: 'Inbound and outbound',
    icon: Webhook,
    items: [
      { name: 'Overview', href: '/admin/webhooks', description: 'Webhook registry' },
      { name: 'Inbound', href: '/admin/webhooks/inbound', description: 'Inbound events' },
      { name: 'Omnichannel', href: '/admin/webhooks/omni', description: 'Channel integrations' },
    ],
  },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('admin:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-400" />
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="min-h-screen bg-slate-deep p-8">
        <AccessDenied />
      </div>
    );
  }

  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Administration"
      sidebarTitle="Admin"
      sidebarDescription="Platform and settings"
      baseRoute="/admin"
      accentColor="slate"
      icon={LayoutDashboard}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
