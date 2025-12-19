'use client';

import { TrendingUp, FileText } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

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
