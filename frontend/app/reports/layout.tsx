'use client';

import { TrendingUp, FileText } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'reports',
    label: 'Reports',
    description: 'Financial and performance',
    icon: FileText,
    items: [
      { name: 'Overview', href: '/reports', description: 'Report center' },
      { name: 'Revenue', href: '/reports/revenue', description: 'Topline trends' },
      { name: 'Expenses', href: '/reports/expenses', description: 'Spend breakdown' },
      { name: 'Profitability', href: '/reports/profitability', description: 'Margins and segments' },
      { name: 'Cash Position', href: '/reports/cash-position', description: 'Balances and runway' },
    ],
  },
];

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('reports:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
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
      moduleSubtitle="Reports"
      sidebarTitle="Reports"
      sidebarDescription="Revenue, expenses, and cash"
      baseRoute="/reports"
      accentColor="emerald"
      icon={TrendingUp}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}