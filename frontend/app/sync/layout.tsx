'use client';

import { RefreshCw, Database, CreditCard, Server, MessageSquare, History, AlertTriangle } from 'lucide-react';
import { ModuleLayout, QuickLink } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    description: 'Sync overview',
    icon: Database,
    items: [
      { name: 'Sync Status', href: '/sync', description: 'All connectors & health' },
    ],
  },
  {
    key: 'connectors',
    label: 'Connectors',
    description: 'External platforms',
    icon: RefreshCw,
    items: [
      { name: 'Splynx', href: '/sync#splynx', description: 'Billing & customers' },
      { name: 'ERPNext', href: '/sync#erpnext', description: 'HR & operations' },
      { name: 'Chatwoot', href: '/sync#chatwoot', description: 'Support & conversations' },
    ],
  },
  {
    key: 'history',
    label: 'History & Logs',
    description: 'Sync activity',
    icon: History,
    items: [
      { name: 'Sync History', href: '/sync#history', description: 'Recent sync runs' },
      { name: 'Error Log', href: '/sync#errors', description: 'Failed syncs' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Sync All', href: '/sync', icon: RefreshCw, color: 'orange-400' },
  { label: 'View Errors', href: '/sync#errors', icon: AlertTriangle, color: 'coral-alert' },
];

export default function SyncLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Data Sync"
      sidebarTitle="Data Sync"
      sidebarDescription="Platform connectors & sync status"
      baseRoute="/sync"
      accentColor="orange"
      icon={Database}
      sections={sections}
      quickLinks={quickLinks}
    >
      {children}
    </ModuleLayout>
  );
}