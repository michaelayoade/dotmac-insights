'use client';

import {
  LayoutDashboard,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSection } from '@/components/ModuleLayout/types';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Overview',
    description: 'Core insights',
    icon: LayoutDashboard,
    items: [
      { name: 'Overview', href: '/insights/overview', description: 'Summary dashboards' },
      { name: 'Data Completeness', href: '/insights/completeness', description: 'Coverage and gaps' },
      { name: 'Customer Segments', href: '/insights/segments', description: 'Segmentation analysis' },
      { name: 'Customer Health', href: '/insights/health', description: 'Health scoring' },
      { name: 'Relationships', href: '/insights/relationships', description: 'Data links' },
      { name: 'Anomalies', href: '/insights/anomalies', description: 'Outlier detection' },
    ],
  },
];

export default function InsightsLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');

  if (authLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric" />
      </div>
    );
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Insights"
      sidebarTitle="Deep Insights"
      sidebarDescription="Completeness, segments, and anomalies"
      baseRoute="/insights"
      accentColor="violet"
      icon={LayoutDashboard}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
