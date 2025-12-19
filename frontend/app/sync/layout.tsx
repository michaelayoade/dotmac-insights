'use client';

import { RefreshCw } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'sync',
    label: 'Data Sync',
    description: 'External connectors',
    icon: RefreshCw,
    items: [
      { name: 'Sync Status', href: '/sync', description: 'Runs and logs' },
    ],
  },
];

export default function SyncLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Data Sync"
      sidebarTitle="Data Sync"
      sidebarDescription="External integrations"
      baseRoute="/sync"
      accentColor="orange"
      icon={RefreshCw}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
