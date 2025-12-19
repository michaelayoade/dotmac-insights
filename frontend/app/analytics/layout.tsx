'use client';

import { Activity } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Analytics',
    description: 'Dashboards and trends',
    icon: Activity,
    items: [
      { name: 'Overview', href: '/analytics', description: 'KPI summary' },
    ],
  },
];

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Analytics"
      sidebarTitle="Analytics"
      sidebarDescription="Cross-module performance"
      baseRoute="/analytics"
      accentColor="cyan"
      icon={Activity}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
