'use client';

import { Database } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'explorer',
    label: 'Explorer',
    description: 'Data tables and exports',
    icon: Database,
    items: [
      { name: 'Data Explorer', href: '/explorer', description: 'Query and export' },
    ],
  },
];

export default function ExplorerLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Explorer"
      sidebarTitle="Data Explorer"
      sidebarDescription="Tables, filters, and exports"
      baseRoute="/explorer"
      accentColor="slate"
      icon={Database}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
