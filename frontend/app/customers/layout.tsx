'use client';

import { Users } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Customers',
    description: 'Accounts and lifecycle',
    icon: Users,
    items: [
      { name: 'All Customers', href: '/customers', description: 'Customer directory' },
      { name: 'Analytics', href: '/customers/analytics', description: 'KPIs and cohorts' },
      { name: 'Insights', href: '/customers/insights', description: 'Health and growth' },
      { name: 'Blocked Customers', href: '/customers/blocked', description: 'At-risk accounts' },
      { name: 'Blocked Analytics', href: '/customers/analytics/blocked', description: 'Blocked trends' },
    ],
  },
];

export default function CustomersLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope(['customers:read', 'analytics:read']);

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
      moduleSubtitle="Customers"
      sidebarTitle="Customers"
      sidebarDescription="Accounts, analytics, and insights"
      baseRoute="/customers"
      accentColor="indigo"
      icon={Users}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
